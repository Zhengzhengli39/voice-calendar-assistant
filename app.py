import os
import sys
import logging
import asyncio
import threading
from datetime import datetime
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
    """
    SINGLE browser instance.
    Browser is started once and reused.
    Uses real Chrome profile to bypass Google automation restrictions.
    """

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

    # -------------------------------------------------------------------------

    def _run(self, coro):
        return self.loop.run_until_complete(coro)

    # -------------------------------------------------------------------------

    async def _start_browser_async(self, manual_login: bool):
        logger.info("Starting Playwright browser with real Chrome profile...")

        # TODO: 替换成你的真实 Chrome 用户数据目录
        CHROME_USER_DATA_DIR = r"C:\Users\YOUR_USERNAME\AppData\Local\Google\Chrome\User Data"

        self.playwright = await async_playwright().start()

        # 使用真实 Chrome profile 启动持久化浏览器
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

        # 打开 Google Calendar
        await self.page.goto("https://calendar.google.com", wait_until="domcontentloaded")
        await asyncio.sleep(3)

        # 检测登录状态
        url = self.page.url
        if "accounts.google.com" in url:
            self.logged_in = False
            if manual_login:
                logger.info("Waiting for manual login...")
                await self.page.wait_for_url(
                    lambda u: "calendar.google.com" in u,
                    timeout=300000  # 5 分钟
                )
                self.logged_in = True
        else:
            self.logged_in = True

        self.initialized = True
        logger.info("Browser ready and logged in")

    # -------------------------------------------------------------------------

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

    # -------------------------------------------------------------------------

    def is_ready(self) -> bool:
        return self.initialized and self.page is not None

    def is_logged_in(self) -> bool:
        return self.logged_in

    # -------------------------------------------------------------------------

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

        # Fill title
        title_input = await self.page.query_selector('input[aria-label="Add title"]')
        if title_input:
            await title_input.fill(title)

        await asyncio.sleep(1)

        # Fill date
        date_inputs = await self.page.query_selector_all('input[aria-label="Event date"]')
        if date_inputs and len(date_inputs) >= 1:
            await date_inputs[0].fill(date)

        # Fill start time
        start_inputs = await self.page.query_selector_all('input[aria-label="Start time"]')
        if start_inputs and len(start_inputs) >= 1:
            await start_inputs[0].fill(start)

        # Fill end time
        end_inputs = await self.page.query_selector_all('input[aria-label="End time"]')
        if end_inputs and len(end_inputs) >= 1:
            await end_inputs[0].fill(end)

        await asyncio.sleep(1)

        # Click Save
        save_btn = await self.page.query_selector('button:has-text("Save")')
        if save_btn:
            await save_btn.click()

        return {
            "success": True,
            "message": f"Event '{title}' added on {date} from {start} to {end}"
        }

    # -------------------------------------------------------------------------

    def add_event(self, title, date, start, end):
        with self.lock:
            return self._run(self._add_event_async(title, date, start, end))

    # -------------------------------------------------------------------------

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
        text = text.lower()

        date = dateparser.parse(text, settings={"PREFER_DATES_FROM": "future"})
        date_str = date.strftime("%Y-%m-%d") if date else datetime.now().strftime("%Y-%m-%d")

        time_match = re.search(r"(\d{1,2})(?:[:](\d{2}))?\s*(am|pm)?", text)
        hour = int(time_match.group(1)) if time_match else 9
        minute = int(time_match.group(2) or 0)

        if time_match and time_match.group(3) == "pm" and hour < 12:
            hour += 12

        start = f"{hour:02d}:{minute:02d}"
        end = f"{(hour+1)%24:02d}:{minute:02d}"

        return {
            "title": "Meeting",
            "date": date_str,
            "start": start,
            "end": end
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
    start = data.get("start") or data.get("start_time")
    end = data.get("end") or data.get("end_time")
    result = calendar.add_event(
        data["title"], data["date"], start, end
    )
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
    if not calendar.is_ready():
        emit("voice_response", {"success": False, "message": "Please initialize first"})
        return

    parsed = parser.parse(text)
    result = calendar.add_event(
        parsed["title"],
        parsed["date"],
        parsed["start"],
        parsed["end"]
    )
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
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
