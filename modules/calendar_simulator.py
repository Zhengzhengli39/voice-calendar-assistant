"""
日历模拟模块 - 当无法连接真实Google日历时使用
"""

from datetime import datetime
import json
import os

class CalendarSimulator:
    def __init__(self):
        self.events_file = 'auth/simulated_events.json'
        self.events = self.load_events()
        print("日历模拟模式启用")
    
    def load_events(self):
        """加载模拟事件"""
        if os.path.exists(self.events_file):
            try:
                with open(self.events_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return []
    
    def save_events(self):
        """保存模拟事件"""
        os.makedirs('auth', exist_ok=True)
        with open(self.events_file, 'w', encoding='utf-8') as f:
            json.dump(self.events, f, ensure_ascii=False, indent=2)
    
    def check_time_slot_conflict(self, start_time, end_time):
        """检查时间冲突（模拟）"""
        # 简单模拟：随机决定是否有冲突
        import random
        return random.random() < 0.2  # 20%的几率有冲突
    
    def create_calendar_event(self, title, start_time, end_time, description=''):
        """创建日历事件（模拟）"""
        try:
            event = {
                'id': f"sim_{len(self.events) + 1}",
                'title': title,
                'start_time': start_time.isoformat() if isinstance(start_time, datetime) else start_time,
                'end_time': end_time.isoformat() if isinstance(end_time, datetime) else end_time,
                'description': description,
                'created_at': datetime.now().isoformat()
            }
            
            self.events.append(event)
            self.save_events()
            
            print(f"[日历模拟] 创建事件: {title}")
            print(f"          时间: {start_time} 到 {end_time}")
            
            return True
        
        except Exception as e:
            print(f"创建模拟事件失败: {e}")
            return False
    
    def get_events(self):
        """获取所有事件"""
        return self.events
    
    def is_logged_in(self):
        """模拟登录状态"""
        return True