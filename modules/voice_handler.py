"""
Voice handling module for speech recognition and synthesis
"""

import speech_recognition as sr
import pyttsx3
import base64
import io
import tempfile
import wave
import logging
import threading

logger = logging.getLogger(__name__)

class VoiceHandler:
    def __init__(self):
        """Initialize voice handler"""
        self.recognizer = sr.Recognizer()
        self.engine = None
        self._init_tts_engine()
        
    def _init_tts_engine(self):
        """Initialize text-to-speech engine"""
        try:
            self.engine = pyttsx3.init()
            # Configure voice properties
            voices = self.engine.getProperty('voices')
            if voices:
                self.engine.setProperty('voice', voices[0].id)  # First available voice
            self.engine.setProperty('rate', 150)  # Speed of speech
            self.engine.setProperty('volume', 0.9)  # Volume (0.0 to 1.0)
            logger.info("TTS engine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize TTS engine: {str(e)}")
            self.engine = None
    
    def speech_to_text(self, audio_data_base64):
        """
        Convert speech to text
        
        Args:
            audio_data_base64: Base64 encoded audio data
            
        Returns:
            str: Recognized text or None if recognition fails
        """
        try:
            # Decode base64 audio
            audio_bytes = base64.b64decode(audio_data_base64)
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_bytes)
                temp_file_path = temp_file.name
            
            # Use SpeechRecognition to process audio
            with sr.AudioFile(temp_file_path) as source:
                # Adjust for ambient noise
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.record(source)
            
            # Recognize speech using Google Web Speech API
            text = self.recognizer.recognize_google(audio)
            
            # Clean up temporary file
            import os
            os.unlink(temp_file_path)
            
            logger.info(f"Speech recognized: {text}")
            return text
            
        except sr.UnknownValueError:
            logger.warning("Speech recognition could not understand audio")
            return None
        except sr.RequestError as e:
            logger.error(f"Speech recognition service error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error in speech-to-text: {str(e)}")
            return None
    
    def text_to_speech(self, text):
        """
        Convert text to speech
        
        Args:
            text: Text to convert to speech
            
        Returns:
            str: Base64 encoded audio data
        """
        try:
            if not self.engine:
                self._init_tts_engine()
                if not self.engine:
                    return None
            
            # Create temporary file for audio output
            import tempfile
            import os
            
            temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_file_path = temp_file.name
            temp_file.close()
            
            # Save speech to file
            self.engine.save_to_file(text, temp_file_path)
            self.engine.runAndWait()
            
            # Read file and encode to base64
            with open(temp_file_path, 'rb') as f:
                audio_data = f.read()
            
            # Clean up
            os.unlink(temp_file_path)
            
            # Encode to base64
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            return audio_base64
            
        except Exception as e:
            logger.error(f"Error in text-to-speech: {str(e)}")
            return None
    
    def text_to_speech_stream(self, text):
        """
        Convert text to speech and return as byte stream
        
        Args:
            text: Text to convert
            
        Returns:
            bytes: Audio data in WAV format
        """
        try:
            if not self.engine:
                self._init_tts_engine()
            
            # Use pyttsx3's in-memory output (requires workaround)
            # For simplicity, we'll use the file-based approach
            audio_base64 = self.text_to_speech(text)
            if audio_base64:
                return base64.b64decode(audio_base64)
            return None
            
        except Exception as e:
            logger.error(f"Error in TTS streaming: {str(e)}")
            return None