"""
自然语言处理模块 - 解析日期时间
"""

import re
from datetime import datetime, timedelta
import jieba

class NLPParser:
    def __init__(self):
        # 初始化jieba
        jieba.initialize()
        
        # 时间关键词映射
        self.time_keywords = {
            '今天': 0, '今日': 0,
            '明天': 1, '明日': 1,
            '后天': 2, '后日': 2,
            '大后天': 3,
            '昨天': -1, '昨日': -1,
            '前天': -2, '前日': -2,
            '上午': 'AM', '早上': 'AM', '早晨': 'AM', '早': 'AM',
            '下午': 'PM', '中午': 'PM', '午后': 'PM',
            '晚上': 'PM', '傍晚': 'PM', '晚': 'PM',
            '点': '时', '点钟': '时', '时': '时'
        }
        
        # 中文数字映射
        self.chinese_numbers = {
            '零': 0, '〇': 0, '一': 1, '二': 2, '三': 3, '四': 4,
            '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
            '十': 10, '十一': 11, '十二': 12, '十三': 13,
            '十四': 14, '十五': 15, '十六': 16, '十七': 17,
            '十八': 18, '十九': 19, '二十': 20, '二十': 20,
            '两': 2, '半': 30
        }
    
    def parse_event(self, text):
        """解析事件文本，提取日期、时间和标题"""
        try:
            print(f"解析文本: {text}")
            
            # 提取标题（去除时间描述）
            title = self.extract_title(text)
            
            # 解析时间
            time_info = self.parse_time(text)
            
            if not time_info:
                return None
            
            return {
                'title': title,
                'start_time': time_info['start_time'],
                'end_time': time_info['end_time'],
                'description': f"语音添加: {text}",
                'parsed_text': text
            }
        
        except Exception as e:
            print(f"解析错误: {e}")
            return None
    
    def extract_title(self, text):
        """提取事件标题"""
        # 移除常见的时间前缀
        patterns = [
            r'明天',
            r'今天',
            r'后天',
            r'上午',
            r'下午',
            r'晚上',
            r'\d+点',
            r'\d+时',
            r'[一二三四五六七八九十]+点',
            r'[一二三四五六七八九十]+时'
        ]
        
        cleaned_text = text
        for pattern in patterns:
            cleaned_text = re.sub(pattern, '', cleaned_text)
        
        # 移除常见动词
        verbs = ['安排', '添加', '创建', '设置', '预定', '预约', '开会', '会议']
        for verb in verbs:
            cleaned_text = cleaned_text.replace(verb, '')
        
        # 清理标点和空白
        cleaned_text = re.sub(r'[，。；、]', ' ', cleaned_text).strip()
        
        if not cleaned_text:
            return "未命名事件"
        
        return cleaned_text
    
    def parse_time(self, text):
        """解析时间信息"""
        try:
            now = datetime.now()
            
            # 提取日期偏移
            day_offset = 0
            for keyword, offset in self.time_keywords.items():
                if offset in [0, 1, 2, 3, -1, -2]:  # 日期偏移
                    if keyword in text:
                        day_offset = offset
                        break
            
            target_date = now + timedelta(days=day_offset)
            
            # 提取时间
            time_patterns = [
                r'(\d+)[点时]到(\d+)[点时]',  # 10点到11点
                r'(\d+)[点时]至(\d+)[点时]',  # 10点至11点
                r'(\d+)[点时]-(\d+)[点时]',   # 10点-11点
                r'([一二三四五六七八九十]+)[点时]到([一二三四五六七八九十]+)[点时]',  # 十点到十一点
                r'上午(\d+)[点时]',  # 上午10点
                r'下午(\d+)[点时]',  # 下午2点
            ]
            
            start_hour = 10  # 默认10点
            end_hour = 11    # 默认11点
            
            for pattern in time_patterns:
                match = re.search(pattern, text)
                if match:
                    groups = match.groups()
                    if len(groups) >= 2:
                        # 解析开始和结束时间
                        start_hour = self.parse_hour(groups[0])
                        end_hour = self.parse_hour(groups[1])
                    elif len(groups) == 1:
                        start_hour = self.parse_hour(groups[0])
                        end_hour = start_hour + 1  # 默认1小时
                    break
            
            # 处理上午/下午
            if '下午' in text or '晚上' in text or '傍晚' in text:
                if start_hour < 12:
                    start_hour += 12
                if end_hour < 12:
                    end_hour += 12
            
            # 处理"小时"持续时间
            duration_match = re.search(r'(\d+)[个小]?小时', text)
            if duration_match:
                duration = int(duration_match.group(1))
                end_hour = start_hour + duration
            
            # 创建时间对象
            start_time = target_date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
            end_time = target_date.replace(hour=end_hour, minute=0, second=0, microsecond=0)
            
            return {
                'start_time': start_time,
                'end_time': end_time,
                'date_str': target_date.strftime('%Y-%m-%d'),
                'time_str': f"{start_hour:02d}:00-{end_hour:02d}:00"
            }
        
        except Exception as e:
            print(f"时间解析错误: {e}")
            # 返回默认时间（明天10-11点）
            tomorrow = now + timedelta(days=1)
            return {
                'start_time': tomorrow.replace(hour=10, minute=0, second=0, microsecond=0),
                'end_time': tomorrow.replace(hour=11, minute=0, second=0, microsecond=0),
                'date_str': tomorrow.strftime('%Y-%m-%d'),
                'time_str': "10:00-11:00"
            }
    
    def parse_hour(self, hour_str):
        """解析小时数"""
        try:
            # 如果是数字
            if hour_str.isdigit():
                return int(hour_str)
            
            # 如果是中文数字
            if hour_str in self.chinese_numbers:
                return self.chinese_numbers[hour_str]
            
            # 处理"十一点"这样的格式
            for chinese, number in self.chinese_numbers.items():
                if chinese in hour_str:
                    # 简单处理，更复杂的需要更全面的解析
                    return number
            
            # 默认返回10
            return 10
        
        except:
            return 10  # 默认值