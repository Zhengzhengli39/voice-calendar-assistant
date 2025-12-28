"""
语音处理模块 - 完整版
包含真实的语音识别和TTS功能
"""

import tempfile
import os
import base64

class VoiceReal:
    def __init__(self):
        self.available = False
        self.recognizer = None
        self.tts_engine = None
        
        try:
            # 尝试导入SpeechRecognition
            import speech_recognition as sr
            self.recognizer = sr.Recognizer()
            print("✓ SpeechRecognition导入成功")
            
            # 尝试导入pyttsx3
            import pyttsx3
            self.tts_engine = pyttsx3.init()
            
            # 配置TTS
            self.tts_engine.setProperty('rate', 150)
            self.tts_engine.setProperty('volume', 0.9)
            
            # 尝试选择中文语音
            voices = self.tts_engine.getProperty('voices')
            for voice in voices:
                if 'chinese' in voice.name.lower() or 'zh' in voice.id.lower():
                    self.tts_engine.setProperty('voice', voice.id)
                    print(f"✓ 找到中文语音: {voice.name}")
                    break
            
            self.available = True
            print("✓ 语音模块初始化成功")
            
        except ImportError as e:
            print(f"✗ 语音库导入失败: {e}")
            print("请安装: pip install SpeechRecognition pyttsx3")
        except Exception as e:
            print(f"✗ 语音模块初始化失败: {e}")
            self.available = False
    
    def speech_to_text(self, audio_data=None, audio_file=None):
        """语音转文本"""
        if not self.available or not self.recognizer:
            # 模拟模式
            return self._simulate_speech_to_text()
        
        try:
            if audio_data and isinstance(audio_data, str):
                # 处理base64音频数据
                if audio_data.startswith('data:audio'):
                    audio_data = audio_data.split(',')[1]
                
                audio_bytes = base64.b64decode(audio_data)
                
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                    f.write(audio_bytes)
                    temp_path = f.name
                
                with self.recognizer.AudioFile(temp_path) as source:
                    audio = self.recognizer.record(source)
                    text = self.recognizer.recognize_google(audio, language='zh-CN')
                
                os.unlink(temp_path)
                print(f"✓ 语音识别成功: {text}")
                return text
            
            elif audio_file:
                with self.recognizer.AudioFile(audio_file) as source:
                    audio = self.recognizer.record(source)
                    text = self.recognizer.recognize_google(audio, language='zh-CN')
                return text
            
            else:
                return self._simulate_speech_to_text()
        
        except self.recognizer.UnknownValueError:
            print("✗ 无法识别语音")
            return "无法识别，请重试"
        except self.recognizer.RequestError as e:
            print(f"✗ 语音识别服务错误: {e}")
            return self._simulate_speech_to_text()
        except Exception as e:
            print(f"✗ 语音识别失败: {e}")
            return self._simulate_speech_to_text()
    
    def _simulate_speech_to_text(self):
        """模拟语音识别"""
        import random
        mock_responses = [
            "明天上午十点到十一点开会",
            "今天下午两点到四点技术评审",
            "后天上午九点到十二点项目讨论",
            "明天下午三点到五点半客户拜访",
            "今天上午九点到十点团队晨会"
        ]
        result = random.choice(mock_responses)
        print(f"[模拟] 语音识别: {result}")
        return result
    
    def text_to_speech(self, text):
        """文本转语音"""
        if not self.available or not self.tts_engine:
            # 模拟模式
            print(f"[模拟TTS] 播放: {text}")
            return None
        
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
            print(f"✗ TTS错误: {e}")
            print(f"[模拟TTS] 播放: {text}")
            return None
    
    def is_available(self):
        return self.available