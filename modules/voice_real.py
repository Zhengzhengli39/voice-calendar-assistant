"""
真实语音处理模块
"""

import speech_recognition as sr
import pyttsx3
import tempfile
import os
import base64

class VoiceReal:
    def __init__(self):
        try:
            self.recognizer = sr.Recognizer()
            self.tts_engine = pyttsx3.init()
            
            # 配置TTS
            self.tts_engine.setProperty('rate', 150)
            self.tts_engine.setProperty('volume', 0.9)
            
            # 尝试设置中文语音
            voices = self.tts_engine.getProperty('voices')
            for voice in voices:
                if 'chinese' in voice.name.lower() or 'zh' in voice.id.lower():
                    self.tts_engine.setProperty('voice', voice.id)
                    break
            
            self.available = True
            print("真实语音模块初始化成功")
        except Exception as e:
            print(f"语音模块初始化失败: {e}")
            self.available = False
    
    def speech_to_text(self, audio_data=None, audio_file=None):
        """语音转文本"""
        try:
            if audio_data and isinstance(audio_data, str):
                # 处理base64音频数据
                if audio_data.startswith('data:audio'):
                    audio_data = audio_data.split(',')[1]
                
                audio_bytes = base64.b64decode(audio_data)
                
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                    f.write(audio_bytes)
                    temp_path = f.name
                
                with sr.AudioFile(temp_path) as source:
                    audio = self.recognizer.record(source)
                    text = self.recognizer.recognize_google(audio, language='zh-CN')
                
                os.unlink(temp_path)
                return text
            
            elif audio_file:
                with sr.AudioFile(audio_file) as source:
                    audio = self.recognizer.record(source)
                    text = self.recognizer.recognize_google(audio, language='zh-CN')
                return text
            
            else:
                raise ValueError("需要音频数据或文件")
        
        except sr.UnknownValueError:
            return "无法识别语音"
        except sr.RequestError as e:
            return f"语音识别服务错误: {e}"
        except Exception as e:
            return f"语音处理错误: {e}"
    
    def text_to_speech(self, text):
        """文本转语音"""
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                temp_path = f.name
            
            # 保存为音频文件
            self.tts_engine.save_to_file(text, temp_path)
            self.tts_engine.runAndWait()
            
            # 读取并转换为base64
            with open(temp_path, 'rb') as audio_file:
                audio_bytes = audio_file.read()
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            
            os.unlink(temp_path)
            return f"data:audio/mp3;base64,{audio_base64}"
        
        except Exception as e:
            print(f"TTS错误: {e}")
            return None
    
    def is_available(self):
        return self.available