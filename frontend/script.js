/**
 * Frontend JavaScript for Voice Calendar Assistant
 */

class VoiceCalendarApp {
    constructor() {
        this.socket = null;
        this.isRecording = false;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.sessionId = this.generateSessionId();
        this.requiresLogin = false;
        
        this.initializeElements();
        this.initializeSocket();
        this.initializeEventListeners();
        this.updateStatus('app', 'Ready', 'status-active');
    }
    
    generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
    
    initializeElements() {
        // Buttons
        this.initBtn = document.getElementById('init-btn');
        this.loginBtn = document.getElementById('login-btn');
        this.voiceBtn = document.getElementById('voice-btn');
        this.clearBtn = document.getElementById('clear-btn');
        this.confirmLoginBtn = document.getElementById('confirm-login');
        this.cancelLoginBtn = document.getElementById('cancel-login');
        
        // Status indicators
        this.appStatus = document.getElementById('app-status');
        this.authStatus = document.getElementById('auth-status');
        this.voiceStatus = document.getElementById('voice-status');
        this.voiceIndicator = document.getElementById('voice-indicator');
        
        // Display elements
        this.responseText = document.getElementById('response-text');
        this.responseAudio = document.getElementById('response-audio');
        this.audioPlayer = document.getElementById('audio-player');
        this.eventLog = document.getElementById('event-log');
        
        // Modal
        this.loginModal = document.getElementById('login-modal');
    }
    
    initializeSocket() {
        // Connect to WebSocket server
        this.socket = io();
        
        this.socket.on('connect', () => {
            this.logMessage('[System]', 'Connected to server');
            this.updateStatus('app', 'Connected', 'status-active');
        });
        
        this.socket.on('disconnect', () => {
            this.logMessage('[System]', 'Disconnected from server');
            this.updateStatus('app', 'Disconnected', 'status-error');
        });
        
        this.socket.on('connect_error', (error) => {
            this.logMessage('[System]', `Connection error: ${error.message}`);
            this.updateStatus('app', 'Connection Error', 'status-error');
        });
        
        this.socket.on('voice_response', (data) => {
            this.handleVoiceResponse(data);
        });
        
        this.socket.on('login_status', (data) => {
            this.handleLoginStatus(data);
        });
        
        this.socket.on('error', (data) => {
            this.showError(data.message);
        });
    }
    
    initializeEventListeners() {
        // Initialize button
        this.initBtn.addEventListener('click', () => {
            this.initializeAssistant();
        });
        
        // Manual login button
        this.loginBtn.addEventListener('click', () => {
            this.showLoginModal();
        });
        
        // Voice button
        this.voiceBtn.addEventListener('click', () => {
            if (!this.isRecording) {
                this.startVoiceRecording();
            } else {
                this.stopVoiceRecording();
            }
        });
        
        // Clear button
        this.clearBtn.addEventListener('click', () => {
            this.clearSession();
        });
        
        // Modal buttons
        this.confirmLoginBtn.addEventListener('click', () => {
            this.performManualLogin();
            this.hideLoginModal();
        });
        
        this.cancelLoginBtn.addEventListener('click', () => {
            this.hideLoginModal();
        });
        
        // Initialize audio context for recording
        this.initializeAudio();
    }
    
    async initializeAudio() {
        try {
            // Check for microphone permission
            const stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    sampleRate: 44100
                }
            });
            
            // Create MediaRecorder
            this.mediaRecorder = new MediaRecorder(stream, {
                mimeType: 'audio/webm;codecs=opus'
            });
            
            // Handle data available
            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };
            
            // Handle recording stop
            this.mediaRecorder.onstop = () => {
                this.processAudioRecording();
            };
            
            this.updateStatus('voice', 'Microphone ready', 'status-active');
            
        } catch (error) {
            console.error('Error initializing audio:', error);
            this.updateStatus('voice', 'Microphone access denied', 'status-error');
            this.showError('Microphone access is required for voice input. Please allow microphone access.');
        }
    }
    
    async initializeAssistant() {
        this.showLoading(this.initBtn, 'Initializing...');
        
        try {
            const response = await fetch('/api/initialize', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.logMessage('[System]', 'Assistant initialized successfully');
                
                if (data.requires_login) {
                    this.requiresLogin = true;
                    this.loginBtn.disabled = false;
                    this.updateStatus('auth', 'Login required', 'status-warning');
                    this.showInfo('Please click "Manual Login" to authenticate with Google Calendar');
                } else {
                    this.requiresLogin = false;
                    this.voiceBtn.disabled = false;
                    this.updateStatus('auth', 'Authenticated', 'status-active');
                    this.showInfo('Assistant ready. Click "Start Voice Session" to begin.');
                }
                
                this.updateStatus('app', 'Initialized', 'status-active');
            } else {
                throw new Error(data.error || 'Initialization failed');
            }
            
        } catch (error) {
            this.showError(`Initialization failed: ${error.message}`);
            this.updateStatus('app', 'Initialization failed', 'status-error');
        } finally {
            this.hideLoading(this.initBtn, '<i class="fas fa-play"></i> Initialize Assistant');
        }
    }
    
    startVoiceRecording() {
        if (!this.mediaRecorder) {
            this.showError('Microphone not available. Please refresh the page.');
            return;
        }
        
        // Check if authentication is required
        if (this.requiresLogin) {
            this.showError('Please login first using the Manual Login button.');
            return;
        }
        
        this.isRecording = true;
        this.audioChunks = [];
        
        // Update UI
        this.voiceBtn.innerHTML = '<i class="fas fa-stop"></i> Stop Recording';
        this.voiceIndicator.classList.add('recording');
        this.updateStatus('voice', 'Recording...', 'status-active');
        
        // Start recording
        this.mediaRecorder.start(100); // Collect data every 100ms
        
        this.logMessage('[User]', 'Started voice recording');
        
        // Auto-stop after 10 seconds
        setTimeout(() => {
            if (this.isRecording) {
                this.stopVoiceRecording();
            }
        }, 10000);
    }
    
    stopVoiceRecording() {
        if (!this.isRecording || !this.mediaRecorder) {
            return;
        }
        
        this.isRecording = false;
        this.mediaRecorder.stop();
        
        // Update UI
        this.voiceBtn.innerHTML = '<i class="fas fa-microphone"></i> Start Voice Session';
        this.voiceIndicator.classList.remove('recording');
        this.updateStatus('voice', 'Processing...', 'status-warning');
    }
    
    async processAudioRecording() {
        try {
            // Create audio blob
            const audioBlob = new Blob(this.audioChunks, { 
                type: 'audio/webm;codecs=opus' 
            });
            
            // Convert to base64
            const reader = new FileReader();
            reader.readAsDataURL(audioBlob);
            
            reader.onloadend = () => {
                const base64Audio = reader.result.split(',')[1]; // Remove data URL prefix
                
                // Send to server
                this.socket.emit('voice_input', {
                    audio_data: base64Audio,
                    session_id: this.sessionId
                });
                
                this.logMessage('[User]', 'Voice sent for processing');
            };
            
        } catch (error) {
            console.error('Error processing audio:', error);
            this.showError('Error processing audio recording');
            this.updateStatus('voice', 'Processing failed', 'status-error');
        }
    }
    
    handleVoiceResponse(data) {
        // Update response text
        this.responseText.innerHTML = `<p class="assistant-response">${data.text}</p>`;
        
        // Play audio response if available
        if (data.audio) {
            const audioSrc = `data:audio/wav;base64,${data.audio}`;
            this.responseAudio.src = audioSrc;
            this.audioPlayer.style.display = 'block';
            
            // Auto-play audio
            this.responseAudio.play().catch(e => {
                console.log('Auto-play prevented:', e);
                this.showInfo('Click the play button to hear the response');
            });
        }
        
        // Update status
        if (data.event_added) {
            this.logMessage('[Assistant]', `Event added: ${data.text}`);
            this.updateStatus('voice', 'Event added successfully', 'status-active');
        } else {
            this.logMessage('[Assistant]', data.text);
            this.updateStatus('voice', 'Response sent', 'status-active');
        }
        
        // Handle initialization requirement
        if (data.requires_init) {
            this.showInfo('Please initialize the assistant first.');
        }
    }
    
    showLoginModal() {
        this.loginModal.style.display = 'flex';
    }
    
    hideLoginModal() {
        this.loginModal.style.display = 'none';
    }
    
    performManualLogin() {
        this.showLoading(this.loginBtn, 'Opening browser...');
        
        // Notify server to start manual login
        this.socket.emit('manual_login', {
            session_id: this.sessionId
        });
        
        this.logMessage('[System]', 'Manual login initiated. Please complete login in the browser window.');
    }
    
    handleLoginStatus(data) {
        if (data.success) {
            this.requiresLogin = false;
            this.loginBtn.disabled = true;
            this.voiceBtn.disabled = false;
            
            this.updateStatus('auth', 'Authenticated', 'status-active');
            this.showInfo('Login successful! You can now start voice sessions.');
            
            this.logMessage('[System]', 'Google Calendar authentication completed');
        } else {
            this.showError(`Login failed: ${data.error}`);
            this.updateStatus('auth', 'Authentication failed', 'status-error');
        }
        
        this.hideLoading(this.loginBtn, '<i class="fas fa-sign-in-alt"></i> Manual Login');
    }
    
    clearSession() {
        // Clear response and log
        this.responseText.innerHTML = '<p class="placeholder">Your assistant\'s responses will appear here...</p>';
        this.eventLog.innerHTML = '<div class="log-entry"><span class="log-time">[System]</span><span class="log-message">Session cleared. Ready for new session.</span></div>';
        this.audioPlayer.style.display = 'none';
        
        // Reset session
        this.sessionId = this.generateSessionId();
        
        this.logMessage('[System]', 'Session cleared');
        this.showInfo('Session cleared. Ready for new voice sessions.');
    }
    
    updateStatus(element, text, statusClass = '') {
        const statusMap = {
            'app': this.appStatus,
            'auth': this.authStatus,
            'voice': this.voiceStatus
        };
        
        const elementRef = statusMap[element];
        if (!elementRef) return;
        
        const icon = elementRef.querySelector('.status-icon');
        const textElement = elementRef.querySelector('.status-text');
        
        textElement.textContent = text;
        
        // Update icon color based on status class
        if (statusClass === 'status-active') {
            icon.style.color = '#2ed573';
        } else if (statusClass === 'status-warning') {
            icon.style.color = '#ffa502';
        } else if (statusClass === 'status-error') {
            icon.style.color = '#ff4757';
        }
    }
    
    logMessage(source, message) {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.className = 'log-entry';
        logEntry.innerHTML = `
            <span class="log-time">[${timestamp}] ${source}</span>
            <span class="log-message">${message}</span>
        `;
        
        this.eventLog.prepend(logEntry);
        
        // Limit log entries
        const entries = this.eventLog.querySelectorAll('.log-entry');
        if (entries.length > 50) {
            entries[entries.length - 1].remove();
        }
    }
    
    showLoading(button, text) {
        button.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${text}`;
        button.disabled = true;
    }
    
    hideLoading(button, originalText) {
        button.innerHTML = originalText;
        button.disabled = false;
    }
    
    showInfo(message) {
        this.logMessage('[Info]', message);
        
        // Show temporary notification
        const notification = document.createElement('div');
        notification.className = 'notification';
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #3742fa;
            color: white;
            padding: 15px 20px;
            border-radius: 8px;
            z-index: 1000;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
    
    showError(message) {
        this.logMessage('[Error]', message);
        
        // Show error notification
        const notification = document.createElement('div');
        notification.className = 'notification error';
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #ff4757;
            color: white;
            padding: 15px 20px;
            border-radius: 8px;
            z-index: 1000;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }
}

// Initialize application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new VoiceCalendarApp();
});