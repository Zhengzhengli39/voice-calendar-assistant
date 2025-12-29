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
# CALENDAR ASSISTANT
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

    async def _add_event_async(self, title, date, start, end):
        if not self.is_ready():
            return {"success": False, "message": "Browser not initialized"}

        if not self.logged_in:
            return {"success": False, "message": "Please login first"}

        await self.page.bring_to_front()
        await asyncio.sleep(1)

        # Press 'c' to create new event
        await self.page.keyboard.press("c")
        await asyncio.sleep(2)

        # 填充事件标题
        try:
            # 使用多个选择器尝试找到标题输入框
            title_selectors = [
                'input[placeholder="Add title"]',
                'input[aria-label="Add title"]',
                'textarea[placeholder="Add title"]',
                'textarea[aria-label="Add title"]',
                'div[contenteditable="true"][role="textbox"]'
            ]
            
            title_input = None
            for selector in title_selectors:
                try:
                    title_input = await self.page.wait_for_selector(selector, timeout=3000)
                    if title_input:
                        await title_input.click()
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

        # 设置日期和时间
        try:
            # 根据截图，Google日历可能已经直接显示了正确的日期时间
            # 我们需要找到日期和时间输入区域
            
            # 首先尝试直接找到日期输入区域
            date_selectors = [
                'input[aria-label*="Date"]',
                'div[aria-label*="Date"]',
                'div[data-testid*="date"]',
                'div[role="button"][aria-label*="Date"]'
            ]
            
            date_input = None
            for selector in date_selectors:
                try:
                    date_input = await self.page.wait_for_selector(selector, timeout=2000)
                    if date_input:
                        await date_input.click()
                        await asyncio.sleep(0.5)
                        
                        # 清空现有内容
                        await date_input.press("Control+A")
                        await asyncio.sleep(0.2)
                        await date_input.press("Backspace")
                        await asyncio.sleep(0.5)
                        
                        # 输入新日期
                        await date_input.type(date, delay=100)
                        await asyncio.sleep(0.5)
                        await date_input.press("Enter")
                        await asyncio.sleep(1)
                        break
                except:
                    continue
            
            # 设置开始时间
            start_time_selectors = [
                'input[aria-label*="Start time"]',
                'div[aria-label*="Start time"]',
                'div[data-testid*="start-time"]',
                'input[placeholder*="Start time"]'
            ]
            
            start_time_input = None
            for selector in start_time_selectors:
                try:
                    start_time_input = await self.page.wait_for_selector(selector, timeout=2000)
                    if start_time_input:
                        await start_time_input.click()
                        await asyncio.sleep(0.5)
                        
                        # 清空现有内容
                        await start_time_input.press("Control+A")
                        await asyncio.sleep(0.2)
                        await start_time_input.press("Backspace")
                        await asyncio.sleep(0.5)
                        
                        # 输入开始时间
                        await start_time_input.type(start, delay=100)
                        await asyncio.sleep(0.5)
                        await start_time_input.press("Enter")
                        await asyncio.sleep(1)
                        break
                except:
                    continue
            
            # 设置结束时间
            end_time_selectors = [
                'input[aria-label*="End time"]',
                'div[aria-label*="End time"]',
                'div[data-testid*="end-time"]',
                'input[placeholder*="End time"]'
            ]
            
            end_time_input = None
            for selector in end_time_selectors:
                try:
                    end_time_input = await self.page.wait_for_selector(selector, timeout=2000)
                    if end_time_input:
                        await end_time_input.click()
                        await asyncio.sleep(0.5)
                        
                        # 清空现有内容
                        await end_time_input.press("Control+A")
                        await asyncio.sleep(0.2)
                        await end_time_input.press("Backspace")
                        await asyncio.sleep(0.5)
                        
                        # 输入结束时间
                        await end_time_input.type(end, delay=100)
                        await asyncio.sleep(0.5)
                        await end_time_input.press("Enter")
                        await asyncio.sleep(1)
                        break
                except:
                    continue
            
            # 如果找不到独立的日期/时间输入框，尝试使用更通用的方法
            if not date_input or not start_time_input:
                # 尝试找到日期时间组合区域
                datetime_area_selectors = [
                    'div[data-testid="quick-add-datetime"]',
                    'div[aria-label*="date and time"]',
                    'div[role="region"][aria-label*="date"]'
                ]
                
                for selector in datetime_area_selectors:
                    try:
                        datetime_area = await self.page.wait_for_selector(selector, timeout=1000)
                        if datetime_area:
                            await datetime_area.click()
                            await asyncio.sleep(1)
                            
                            # 使用键盘输入完整的日期时间字符串
                            # 格式: "Jan 5, 2026 10:00 PM"
                            datetime_str = f"{date} {start}"
                            await self.page.keyboard.type(datetime_str, delay=100)
                            await asyncio.sleep(0.5)
                            await self.page.keyboard.press("Enter")
                            await asyncio.sleep(1)
                            break
                    except:
                        continue
                    
        except Exception as e:
            logger.error(f"Error setting date/time: {e}")
            return {"success": False, "message": f"Failed to set date/time: {e}"}

        await asyncio.sleep(1)

        # 点击保存按钮
        try:
            # 尝试多个可能的选择器来找到保存按钮
            save_selectors = [
                'button:has-text("Save")',
                'div[role="button"]:has-text("Save")',
                'button[data-testid="save-button"]',
                'div[data-testid="save-button"]',
                '[aria-label="Save"]',
                'button[aria-label="Save"]',
                'div[aria-label="Save"]',
                'div[role="button"][aria-label="Save"]'
            ]
            
            save_button = None
            for selector in save_selectors:
                try:
                    save_button = await self.page.wait_for_selector(selector, timeout=3000)
                    if save_button:
                        await save_button.click()
                        await asyncio.sleep(1)
                        break
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
# VOICE PARSER - 修复版本
# =============================================================================

class VoiceParser:
    def _get_next_weekday(self, weekday_name):
        """获取下一个指定星期几的日期"""
        weekdays = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6
        }
        
        target_weekday = weekdays.get(weekday_name.lower())
        if target_weekday is None:
            return None
        
        today = datetime.now()
        days_ahead = target_weekday - today.weekday()
        if days_ahead <= 0:  # 如果今天已经是这个星期几或已经过了，则到下周
            days_ahead += 7
        
        return today + timedelta(days=days_ahead)

    def parse(self, text: str) -> Dict[str, str]:
        logger.info(f"Parsing text: {text}")
        
        # 保留原始文本用于提取标题
        original_text = text
        
        # 转换为小写用于解析
        text_lower = text.lower()
        
        # 1. 提取标题
        title = "Meeting"  # 默认标题
        
        # 移除命令关键词
        command_patterns = [
            r'^(?:add|create|schedule|book)\s+(.+)',
            r'^(?:i want to|i need to)\s+(?:add|create|schedule|book)\s+(.+)'
        ]
        
        for pattern in command_patterns:
            match = re.search(pattern, text_lower)
            if match:
                remaining_text = match.group(1)
                # 从剩余文本中提取标题（在时间/日期关键词之前的部分）
                title_part = re.split(r'\s+(?:at|on|for|tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday|next|\d)', remaining_text, maxsplit=1)[0]
                if title_part and len(title_part) > 1:
                    title = title_part.strip()
                    break
        
        # 如果标题包含"appointment"，处理它
        if "appointment" in title:
            # 提取"appointment"之前的内容
            parts = title.split("appointment")
            if len(parts) > 1 and parts[0]:
                title = parts[0].strip() + " Appointment"
            elif len(parts) == 1:
                title = "Appointment"
        
        # 标题首字母大写
        title = title.title()
        
        # 2. 解析日期 - 修复"next Monday"的问题
        date_obj = None
        
        # 检查是否包含"next [weekday]"
        weekday_pattern = r'next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)'
        weekday_match = re.search(weekday_pattern, text_lower)
        
        if weekday_match:
            # 使用我们的函数获取下一个星期几
            weekday_name = weekday_match.group(1)
            date_obj = self._get_next_weekday(weekday_name)
            logger.info(f"Found 'next {weekday_name}': {date_obj}")
        else:
            # 使用dateparser作为备用
            try:
                date_obj = dateparser.parse(text_lower, settings={
                    "PREFER_DATES_FROM": "future",
                    "RELATIVE_BASE": datetime.now()
                })
            except Exception as e:
                logger.error(f"Error parsing date with dateparser: {e}")
        
        if date_obj:
            # 格式化日期为Google日历接受的格式
            month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            month = month_names[date_obj.month - 1]
            date_str = f"{month} {date_obj.day}, {date_obj.year}"
        else:
            # 如果无法解析，使用今天
            today = datetime.now()
            month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            month = month_names[today.month - 1]
            date_str = f"{month} {today.day}, {today.year}"
        
        # 3. 解析时间
        start_time = ""
        end_time = ""
        
        # 提取时间模式
        time_patterns = [
            r'(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)',
            r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)',
            r'(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)'
        ]
        
        time_match = None
        for pattern in time_patterns:
            time_match = re.search(pattern, text_lower, re.IGNORECASE)
            if time_match:
                break
        
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            period = time_match.group(3).lower().replace('.', '') if time_match.group(3) else ""
            
            # 处理12小时制
            if period:
                if period == 'pm' and hour < 12:
                    hour24 = hour + 12
                elif period == 'am' and hour == 12:
                    hour24 = 0
                else:
                    hour24 = hour
                
                # 格式化时间 (12小时制)
                period_display = period.upper()
                start_time = f"{hour}:{minute:02d} {period_display}"
                
                # 计算结束时间 (默认1小时后)
                end_hour24 = (hour24 + 1) % 24
                
                # 转换回12小时制
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
            else:
                # 24小时制
                start_time = f"{hour:02d}:{minute:02d}"
                end_hour = (hour + 1) % 24
                end_time = f"{end_hour:02d}:{minute:02d}"
        else:
            # 默认时间: 上午9点到10点
            start_time = "9:00 AM"
            end_time = "10:00 AM"
        
        logger.info(f"Parse result: title='{title}', date='{date_str}', start='{start_time}', end='{end_time}'")
        
        return {
            "title": title,
            "date": date_str,
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
    
    result = calendar.add_event(parsed["title"], parsed["date"], parsed["start"], parsed["end"])
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
    print("\nVOICE CALENDAR ASSISTANT READY")
    print(f"Today is: {datetime.now().strftime('%A, %B %d, %Y')}")
    print("For testing: Say 'Add doctor appointment at next Monday, 10:00 PM'")
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)