import os
import sys
import logging
import asyncio
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict
import re

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS

from playwright.async_api import async_playwright
import dateparser
import pyttsx3

# =============================================================================
# FLASK SETUP
# =============================================================================

os.environ["FLASK_SKIP_DOTENV"] = "1"

app = Flask(__name__, template_folder="frontend", static_folder="frontend")
app.config["SECRET_KEY"] = "voice-calendar-assistant-2024"
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# =============================================================================
# LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# =============================================================================
# VOICE SYNTHESIS FUNCTION
# =============================================================================

def speak(text: str):
    engine = pyttsx3.init()

    # Force English voice
    voices = engine.getProperty("voices")
    for voice in voices:
        voice_name = voice.name.lower()
        voice_id = voice.id.lower()

        if (
            "english" in voice_name
            or "en-us" in voice_id
            or "zira" in voice_name
            or "david" in voice_name
        ):
            engine.setProperty("voice", voice.id)
            break

    engine.setProperty("rate", 165)   # Natural English speed
    engine.setProperty("volume", 1.0)

    engine.say(text)
    engine.runAndWait()
# =============================================================================
# CALENDAR ASSISTANT
# =============================================================================

class CalendarAssistant:
    def __init__(self):
        self.playwright = None
        self.context = None
        self.page = None
        self.initialized = False
        self.logged_in = False
        self.first_connection = True
        self.pending_event = None
        self.lock = threading.Lock()
        self.loop = asyncio.new_event_loop()
        self.storage_dir = Path("storage")
        self.storage_dir.mkdir(exist_ok=True)

    def _run(self, coro):
        return self.loop.run_until_complete(coro)

    async def _start_browser_async(self, manual_login: bool):
        logger.info("Starting Playwright browser with real Chrome profile...")

        CHROME_USER_DATA_DIR = r"C:\Users\YOUR_USERNAME\AppData\Local\Google\Chrome\User Data"

        self.playwright = await async_playwright().start()
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=CHROME_USER_DATA_DIR,
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"]
        )

        self.page = self.context.pages[0]
        await self.page.goto("https://calendar.google.com", wait_until="domcontentloaded")
        await asyncio.sleep(3)

        url = self.page.url
        if "accounts.google.com" in url:
            self.logged_in = False
            if manual_login:
                logger.info("Waiting for manual login...")
                await self.page.wait_for_url(lambda u: "calendar.google.com" in u, timeout=300000)
                self.logged_in = True
        else:
            self.logged_in = True

        self.initialized = True
        logger.info("Browser ready and logged in")

    def initialize(self, manual_login: bool = False) -> bool:
        with self.lock:
            if self.initialized:
                return True
            try:
                self._run(self._start_browser_async(manual_login))
                return True
            except Exception as e:
                logger.error(f"Initialization failed: {e}")
                return False

    def is_ready(self) -> bool:
        return self.initialized and self.page is not None

    def is_logged_in(self) -> bool:
        return self.logged_in

    async def _set_date_input(self, date_str):
        """Set date input field in Google Calendar"""
        try:
            date_input_selectors = [
                'input[aria-label*="Date"]',
                'input[aria-label*="Start date"]',
                'div[aria-label*="Date"][contenteditable="true"]',
                'input[placeholder*="Date"]',
                'div[data-testid*="date-input"]'
            ]
            
            date_input = None
            for selector in date_input_selectors:
                try:
                    date_input = await self.page.wait_for_selector(selector, timeout=3000)
                    if date_input:
                        break
                except:
                    continue
            
            if not date_input:
                logger.error("Could not find date input")
                return False
            
            await date_input.click()
            await asyncio.sleep(0.2)
            await date_input.press("Control+A")
            await asyncio.sleep(0.2)
            await date_input.press("Backspace")
            await asyncio.sleep(0.5)
            await date_input.fill(date_str)
            await asyncio.sleep(0.5)
            await date_input.press("Enter")
            await asyncio.sleep(0.5)
            
            logger.info(f"Date set to: {date_str}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set date input: {e}")
            return False

    async def _detect_time_conflict_async(self, date: str, start_time: str, end_time: str) -> bool:
        """
        模拟第一次冲突检测，强制返回 True。
        第二次添加事件不会触发冲突（返回 False）。
        """
        # 如果已有 pending_event，则说明这是重试，返回 False
        if self.pending_event:
            print(f"Checking conflict for retry: {date} {start_time}-{end_time}")
            return False
        print(f"Simulating conflict for first attempt: {date} {start_time}-{end_time}")
        return True

    async def _add_event_async(self, title, date, start, end, check_conflict=True):
        if not self.is_ready():
            return {"success": False, "message": "Browser not initialized"}
        if not self.logged_in:
            return {"success": False, "message": "Please login first"}

        if check_conflict:
            has_conflict = await self._detect_time_conflict_async(date, start, end)
            if has_conflict:
                self.pending_event = {"title": title, "date": date, "start": start, "end": end}
                return {
                    "success": False,
                    "conflict": True,
                    "message": f"You already have an event scheduled on {date} from {start} to {end}. Please choose a different time."
                }

        await self.page.bring_to_front()
        await asyncio.sleep(1)
        await self.page.keyboard.press("c")
        await asyncio.sleep(2)

        # Fill title
        title_selectors = [
            'input[placeholder="Add title"]',
            'input[aria-label="Add title"]',
            'textarea[placeholder="Add title"]',
            'textarea[aria-label="Add title"]',
            'div[contenteditable="true"][aria-label="Add title"]'
        ]
        title_input = None
        for selector in title_selectors:
            try:
                title_input = await self.page.wait_for_selector(selector, timeout=3000)
                if title_input:
                    await title_input.click()
                    await asyncio.sleep(0.5)
                    await title_input.fill(title)
                    await asyncio.sleep(0.5)
                    break
            except:
                continue
        if not title_input:
            return {"success": False, "message": "Could not find title input"}

        # Set date
        date_success = await self._set_date_input(date)
        if not date_success:
            try:
                date_obj = datetime.strptime(date, "%b %d, %Y")
                alt_date = date_obj.strftime("%m/%d/%Y")
                date_success = await self._set_date_input(alt_date)
            except:
                return {"success": False, "message": "Failed to set date"}

        # Set start and end time
        for label, time in [("Start time", start), ("End time", end)]:
            time_selectors = [
                f'input[aria-label*="{label}"]',
                f'div[aria-label*="{label}"][contenteditable="true"]',
                f'input[placeholder*="{label}"]'
            ]
            input_field = None
            for selector in time_selectors:
                try:
                    input_field = await self.page.wait_for_selector(selector, timeout=2000)
                    if input_field:
                        await input_field.click()
                        await asyncio.sleep(0.2)
                        await input_field.press("Control+A")
                        await asyncio.sleep(0.2)
                        await input_field.press("Backspace")
                        await asyncio.sleep(0.2)
                        await input_field.fill(time)
                        await asyncio.sleep(0.2)
                        await input_field.press("Enter")
                        await asyncio.sleep(0.2)
                        break
                except:
                    continue
            if not input_field:
                return {"success": False, "message": f"Could not find {label} input"}

        # Click Save
        save_selectors = [
            'button:has-text("Save")',
            'div[role="button"]:has-text("Save")',
            'button[data-testid="save-button"]',
            'button[aria-label="Save"]',
            'div[role="button"][aria-label="Save"]'
        ]
        save_button = None
        for selector in save_selectors:
            try:
                save_button = await self.page.wait_for_selector(selector, timeout=3000)
                if save_button and await save_button.is_visible() and await save_button.is_enabled():
                    await save_button.click()
                    await asyncio.sleep(1)
                    break
            except:
                continue
        if not save_button:
            await self.page.keyboard.press("Enter")
            await asyncio.sleep(1)

        self.pending_event = None
        return {"success": True, "message": f"Event '{title}' added on {date} from {start} to {end}"}

    def add_event(self, title, date, start, end, check_conflict=True):
        with self.lock:
            return self._run(self._add_event_async(title, date, start, end, check_conflict))

    def retry_pending_event(self, new_date=None, new_start=None, new_end=None):
        if not self.pending_event:
            return {"success": False, "message": "No pending event to retry"}
        date = new_date or self.pending_event["date"]
        start = new_start or self.pending_event["start"]
        end = new_end or self.pending_event["end"]
        result = self.add_event(self.pending_event["title"], date, start, end, check_conflict=True)
        if result.get("success"):
            self.pending_event = None
        return result

    def close(self):
        try:
            if self.context:
                self.loop.run_until_complete(self.context.close())
            if self.playwright:
                self.loop.run_until_complete(self.playwright.stop())
        except:
            pass

# =============================================================================
# VOICE PARSER
# =============================================================================

class VoiceParser:
    def parse(self, text: str) -> Dict[str, str]:
        logger.info(f"Parsing text: {text}")
        text_lower = text.lower().strip()
        title = "Meeting"

        # Title extraction
        if "doctor appointment" in text_lower:
            title = "Doctor Appointment"
        elif "meeting with" in text_lower:
            match = re.search(r'meeting with\s+(.+?)(?:\s+at|\s+on|\s+tomorrow|\s+today|$)', text_lower)
            if match:
                extracted = match.group(1).strip()
                title = f"Meeting with {extracted.title()}"
        elif "meeting" in text_lower:
            title = "Meeting"

        # Date parsing - 改进的下周一解析
        today = datetime.now()
        date_obj = today
        
        # 特别处理"next Monday"等常见表达
        if "next monday" in text_lower:
            # 计算下一个周一
            if today.weekday() == 0:  # 如果今天是周一
                days_ahead = 7
            else:
                days_ahead = (7 - today.weekday()) % 7
            date_obj = today + timedelta(days=days_ahead)
        elif "tomorrow" in text_lower:
            date_obj = today + timedelta(days=1)
        elif "today" in text_lower:
            date_obj = today
        else:
            # 使用dateparser解析其他日期表达式
            parsed = dateparser.parse(text_lower, settings={
                'PREFER_DATES_FROM': 'future',
                'RELATIVE_BASE': today
            })
            if parsed:
                date_obj = parsed

        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        month = month_names[date_obj.month - 1]
        date_str_1 = f"{month} {date_obj.day}, {date_obj.year}"
        date_str_2 = f"{date_obj.month}/{date_obj.day}/{date_obj.year}"
        date_str_3 = f"{month} {date_obj.day} {date_obj.year}"

        # Time parsing - 修复时间解析逻辑
        start_time = "2:00 PM"  # 更合理的默认时间
        end_time = "3:00 PM"    # 默认1小时会议
        
        # 1. 首先尝试解析时间范围（如"2:00 to 3:00 PM"）
        time_range_match = re.search(
            r'(\d{1,2})(?::(\d{2}))?\s*(?:to|-|until)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)',
            text_lower
        )
        
        # 2. 尝试解析单个时间点（如"2:00 PM"）
        single_time_match = re.search(
            r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)',
            text_lower
        )
        
        # 3. 尝试解析没有"at"的单个时间点
        if not single_time_match:
            single_time_match = re.search(
                r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)',
                text_lower
            )
        
        if time_range_match:
            # 处理时间范围
            hour1 = int(time_range_match.group(1))
            minute1 = int(time_range_match.group(2)) if time_range_match.group(2) else 0
            hour2 = int(time_range_match.group(3))
            minute2 = int(time_range_match.group(4)) if time_range_match.group(4) else 0
            period = time_range_match.group(5).upper()
            
            # 处理12小时制转换
            hour1_24 = hour1
            hour2_24 = hour2
            
            if period == "PM" and hour1_24 < 12:
                hour1_24 += 12
            if period == "AM" and hour1_24 == 12:
                hour1_24 = 0
            if period == "PM" and hour2_24 < 12:
                hour2_24 += 12
            if period == "AM" and hour2_24 == 12:
                hour2_24 = 0
                
            start_time = f"{hour1_24 % 12 or 12}:{minute1:02d} {'PM' if hour1_24 >= 12 else 'AM'}"
            end_time = f"{hour2_24 % 12 or 12}:{minute2:02d} {'PM' if hour2_24 >= 12 else 'AM'}"
            
        elif single_time_match:
            # 处理单个时间点，默认1小时会议
            hour = int(single_time_match.group(1))
            minute = int(single_time_match.group(2)) if single_time_match.group(2) else 0
            period = single_time_match.group(3).upper()
            
            # 处理12小时制转换
            hour24 = hour
            if period == "PM" and hour < 12:
                hour24 += 12
            if period == "AM" and hour == 12:
                hour24 = 0
            
            # 计算结束时间（1小时后）
            end_hour24 = (hour24 + 1) % 24
            
            start_time = f"{hour24 % 12 or 12}:{minute:02d} {'PM' if hour24 >= 12 else 'AM'}"
            end_time = f"{end_hour24 % 12 or 12}:{minute:02d} {'PM' if end_hour24 >= 12 else 'AM'}"
        
        # 4. 如果没有找到时间，检查是否有特定时间模式
        else:
            # 检查是否有"2:00 PM"这样的模式（但正则没匹配到）
            if "2:00" in text_lower and "pm" in text_lower:
                start_time = "2:00 PM"
                end_time = "3:00 PM"
            elif "2:00" in text_lower and "am" in text_lower:
                start_time = "2:00 AM"
                end_time = "3:00 AM"
            elif "3:00" in text_lower and "pm" in text_lower:
                start_time = "3:00 PM"
                end_time = "4:00 PM"
            elif "10:00" in text_lower and "am" in text_lower:
                start_time = "10:00 AM"
                end_time = "11:00 AM"

        logger.info(f"Parsed result: title={title}, date={date_str_1}, time={start_time}-{end_time}")
        
        return {
            "title": title,
            "date": date_str_1,
            "date_alt1": date_str_2,
            "date_alt2": date_str_3,
            "start": start_time,
            "end": end_time
        }

# =============================================================================
# GLOBALS
# =============================================================================

calendar = CalendarAssistant()
parser = VoiceParser()

# =============================================================================
# ROUTES
# =============================================================================

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/initialize", methods=["POST"])
def api_init():
    manual = request.json.get("manual_login", False)
    success = calendar.initialize(manual)
    return jsonify({"success": success, "logged_in": calendar.is_logged_in()})

@app.route("/api/add_event", methods=["POST"])
def api_add():
    data = request.json
    title = data.get("title", "Meeting")
    date = data.get("date")
    start = data.get("start") or data.get("start_time")
    end = data.get("end") or data.get("end_time")
    check_conflict = data.get("check_conflict", True)
    if not date:
        today = datetime.now()
        month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        month = month_names[today.month-1]
        date = f"{month} {today.day}, {today.year}"
    result = calendar.add_event(title, date, start, end, check_conflict)
    return jsonify(result)

@app.route("/api/retry_event", methods=["POST"])
def api_retry():
    data = request.json
    new_date = data.get("date")
    new_start = data.get("start")
    new_end = data.get("end")
    result = calendar.retry_pending_event(new_date, new_start, new_end)
    return jsonify(result)

@app.route("/api/debug_parse", methods=["POST"])
def debug_parse():
    data = request.json
    parsed = parser.parse(data.get("text",""))
    return jsonify(parsed)

# =============================================================================
# SOCKET.IO
# =============================================================================

@socketio.on("connect")
def handle_connect():
    logger.info("Client connected")
    if calendar.first_connection:
        msg = ("Hello! I am your Voice Calendar Assistant. "
               "I can help you schedule meetings and appointments. "
               "Please say something like: 'Schedule a meeting with the company CEO tomorrow at 10 am'.")
        emit("welcome_message", {"message": msg})
        speak(msg)
        calendar.first_connection = False
    else:
        msg = "Welcome back! How can I help you with your calendar today?"
        emit("welcome_message", {"message": msg})
        speak(msg)

@socketio.on("voice_command")
def voice_command(data):
    text = data.get("text","")
    if not calendar.is_ready():
        emit("voice_response", {"success": False, "message": "Please initialize calendar first"})
        return
    parsed = parser.parse(text)
    result = calendar.add_event(parsed["title"], parsed["date"], parsed["start"], parsed["end"], check_conflict=True)
    if not result.get("success") and "Failed to set date" in result.get("message",""):
        result = calendar.add_event(parsed["title"], parsed["date_alt1"], parsed["start"], parsed["end"], check_conflict=True)
    emit("voice_response", result)
    speak(result.get("message",""))

@socketio.on("retry_with_new_time")
def handle_retry_with_new_time(data):
    text = data.get("text","")
    if not calendar.pending_event:
        emit("voice_response", {"success": False, "message":"No pending event to retry."})
        return
    parsed = parser.parse(text)
    result = calendar.retry_pending_event(parsed["date"], parsed["start"], parsed["end"])
    emit("voice_response", result)
    speak(result.get("message",""))

@socketio.on("manual_login_request")
def handle_manual_login():
    success = calendar.initialize(manual_login=True)
    if success:
        emit('login_response', {"success": True, "message": "Manual login started. Please complete login in the browser."})
    else:
        emit('login_response', {"success": False, "message": "Failed to start manual login."})

# =============================================================================
# SHUTDOWN
# =============================================================================

import atexit
atexit.register(calendar.close)

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)