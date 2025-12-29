# Voice Calendar Assistant

A voice-driven web application that automatically adds events to Google Calendar using browser automation with Playwright.

## Features

- **Voice Interface**: Natural language voice commands for scheduling events
- **Google Calendar Integration**: Automatically adds events without using the official API
- **Authentication Management**: Saves login state to avoid repeated manual logins
- **Conflict Detection**: Checks for scheduling conflicts before adding events
- **Web Interface**: Modern, responsive web interface with real-time feedback

## Tech Stack

### Backend
- **Python 3.8+**
- **Flask**: Web framework
- **Flask-SocketIO**: Real-time WebSocket communication
- **Playwright**: Browser automation
- **SpeechRecognition**: Voice-to-text conversion
- **pyttsx3**: Text-to-speech synthesis

### Frontend
- **HTML5/CSS3**: Responsive interface
- **JavaScript**: Client-side logic
- **Web Speech API**: Browser-based voice recording
- **Socket.IO Client**: Real-time communication

## Installation

### 1. Prerequisites
```bash
# Install Python 3.8 or higher
python --version

# Install Playwright browsers
playwright install chromium

### 2. Clone and Setup
```bash
git clone <repository-url>
cd voice-calendar-assistant

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

### 3. Environment Setup
```bash
Create a .env file in the project root:
SECRET_KEY=your-secret-key-here
DEBUG=True

## Usage
### 1. Start the Application
```bash
python app.py
The application will start on http://localhost:5000

### 2. First-Time Setup
#### 1. Open http://localhost:5000 in your browser

#### 2. Click "Initialize Assistant"

#### 3. If prompted, click "Manual Login"

#### 4. A browser window will open - complete Google login (including MFA if enabled)

#### 5. Once logged in, close the browser window

### 3. Adding Events via Voice

#### 1. Click "Start Voice Session"

#### 2. Speak your event command (see examples below)

#### 3. The assistant will confirm and add the event to your calendar

## Voice Command Examples

"Schedule a meeting with John tomorrow at 2 PM for 1 hour"

"Add team meeting on Friday at 10 AM to 11 AM"

"Create event: Doctor appointment next Monday at 3 PM"

"Set up a call with Sarah tomorrow morning at 9 for 30 minutes"

## Project Structure

voice-calendar-assistant/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── .env                  # Environment variables
├── frontend/             # Web interface
│   ├── index.html
│   ├── script.js
│   └── style.css
├── modules/              # Core functionality modules
│   ├── voice_handler.py  # Speech recognition & synthesis
│   ├── nlp_parser.py     # Natural language processing
│   ├── calendar_bot.py   # Playwright automation
│   └── auth_manager.py   # Authentication state management
└── storage/              # Persistent data storage
    └── auth_state.json   # Saved browser authentication

## Authentication Management
The application uses Playwright's storage_state feature to persist login sessions:

### 1. First Run: Browser opens for manual login

### 2. Login State Saved: Authentication cookies stored in storage/auth_state.json

### 3. Subsequent Runs: Uses saved state to avoid re-login

### 4. State Expiry: If login expires, prompts for manual login again

## Known Limitations

### 1. Google Security: Google may require re-authentication periodically

### 2. Voice Recognition: Accuracy depends on microphone quality and clarity of speech

### 3. Time Zones: Currently uses UTC timezone - may need adjustment

### 4. Calendar Layout: Google Calendar UI changes may break Playwright selectors

## Troubleshooting

### Common Issues

#### 1."Microphone access denied"

          Grant microphone permissions in your browser

          Check browser settings for site permissions

#### 2."Playwright browser not found"
          ```bash
          playwright install chromium

#### 3."Authentication state not saving"

          Ensure storage/ directory exists and is writable

          Check browser permissions for saving cookies

#### 4."Cannot find Google Calendar elements"

         Google Calendar UI may have changed

         Check console logs for selector errors

         May need to update Playwright selectors in calendar_bot.py

### Debugging

       Check app.log for detailed error information

       Enable debug mode in .env: DEBUG=True

       Browser automation runs in non-headless mode by default for debugging

### Security Notes

      No Google API Keys Required: Uses browser automation instead of official API

      Local Storage: Authentication state stored locally only

      No Cloud Services: All processing happens locally

     Temporary Files: Audio files are created temporarily and deleted

## Development

### Running Tests
```bash
# Install test dependencies
pip install pytest playwright pytest-playwright

# Run tests
pytest tests/

### Code Style
```bash
# Install formatting tools
pip install black flake8

# Format code
black .

# Check linting
flake8 .

### Adding Features

Fork the repository

Create a feature branch

Make changes with tests

Submit pull request

## License

This project is for educational purposes. Use responsibly and in accordance with Google's Terms of Service.

##  Disclaimer

This tool automates browser interactions with Google Calendar. Use at your own risk. The developers are not responsible for any issues caused by this software, including but not limited to duplicate events, missed appointments, or Google account restrictions.
