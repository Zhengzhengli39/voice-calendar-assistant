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
# CALENDAR ASSISTANT - 简化版本，直接输入日期
# =============================================================================

class CalendarAssistant:
    def __init__(self):
        self.playwright = None
        self.context = None
        self.page = None
        self.initialized = False
        self.logged_in = False

        self.lock = threading.Lock()
        self.loop = asyncio.new_event_loop()
        self.storage_dir = Path("storage")
        self.storage_dir.mkdir(exist_ok=True)

    def _run(self, coro):
        return self.loop.run_until_complete(coro)

    async def _start_browser_async(self, manual_login: bool):
        logger.info("Starting Playwright browser with real Chrome profile...")

        # TODO: 替换成你的真实 Chrome 用户数据目录
        CHROME_USER_DATA_DIR = r"C:\Users\YOUR_USERNAME\AppData\Local\Google\Chrome\User Data"

        self.playwright = await async_playwright().start()
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=CHROME_USER_DATA_DIR,
            channel="chrome",
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ]
        )

        self.page = self.context.pages[0]
        await self.page.goto("https://calendar.google.com", wait_until="domcontentloaded")
        await asyncio.sleep(3)

        url = self.page.url
        if "accounts.google.com" in url:
            self.logged_in = False
            if manual_login:
                logger.info("Waiting for manual login...")
                await self.page.wait_for_url(
                    lambda u: "calendar.google.com" in u,
                    timeout=300000
                )
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
        """直接设置日期输入框的值"""
        try:
            # 尝试找到日期输入框
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
            
            # 点击日期输入框
            await date_input.click()
            await asyncio.sleep(0.2)
            
            # 清空现有内容
            await date_input.press("Control+A")
            await asyncio.sleep(0.2)
            await date_input.press("Backspace")
            await asyncio.sleep(0.5)
            
            # 输入日期 (格式: "Dec 30, 2025" 或 "12/30/2025")
            await date_input.fill(date_str)
            await asyncio.sleep(0.5)
            
            # 按Enter确认
            await date_input.press("Enter")
            await asyncio.sleep(0.5)
            
            logger.info(f"Date set to: {date_str}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set date input: {e}")
            return False

    async def _add_event_async(self, title, date, start, end):
        if not self.is_ready():
            return {"success": False, "message": "Browser not initialized"}

        if not self.logged_in:
            return {"success": False, "message": "Please login first"}

        await self.page.bring_to_front()
        await asyncio.sleep(1)

        # Press 'c' to create new event
        await self.page.keyboard.press("c")
        await asyncio.sleep(2)  # 等待对话框加载

        # 1. 填充事件标题
        try:
            # 尝试多个可能的选择器
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
            
        except Exception as e:
            logger.error(f"Error filling title: {e}")
            return {"success": False, "message": f"Failed to fill event title: {e}"}

        await asyncio.sleep(0.5)

        # 2. 设置日期 - 使用简单的输入方法
        try:
            logger.info(f"Setting date to: {date}")
            date_success = await self._set_date_input(date)
            if not date_success:
                # 尝试备用日期格式
                try:
                    # 将 "Dec 30, 2025" 转换为 "12/30/2025"
                    date_obj = datetime.strptime(date, "%b %d, %Y")
                    alt_date = date_obj.strftime("%m/%d/%Y")
                    logger.info(f"Trying alternative date format: {alt_date}")
                    date_success = await self._set_date_input(alt_date)
                except:
                    # 如果转换失败，尝试直接输入原始格式
                    logger.info(f"Trying original date format: {date}")
                    date_success = await self._set_date_input(date)
            
            if not date_success:
                return {"success": False, "message": "Failed to set date"}
            
            await asyncio.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Error setting date: {e}")
            return {"success": False, "message": f"Failed to set date: {e}"}

        # 3. 设置开始时间
        try:
            # 尝试找到开始时间输入框
            start_time_selectors = [
                'input[aria-label*="Start time"]',
                'div[aria-label*="Start time"][contenteditable="true"]',
                'input[placeholder*="Start time"]'
            ]
            
            start_time_input = None
            for selector in start_time_selectors:
                try:
                    start_time_input = await self.page.wait_for_selector(selector, timeout=2000)
                    if start_time_input:
                        await start_time_input.click()
                        await asyncio.sleep(0.2)
                        
                        # 清空现有内容
                        await start_time_input.press("Control+A")
                        await asyncio.sleep(0.2)
                        await start_time_input.press("Backspace")
                        await asyncio.sleep(0.5)
                        
                        # 输入开始时间
                        await start_time_input.fill(start)
                        await asyncio.sleep(0.5)
                        await start_time_input.press("Enter")
                        await asyncio.sleep(0.5)
                        break
                except:
                    continue
            
            if not start_time_input:
                return {"success": False, "message": "Could not find start time input"}
            
        except Exception as e:
            logger.error(f"Error setting start time: {e}")
            return {"success": False, "message": f"Failed to set start time: {e}"}

        # 4. 设置结束时间
        try:
            # 尝试找到结束时间输入框
            end_time_selectors = [
                'input[aria-label*="End time"]',
                'div[aria-label*="End time"][contenteditable="true"]',
                'input[placeholder*="End time"]'
            ]
            
            end_time_input = None
            for selector in end_time_selectors:
                try:
                    end_time_input = await self.page.wait_for_selector(selector, timeout=2000)
                    if end_time_input:
                        await end_time_input.click()
                        await asyncio.sleep(0.2)
                        
                        # 清空现有内容
                        await end_time_input.press("Control+A")
                        await asyncio.sleep(0.2)
                        await end_time_input.press("Backspace")
                        await asyncio.sleep(0.5)
                        
                        # 输入结束时间
                        await end_time_input.fill(end)
                        await asyncio.sleep(0.5)
                        await end_time_input.press("Enter")
                        await asyncio.sleep(0.5)
                        break
                except:
                    continue
            
            if not end_time_input:
                return {"success": False, "message": "Could not find end time input"}
            
        except Exception as e:
            logger.error(f"Error setting end time: {e}")
            return {"success": False, "message": f"Failed to set end time: {e}"}

        await asyncio.sleep(0.5)

        # 5. 点击保存按钮
        try:
            # 尝试多个可能的选择器来找到保存按钮
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
                    if save_button:
                        # 确保按钮可见且可点击
                        is_visible = await save_button.is_visible()
                        is_enabled = await save_button.is_enabled()
                        
                        if is_visible and is_enabled:
                            await save_button.click()
                            await asyncio.sleep(1)
                            break
                        else:
                            continue
                except:
                    continue
            
            if not save_button:
                # 如果找不到保存按钮，尝试按Enter键
                await self.page.keyboard.press("Enter")
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error clicking save button: {e}")
            return {"success": False, "message": f"Failed to save event: {e}"}

        # 等待保存完成
        await asyncio.sleep(2)
        
        return {
            "success": True,
            "message": f"Event '{title}' added on {date} from {start} to {end}"
        }

    def add_event(self, title, date, start, end):
        with self.lock:
            return self._run(self._add_event_async(title, date, start, end))

    def close(self):
        try:
            if self.context:
                self.loop.run_until_complete(self.context.close())
            if self.playwright:
                self.loop.run_until_complete(self.playwright.stop())
        except:
            pass

# =============================================================================
# VOICE PARSER - 修复版本，提供多种日期格式
# =============================================================================

class VoiceParser:
    def parse(self, text: str) -> Dict[str, str]:
        logger.info(f"Parsing text: {text}")
        
        # 转换为小写用于解析
        text_lower = text.lower().strip()
        
        # 1. 提取标题
        title = "Meeting"
        
        # 检查常见模式
        if "doctor appointment" in text_lower:
            title = "Doctor Appointment"
        elif "meeting" in text_lower:
            # 提取会议标题
            match = re.search(r'(?:schedule|add|create|book)\s+(.+?)\s+(?:at|on|for|tomorrow|today|next)', text_lower)
            if match:
                extracted = match.group(1).strip()
                if extracted and len(extracted) > 1:
                    title = extracted.title()
            else:
                title = "Meeting"
        else:
            # 通用标题提取
            patterns = [
                r'(?:schedule|add|create|book)\s+(.+?)\s+(?:at|on|for|tomorrow|today|next)',
                r'(?:i want to|i need to)\s+(?:schedule|add|create|book)\s+(.+?)\s+(?:at|on|for)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    extracted = match.group(1).strip()
                    if extracted and len(extracted) > 1:
                        title = extracted.title()
                        break
        
        # 2. 解析日期
        today = datetime.now()
        date_obj = today
        
        # 检查特定关键词
        if "tomorrow" in text_lower:
            date_obj = today + timedelta(days=1)
        elif "today" in text_lower:
            date_obj = today
        else:
            # 检查"next [weekday]"
            weekdays = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                'friday': 4, 'saturday': 5, 'sunday': 6
            }
            
            for weekday, day_num in weekdays.items():
                if f"next {weekday}" in text_lower:
                    days_ahead = (day_num - today.weekday() + 7) % 7
                    if days_ahead == 0:  # 如果是今天，跳到下周
                        days_ahead = 7
                    date_obj = today + timedelta(days=days_ahead)
                    break
            
            # 如果没有找到，使用dateparser
            if date_obj == today:
                try:
                    parsed = dateparser.parse(text_lower, settings={'PREFER_DATES_FROM': 'future'})
                    if parsed:
                        date_obj = parsed
                except Exception as e:
                    logger.error(f"Error parsing date with dateparser: {e}")
        
        # 3. 生成多种日期格式用于尝试
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        month = month_names[date_obj.month - 1]
        
        # 格式1: "Dec 30, 2025" (原始格式)
        date_str_1 = f"{month} {date_obj.day}, {date_obj.year}"
        
        # 格式2: "12/30/2025" (月/日/年)
        date_str_2 = f"{date_obj.month}/{date_obj.day}/{date_obj.year}"
        
        # 格式3: "Dec 30 2025" (无逗号)
        date_str_3 = f"{month} {date_obj.day} {date_obj.year}"
        
        logger.info(f"Generated date formats: '{date_str_1}', '{date_str_2}', '{date_str_3}'")
        
        # 4. 解析时间
        start_time = "9:00 AM"
        end_time = "10:00 AM"
        
        # 提取时间模式
        time_patterns = [
            r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)',
            r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)',
            r'(\d{1,2})\s*(am|pm)'
        ]
        
        time_match = None
        for pattern in time_patterns:
            time_match = re.search(pattern, text_lower, re.IGNORECASE)
            if time_match:
                break
        
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            period = time_match.group(3).lower()
            
            # 转换为24小时制
            if period == 'pm' and hour < 12:
                hour24 = hour + 12
            elif period == 'am' and hour == 12:
                hour24 = 0
            else:
                hour24 = hour
            
            # 格式化时间
            start_time = f"{hour}:{minute:02d} {period.upper()}"
            
            # 计算结束时间（1小时后）
            end_hour24 = (hour24 + 1) % 24
            if end_hour24 == 0:
                end_hour = 12
                end_period = "AM"
            elif end_hour24 < 12:
                end_hour = end_hour24
                end_period = "AM"
            elif end_hour24 == 12:
                end_hour = 12
                end_period = "PM"
            else:
                end_hour = end_hour24 - 12
                end_period = "PM"
            
            end_time = f"{end_hour}:{minute:02d} {end_period}"
        
        logger.info(f"Parse result: title='{title}', date='{date_str_1}', start='{start_time}', end='{end_time}'")
        
        return {
            "title": title,
            "date": date_str_1,  # 使用第一种格式作为默认
            "date_alt1": date_str_2,  # 备用格式1
            "date_alt2": date_str_3,  # 备用格式2
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
    return jsonify({
        "success": success,
        "logged_in": calendar.is_logged_in()
    })

@app.route("/api/add_event", methods=["POST"])
def api_add():
    data = request.json
    title = data.get("title", "Meeting")
    date = data.get("date")
    start = data.get("start") or data.get("start_time")
    end = data.get("end") or data.get("end_time")
    
    # 如果没有提供日期，使用今天
    if not date:
        today = datetime.now()
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        month = month_names[today.month - 1]
        date = f"{month} {today.day}, {today.year}"
    
    result = calendar.add_event(title, date, start, end)
    return jsonify({
        "success": result.get("success", False),
        "message": result.get("message", "Unknown error")
    })

@app.route("/api/debug_parse", methods=["POST"])
def debug_parse():
    """调试用：测试语音解析"""
    data = request.json
    text = data.get("text", "")
    parsed = parser.parse(text)
    
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    
    return jsonify({
        "original_text": text,
        "today": today.strftime("%Y-%m-%d (%A)"),
        "tomorrow": tomorrow.strftime("%Y-%m-%d (%A)"),
        "parsed_result": parsed
    })

# =============================================================================
# SOCKET.IO
# =============================================================================

@socketio.on("voice_command")
def voice_command(data):
    text = data.get("text", "")
    logger.info(f"Voice command received: {text}")
    
    if not calendar.is_ready():
        emit("voice_response", {"success": False, "message": "Please initialize first"})
        return

    parsed = parser.parse(text)
    logger.info(f"Parsed result: {parsed}")
    
    # 尝试使用主要日期格式
    result = calendar.add_event(parsed["title"], parsed["date"], parsed["start"], parsed["end"])
    
    # 如果主要格式失败，尝试备用格式
    if not result.get("success", False) and "Failed to set date" in result.get("message", ""):
        logger.info(f"Primary date format failed, trying alternative format: {parsed['date_alt1']}")
        result = calendar.add_event(parsed["title"], parsed["date_alt1"], parsed["start"], parsed["end"])
    
    emit("voice_response", {
        "success": result.get("success", False),
        "message": result.get("message", "Unknown error")
    })

@socketio.on('manual_login_request')
def handle_manual_login():
    try:
        success = calendar.initialize(manual_login=True)
        if success:
            emit('login_response', {
                "success": True,
                "message": "Manual login started. Please complete login in the browser."
            })
        else:
            emit('login_response', {
                "success": False,
                "message": "Failed to start manual login."
            })
    except Exception as e:
        emit('login_response', {
            "success": False,
            "message": f"Error during manual login: {e}"
        })

# =============================================================================
# SHUTDOWN
# =============================================================================

import atexit
atexit.register(calendar.close)

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("VOICE CALENDAR ASSISTANT READY")
    print("="*60)
    
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    print(f"Today: {today.strftime('%Y-%m-%d (%A)')}")
    print(f"Tomorrow: {tomorrow.strftime('%Y-%m-%d (%A)')}")
    
    print("\nTest commands:")
    print('1. "Schedule a meeting at tomorrow, 10:00 PM"')
    print('2. "Add doctor appointment at next Monday, 2:00 PM"')
    print('3. "Create event today at 3:30 PM"')
    print("\n" + "="*60)
    
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)