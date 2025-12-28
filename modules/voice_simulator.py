"""
语音模拟模块 - 当真实语音库不可用时使用
"""

class VoiceSimulator:
    def __init__(self):
        self.available = False
        print("语音模拟模式启用")
    
    def speech_to_text(self, audio_data=None, use_mock=True):
        """模拟语音转文本"""
        if use_mock:
            # 返回模拟的文本
            mock_responses = [
                "明天上午十点到十一点开会",
                "今天下午两点到四点技术评审",
                "后天上午九点到十二点项目讨论",
                "明天下午三点到五点半客户拜访"
            ]
            import random
            return random.choice(mock_responses)
        
        # 真实语音识别（暂不实现）
        return None
    
    def text_to_speech(self, text):
        """模拟文本转语音"""
        print(f"[TTS模拟] 播放语音: {text}")
        # 返回模拟音频URL
        return None
    
    def is_available(self):
        """检查语音功能是否可用"""
        return self.available