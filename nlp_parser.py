"""
自然语言处理模块 - 完整版
解析中文日期时间表达式
"""

import re
from datetime import datetime, timedelta
import jieba

class NLPParser:
    def __init__(self):
        # 初始化jieba
        try:
            jieba.initialize()
            print("✓ jieba分词器初始化成功")
        except Exception as e:
            print(f"✗ jieba初始化失败: {e}")
        
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
            '十八': 18, '十九': 19, '二十': 20,
            '两': 2, '半': 30
        }
        
        print("✓ NLP解析器初始化完成")
    
    def parse_event(self, text):
        """解析事件文本，提取日期、时间和标题"""
        try:
            print(f"解析文本: {text}")
            
            # 提取标题
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
                'parsed_text': text,
                'date_str': time_info['date_str'],
                'time_str': time_info['time_str']
            }
        
        except Exception as e:
            print(f"解析错误: {e}")
            return None
    
    def extract_title(self, text):
        """提取事件标题"""
        # 使用jieba分词
        try:
            words = jieba.lcut(text)
        except:
            words = list(text)
        
        # 移除时间相关词汇
        time_words = ['今天', '明天', '后天', '上午', '下午', '晚上', '点', '时', '到', '至', '开始', '结束']
        filtered_words = [word for word in words if word not in time_words and not word.isdigit()]
        
        # 组合成标题
        title = ''.join(filtered_words)
        
        if not title or len(title) < 2:
            # 提取第一个非时间短语
            for i, word in enumerate(words):
                if word not in time_words and len(word) > 1:
                    start = i
                    for j in range(i+1, len(words)):
                        if words[j] in time_words:
                            title = ''.join(words[start:j])
                            break
                    if title:
                        break
        
        if not title or len(title) < 2:
            title = text[:20] + "..." if len(text) > 20 else text
        
        return title.strip()
    
    def parse_time(self, text):
        """解析时间信息"""
        try:
            now = datetime.now()
            
            # 提取日期偏移
            day_offset = 0
            for keyword, offset in self.time_keywords.items():
                if isinstance(offset, int) and offset in [0, 1, 2, 3, -1, -2]:
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
                r'(\d+)[点时]开始.*(\d+)[点时]结束',  # 10点开始11点结束
                r'从(\d+)[点时]到(\d+)[点时]',  # 从10点到11点
            ]
            
            start_hour = 10  # 默认10点
            end_hour = 11    # 默认11点
            time_found = False
            
            for pattern in time_patterns:
                match = re.search(pattern, text)
                if match:
                    groups = match.groups()
                    if len(groups) >= 2:
                        start_hour = self.parse_hour(groups[0])
                        end_hour = self.parse_hour(groups[1])
                        time_found = True
                    elif len(groups) == 1:
                        start_hour = self.parse_hour(groups[0])
                        end_hour = start_hour + 1
                        time_found = True
                    break
            
            # 如果没有找到明确的时间，尝试其他模式
            if not time_found:
                # 检查"小时"持续时间
                duration_match = re.search(r'(\d+)[个小]?小时', text)
                if duration_match:
                    duration = int(duration_match.group(1))
                    end_hour = start_hour + duration
                    time_found = True
            
            # 处理上午/下午
            if '下午' in text or '晚上' in text or '傍晚' in text:
                if start_hour < 12:
                    start_hour += 12
                if end_hour < 12:
                    end_hour += 12
            elif '上午' in text or '早上' in text or '早晨' in text:
                if start_hour > 12:
                    start_hour -= 12
                if end_hour > 12:
                    end_hour -= 12
            
            # 确保时间有效
            start_hour = min(max(start_hour, 0), 23)
            end_hour = min(max(end_hour, 0), 23)
            
            # 如果结束时间小于开始时间，加12小时
            if end_hour <= start_hour:
                end_hour += 12
            
            # 创建时间对象
            start_time = target_date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
            end_time = target_date.replace(hour=end_hour, minute=0, second=0, microsecond=0)
            
            return {
                'start_time': start_time,
                'end_time': end_time,
                'date_str': target_date.strftime('%Y-%m-%d'),
                'time_str': f"{start_hour:02d}:00-{end_hour:02d}:00",
                'day_offset': day_offset
            }
        
        except Exception as e:
            print(f"时间解析错误: {e}")
            # 返回默认时间
            tomorrow = now + timedelta(days=1)
            return {
                'start_time': tomorrow.replace(hour=10, minute=0, second=0, microsecond=0),
                'end_time': tomorrow.replace(hour=11, minute=0, second=0, microsecond=0),
                'date_str': tomorrow.strftime('%Y-%m-%d'),
                'time_str': "10:00-11:00",
                'day_offset': 1
            }
    
    def parse_hour(self, hour_str):
        """解析小时数"""
        try:
            # 如果是数字
            if isinstance(hour_str, str) and hour_str.isdigit():
                return int(hour_str)
            
            # 如果是中文数字
            if hour_str in self.chinese_numbers:
                return self.chinese_numbers[hour_str]
            
            # 处理中文数字组合
            for chinese, number in self.chinese_numbers.items():
                if chinese in hour_str:
                    return number
            
            # 尝试解析"十二"这样的组合
            if '十' in hour_str:
                parts = hour_str.split('十')
                if len(parts) == 1:  # 比如"十"
                    return 10
                elif len(parts) == 2:
                    if parts[0] and parts[1]:  # 比如"十二"
                        ten = self.chinese_numbers.get(parts[0], 0)
                        one = self.chinese_numbers.get(parts[1], 0)
                        return ten * 10 + one
                    elif parts[0]:  # 比如"十一"
                        return 10 + self.chinese_numbers.get(parts[0], 0)
                    elif parts[1]:  # 比如"二十"
                        return 20
            
            return 10  # 默认值
        
        except:
            return 10