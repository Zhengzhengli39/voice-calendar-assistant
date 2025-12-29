"""
Voice Calendar Assistant - Full Version with Web Speech API
Uses browser's built-in speech recognition (no compilation needed)
"""

import os
# 防止 Flask 自动加载 .env 文件
os.environ['FLASK_SKIP_DOTENV'] = '1'

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import asyncio
import logging
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from playwright.async_api import async_playwright
import dateparser
import pytz

# Initialize Flask app
app = Flask(__name__, template_folder='frontend', static_folder='frontend')
app.config['SECRET_KEY'] = 'voice-calendar-assistant-secret-key-2024'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('calendar_assistant.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CalendarAssistant:
    def __init__(self):
        self.auth_state_path = Path("storage/auth_state.json")
        self.auth_state_path.parent.mkdir(parents=True, exist_ok=True)
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.is_initialized = False
        
    async def initialize_async(self, manual_login=False):
        """Initialize browser with Playwright"""
        try:
            logger.info("Initializing Playwright browser...")
            self.playwright = await async_playwright().start()
            
            # Browser arguments
            browser_args = [
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
            ]
            
            # Check for existing auth state
            if self.auth_state_path.exists() and not manual_login:
                logger.info(f"Loading authentication state from {self.auth_state_path}")
                self.browser = await self.playwright.chromium.launch(
                    headless=False,  # Show browser window
                    args=browser_args
                )
                
                self.context = await self.browser.new_context(
                    storage_state=str(self.auth_state_path),
                    viewport={'width': 1280, 'height': 720}
                )
            else:
                logger.info("Starting new browser session for manual login")
                self.browser = await self.playwright.chromium.launch(
                    headless=False,  # Always show for manual login
                    args=browser_args
                )
                
                self.context = await self.browser.new_context(
                    viewport={'width': 1280, 'height': 720}
                )
            
            # Create new page
            self.page = await self.context.new_page()
            
            # Navigate to Google Calendar
            logger.info("Navigating to Google Calendar...")
            await self.page.goto('https://calendar.google.com', wait_until='networkidle')
            
            # Wait for calendar to load
            try:
                await self.page.wait_for_selector('text="Google Calendar"', timeout=10000)
                logger.info("Google Calendar loaded successfully")
                self.is_initialized = True
            except Exception as e:
                logger.warning(f"Calendar load warning: {str(e)}")
                # Still mark as initialized if we have a page
                self.is_initialized = True
            
            # If this was a manual login, save auth state
            if manual_login:
                await self.save_auth_state_async()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize browser: {str(e)}")
            self.is_initialized = False
            return False
    
    def initialize(self, manual_login=False):
        """Sync wrapper for initialize_async"""
        try:
            return asyncio.run(self.initialize_async(manual_login))
        except Exception as e:
            logger.error(f"Initialize sync error: {str(e)}")
            return False
    
    async def save_auth_state_async(self):
        """Save authentication state"""
        try:
            await self.context.storage_state(path=str(self.auth_state_path))
            logger.info(f"Authentication state saved to {self.auth_state_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving auth state: {str(e)}")
            return False
    
    def save_auth_state(self):
        """Sync wrapper for save_auth_state_async"""
        try:
            return asyncio.run(self.save_auth_state_async())
        except Exception as e:
            logger.error(f"Save auth state sync error: {str(e)}")
            return False
    
    async def add_event_async(self, title, date_str, start_time, end_time):
        """Add event to Google Calendar"""
        try:
            logger.info(f"Adding event: {title} on {date_str} from {start_time} to {end_time}")
            
            # Ensure page is ready
            if not self.page:
                await self.page.goto('https://calendar.google.com')
            
            # Click create button
            try:
                await self.page.click('div[role="button"]:has-text("Create")', timeout=5000)
            except:
                # Try alternative selector
                create_buttons = await self.page.query_selector_all('div[role="button"]')
                for btn in create_buttons:
                    text = await btn.text_content()
                    if text and 'Create' in text:
                        await btn.click()
                        break
            
            # Wait for event dialog
            await self.page.wait_for_selector('div[role="dialog"]', timeout=5000)
            
            # Fill event title
            await self.page.fill('input[aria-label="Add title"]', title)
            
            # Set date
            date_input = await self.page.query_selector('input[aria-label*="Date"]')
            if date_input:
                await date_input.click()
                await date_input.fill(date_str)
                await self.page.keyboard.press('Enter')
                await asyncio.sleep(0.5)
            
            # Set start time
            start_input = await self.page.query_selector('input[aria-label*="Start time"]')
            if start_input:
                await start_input.click()
                await start_input.fill(start_time)
                await self.page.keyboard.press('Enter')
                await asyncio.sleep(0.5)
            
            # Set end time
            end_input = await self.page.query_selector('input[aria-label*="End time"]')
            if end_input:
                await end_input.click()
                await end_input.fill(end_time)
                await self.page.keyboard.press('Enter')
                await asyncio.sleep(0.5)
            
            # Check for conflicts (simplified)
            conflict = await self.check_conflict_async()
            if conflict:
                return {
                    'success': False,
                    'conflict': True,
                    'message': f'The time slot {start_time} to {end_time} on {date_str} is already occupied.'
                }
            
            # Save event
            save_buttons = await self.page.query_selector_all('button')
            for btn in save_buttons:
                text = await btn.text_content()
                if text and 'Save' in text:
                    await btn.click()
                    break
            
            # Wait for save to complete
            await asyncio.sleep(2)
            
            logger.info(f"Event '{title}' added successfully")
            
            return {
                'success': True,
                'message': f"Event '{title}' has been added to your calendar on {date_str} from {start_time} to {end_time}.",
                'event_title': title,
                'date': date_str,
                'start_time': start_time,
                'end_time': end_time
            }
            
        except Exception as e:
            logger.error(f"Error adding event: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def add_event(self, title, date_str, start_time, end_time):
        """Sync wrapper for add_event_async"""
        try:
            return asyncio.run(self.add_event_async(title, date_str, start_time, end_time))
        except Exception as e:
            logger.error(f"Add event sync error: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    async def check_conflict_async(self):
        """Check if there's a scheduling conflict"""
        try:
            # Look for conflict indicators
            conflict_indicators = ['Busy', 'Conflict', 'Overlap', 'Not available']
            for indicator in conflict_indicators:
                elements = await self.page.query_selector_all(f'text="{indicator}"')
                if elements and len(elements) > 0:
                    return True
            return False
        except:
            return False
    
    async def close_async(self):
        """Close browser"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("Browser closed successfully")
        except Exception as e:
            logger.error(f"Error closing browser: {str(e)}")
    
    def close(self):
        """Sync wrapper for close_async"""
        asyncio.run(self.close_async())

class VoiceCommandParser:
    """Parse natural language voice commands"""
    
    def __init__(self):
        self.timezone = pytz.UTC
        
    def parse_voice_command(self, text):
        """
        Parse natural language command for calendar event
        
        Args:
            text: Voice command text
            
        Returns:
            dict: Parsed event details or None if parsing fails
        """
        try:
            logger.info(f"Parsing voice command: {text}")
            
            # Initialize result with defaults
            result = {
                'title': self._extract_title(text),
                'date': self._extract_date(text),
                'start_time': self._extract_start_time(text),
                'end_time': self._extract_end_time(text),
                'raw_text': text,
                'confidence': 1.0
            }
            
            # If no time found, use default
            if not result['start_time']:
                result['start_time'] = '10:00'
                result['end_time'] = '11:00'
            
            # If no date found, use tomorrow
            if not result['date']:
                tomorrow = datetime.now() + timedelta(days=1)
                result['date'] = tomorrow.strftime('%Y-%m-%d')
            
            # Validate required fields
            if not result['title'] or result['title'].lower() == 'meeting':
                result['title'] = 'Meeting'
            
            logger.info(f"Parsed result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing voice command: {str(e)}")
            return None
    
    def _extract_title(self, text):
        """Extract event title from text"""
        try:
            # Remove common date/time phrases
            patterns_to_remove = [
                r'\b(add|schedule|create|set up|book)\s+(a|an|the)?\s*',
                r'\b(to|on|for|at|from|until|till)\s+',
                r'\b(calendar|event|meeting|appointment)\s*',
                r'\b(today|tomorrow|yesterday|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
                r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b',
                r'\b(\d{1,2}):(\d{2})\s*(am|pm)?\b',
                r'\b(\d{1,2})\s*(am|pm)\b',
                r'\b(morning|afternoon|evening|night)\b',
                r'\b(\d+)\s*(hour|hours|minute|minutes)\b',
            ]
            
            title = text.lower()
            for pattern in patterns_to_remove:
                title = re.sub(pattern, '', title, flags=re.IGNORECASE)
            
            # Clean up extra spaces and common words
            title = re.sub(r'\s+', ' ', title).strip()
            common_words = ['the', 'a', 'an', 'my', 'with', 'and', 'or', 'but']
            
            words = title.split()
            filtered_words = [word for word in words if word not in common_words and len(word) > 2]
            
            if filtered_words:
                return ' '.join(filtered_words).capitalize()
            else:
                return 'Meeting'
                
        except:
            return 'Meeting'
    
    def _extract_date(self, text):
        """Extract date from text"""
        try:
            # Use dateparser for natural language dates
            parsed_date = dateparser.parse(text, settings={
                'PREFER_DATES_FROM': 'future',
                'RELATIVE_BASE': datetime.now()
            })
            
            if parsed_date:
                return parsed_date.strftime('%Y-%m-%d')
            
            # Manual fallback patterns
            today = datetime.now()
            
            if re.search(r'\btoday\b', text, re.IGNORECASE):
                return today.strftime('%Y-%m-%d')
            elif re.search(r'\btomorrow\b', text, re.IGNORECASE):
                return (today + timedelta(days=1)).strftime('%Y-%m-%d')
            elif re.search(r'\bday after tomorrow\b', text, re.IGNORECASE):
                return (today + timedelta(days=2)).strftime('%Y-%m-%d')
            
            # Days of week
            days = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                'friday': 4, 'saturday': 5, 'sunday': 6
            }
            
            for day_name, day_offset in days.items():
                if re.search(r'\b' + day_name + r'\b', text, re.IGNORECASE):
                    current_day = today.weekday()
                    days_ahead = day_offset - current_day
                    if days_ahead <= 0:
                        days_ahead += 7
                    return (today + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
            
            return None
            
        except:
            return None
    
    def _extract_start_time(self, text):
        """Extract start time from text"""
        try:
            # Pattern for 12-hour format
            pattern = r'(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)?'
            matches = re.findall(pattern, text)
            
            if matches:
                hour, minute, period = matches[0]
                hour = int(hour)
                minute = int(minute)
                
                # Convert to 24-hour format
                if period and period.lower() == 'pm' and hour < 12:
                    hour += 12
                elif period and period.lower() == 'am' and hour == 12:
                    hour = 0
                
                return f"{hour:02d}:{minute:02d}"
            
            # Pattern for simple hour
            pattern = r'(\d{1,2})\s*(am|pm|AM|PM)'
            matches = re.findall(pattern, text)
            
            if matches:
                hour, period = matches[0]
                hour = int(hour)
                minute = 0
                
                if period and period.lower() == 'pm' and hour < 12:
                    hour += 12
                elif period and period.lower() == 'am' and hour == 12:
                    hour = 0
                
                return f"{hour:02d}:00"
            
            # Default times based on keywords
            if re.search(r'\bmorning\b', text, re.IGNORECASE):
                return '09:00'
            elif re.search(r'\bafternoon\b', text, re.IGNORECASE):
                return '14:00'
            elif re.search(r'\bevening\b', text, re.IGNORECASE):
                return '18:00'
            elif re.search(r'\bnight\b', text, re.IGNORECASE):
                return '20:00'
            
            return None
            
        except:
            return None
    
    def _extract_end_time(self, text):
        """Extract end time from text"""
        try:
            # First try to find explicit end time
            time_pattern = r'(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)?'
            matches = re.findall(time_pattern, text)
            
            if len(matches) >= 2:
                hour, minute, period = matches[1]
                hour = int(hour)
                minute = int(minute)
                
                if period and period.lower() == 'pm' and hour < 12:
                    hour += 12
                elif period and period.lower() == 'am' and hour == 12:
                    hour = 0
                
                return f"{hour:02d}:{minute:02d}"
            
            # Check for duration
            duration_pattern = r'for\s+(\d+)\s*(hour|hours|hr|hrs|minute|minutes|min|mins)'
            match = re.search(duration_pattern, text, re.IGNORECASE)
            
            if match:
                duration = int(match.group(1))
                unit = match.group(2).lower()
                
                # Get start time
                start_time = self._extract_start_time(text)
                if start_time:
                    start_hour, start_minute = map(int, start_time.split(':'))
                    
                    if 'hour' in unit:
                        end_hour = (start_hour + duration) % 24
                        end_minute = start_minute
                    else:  # minutes
                        total_minutes = start_hour * 60 + start_minute + duration
                        end_hour = (total_minutes // 60) % 24
                        end_minute = total_minutes % 60
                    
                    return f"{end_hour:02d}:{end_minute:02d}"
            
            # Default: 1 hour after start time
            start_time = self._extract_start_time(text)
            if start_time:
                start_hour, start_minute = map(int, start_time.split(':'))
                end_hour = (start_hour + 1) % 24
                return f"{end_hour:02d}:{start_minute:02d}"
            
            return '11:00'  # Default end time
            
        except:
            return '11:00'  # Default end time

# Global instances
calendar_assistant = CalendarAssistant()
voice_parser = VoiceCommandParser()

@app.route('/')
def index():
    """Serve the main interface"""
    return render_template('index.html')

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'Voice Calendar Assistant',
        'initialized': calendar_assistant.is_initialized
    })

@app.route('/api/initialize', methods=['POST'])
def initialize_assistant():
    """Initialize the calendar assistant"""
    try:
        data = request.get_json() or {}
        manual_login = data.get('manual_login', False)
        
        logger.info(f"Initializing assistant (manual_login={manual_login})")
        
        success = calendar_assistant.initialize(manual_login)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Calendar assistant initialized successfully',
                'requires_login': manual_login or not calendar_assistant.auth_state_path.exists(),
                'initialized': True
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to initialize calendar assistant'
            })
            
    except Exception as e:
        logger.error(f"Error in initialize_assistant: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/save_auth', methods=['POST'])
def save_auth_state():
    """Save authentication state"""
    try:
        success = calendar_assistant.save_auth_state()
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Authentication state saved successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to save authentication state'
            })
            
    except Exception as e:
        logger.error(f"Error in save_auth_state: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/parse_command', methods=['POST'])
def parse_voice_command():
    """Parse voice command text"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({
                'success': False,
                'error': 'No text provided'
            })
        
        text = data['text']
        parsed = voice_parser.parse_voice_command(text)
        
        if parsed:
            return jsonify({
                'success': True,
                'data': parsed
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to parse command'
            })
            
    except Exception as e:
        logger.error(f"Error in parse_voice_command: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/add_event', methods=['POST'])
def add_calendar_event():
    """Add event to calendar"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            })
        
        # Validate required fields
        required_fields = ['title', 'date', 'start_time', 'end_time']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                })
        
        # Add event to calendar
        result = calendar_assistant.add_event(
            data['title'],
            data['date'],
            data['start_time'],
            data['end_time']
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in add_calendar_event: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    logger.info(f"Client connected: {request.sid}")
    emit('connection_status', {'status': 'connected', 'message': 'Welcome to Voice Calendar Assistant'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    logger.info(f"Client disconnected: {request.sid}")

@socketio.on('start_voice_session')
def handle_start_voice_session():
    """Handle voice session start"""
    try:
        greeting = "Hello, I'm your voice calendar assistant. What event would you like to add to your calendar?"
        emit('voice_response', {
            'type': 'greeting',
            'text': greeting,
            'audio_text': greeting
        })
        logger.info("Voice session started")
        
    except Exception as e:
        logger.error(f"Error in handle_start_voice_session: {str(e)}")
        emit('error', {'message': str(e)})

@socketio.on('voice_command')
def handle_voice_command(data):
    """Handle voice command from client"""
    try:
        text = data.get('text', '').strip()
        session_id = data.get('session_id', 'default')
        
        if not text:
            error_msg = "I didn't hear anything. Please try again."
            emit('voice_response', {
                'type': 'error',
                'text': error_msg,
                'audio_text': error_msg,
                'session_id': session_id
            })
            return
        
        logger.info(f"Received voice command: {text}")
        
        # Parse the command
        parsed = voice_parser.parse_voice_command(text)
        
        if not parsed:
            error_msg = "I couldn't understand that. Please try again with a clear command."
            emit('voice_response', {
                'type': 'error',
                'text': error_msg,
                'audio_text': error_msg,
                'session_id': session_id
            })
            return
        
        # Add event to calendar
        result = calendar_assistant.add_event(
            parsed['title'],
            parsed['date'],
            parsed['start_time'],
            parsed['end_time']
        )
        
        # Prepare response
        if result['success']:
            response_text = result['message']
            response_type = 'success'
        else:
            if result.get('conflict'):
                response_text = f"Sorry, there's a scheduling conflict. {result['message']} Please try a different time."
            else:
                response_text = f"Sorry, I couldn't add the event. {result.get('error', 'Please try again.')}"
            response_type = 'error'
        
        emit('voice_response', {
            'type': response_type,
            'text': response_text,
            'audio_text': response_text,
            'session_id': session_id,
            'event_data': parsed if result['success'] else None,
            'success': result['success']
        })
        
        logger.info(f"Voice command processed: success={result['success']}")
        
    except Exception as e:
        logger.error(f"Error in handle_voice_command: {str(e)}")
        emit('error', {'message': str(e)})

@socketio.on('manual_login_request')
def handle_manual_login_request():
    """Handle manual login request"""
    try:
        # Initialize with manual login
        success = calendar_assistant.initialize(manual_login=True)
        
        if success:
            emit('login_response', {
                'success': True,
                'message': 'Browser window opened. Please complete login and return here.'
            })
        else:
            emit('login_response', {
                'success': False,
                'message': 'Failed to open browser for login'
            })
            
    except Exception as e:
        logger.error(f"Error in handle_manual_login_request: {str(e)}")
        emit('login_response', {
            'success': False,
            'message': str(e)
        })

@socketio.on('save_auth_request')
def handle_save_auth_request():
    """Handle save auth request"""
    try:
        success = calendar_assistant.save_auth_state()
        
        if success:
            emit('auth_response', {
                'success': True,
                'message': 'Login state saved successfully'
            })
        else:
            emit('auth_response', {
                'success': False,
                'message': 'Failed to save login state'
            })
            
    except Exception as e:
        logger.error(f"Error in handle_save_auth_request: {str(e)}")
        emit('auth_response', {
            'success': False,
            'message': str(e)
        })

if __name__ == '__main__':
    logger.info("Starting Voice Calendar Assistant...")
    logger.info("Server will be available at http://localhost:5000")
    # 移除 allow_unsafe_werkzeug 参数
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)