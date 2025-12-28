import speech_recognition as sr
import pyttsx3
import tempfile
import os
from io import BytesIO
import base64

class VoiceProcessor:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.tts_engine = pyttsx3.init()
        
        # 配置TTS引擎
        self.tts_engine.setProperty('rate', 150)  # 语速
        self.tts_engine.setProperty('volume', 0.9)  # 音量
        
        # 尝试选择中文语音
        voices = self.tts_engine.getProperty('voices')
        for voice in voices:
            if 'chinese' in voice.name.lower() or 'zh' in voice.id.lower():
                self.tts_engine.setProperty('voice', voice.id)
                break
    
    def speech_to_text(self, audio_data=None, audio_file=None):
        """将语音转换为文本"""
        try:
            if audio_data:
                # 处理base64音频数据
                if isinstance(audio_data, str) and audio_data.startswith('data:audio'):
                    # 提取base64数据
                    audio_data = audio_data.split(',')[1]
                
                audio_bytes = base64.b64decode(audio_data)
                
                # 创建临时文件
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                    tmp_file.write(audio_bytes)
                    tmp_file_path = tmp_file.name
                
                audio_source = tmp_file_path
            elif audio_file:
                audio_source = audio_file
            else:
                raise ValueError("需要提供音频数据或文件")
            
            # 使用麦克风或文件
            with sr.AudioFile(audio_source) as source:
                audio = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio, language='zh-CN')
                
                # 清理临时文件
                if audio_data:
                    os.unlink(tmp_file_path)
                
                return text
        
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            raise Exception(f"语音识别服务错误: {e}")
        except Exception as e:
            raise Exception(f"语音处理错误: {e}")
    
    def text_to_speech(self, text):
        """将文本转换为语音（返回base64编码的音频）"""
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_file:
                tmp_file_path = tmp_file.name
            
            # 保存为音频文件
            self.tts_engine.save_to_file(text, tmp_file_path)
            self.tts_engine.runAndWait()
            
            # 读取音频文件并转换为base64
            with open(tmp_file_path, 'rb') as audio_file:
                audio_bytes = audio_file.read()
                audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            
            # 清理临时文件
            os.unlink(tmp_file_path)
            
            return f"data:audio/mp3;base64,{audio_base64}"
        
        except Exception as e:
            print(f"TTS错误: {e}")
            # 返回静默音频作为fallback
            return None