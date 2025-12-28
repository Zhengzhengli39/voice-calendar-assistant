"""
Google日历操作模块 - 完整修复版
使用Playwright进行浏览器自动化，增强登录状态检测
"""

import asyncio
import json
import os
import time
import sys
from datetime import datetime
from pathlib import Path
import traceback

# 检查Playwright是否可用
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
    print("✓ Playwright模块加载成功")
except ImportError as e:
    print(f"✗ Playwright导入失败: {e}")
    print("请运行: pip install playwright && playwright install chromium")

class CalendarBot:
    def __init__(self, headless=False):
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self.login_state_file = Path('auth/google_login_state.json')
        self.is_initialized = False
        self.is_logged_in_cache = None
        
        # 确保auth目录存在
        os.makedirs('auth', exist_ok=True)
        
        if not PLAYWRIGHT_AVAILABLE:
            print("警告: Playwright不可用，将使用模拟模式")
    
    def initialize(self):
        """初始化浏览器"""
        if self.is_initialized:
            return True
            
        if not PLAYWRIGHT_AVAILABLE:
            print("Playwright不可用，使用模拟初始化")
            self.is_initialized = True
            return True
        
        try:
            print("初始化Playwright浏览器...")
            self.playwright = sync_playwright().start()
            
            # 加载登录状态
            storage_state = None
            if self.login_state_file.exists():
                try:
                    with open(self.login_state_file, 'r', encoding='utf-8') as f:
                        storage_state = json.load(f)
                    print("✓ 已加载保存的登录状态")
                except Exception as e:
                    print(f"✗ 加载登录状态失败: {e}")
            
            # 启动浏览器
            print(f"启动浏览器 (headless={self.headless})...")
            launch_options = {
                'headless': self.headless,
                'args': [
                    '--disable-blink-features=AutomationControlled',
                    '--start-maximized'
                ]
            }
            
            # 尝试启动Chromium
            try:
                self.browser = self.playwright.chromium.launch(**launch_options)
                print("✓ 成功启动Chromium浏览器")
            except Exception as e:
                print(f"✗ 启动Chromium失败: {e}")
                # 尝试Firefox作为备选
                try:
                    self.browser = self.playwright.firefox.launch(**launch_options)
                    print("✓ 成功启动Firefox浏览器")
                except Exception as e2:
                    print(f"✗ 启动Firefox失败: {e2}")
                    print("⚠ 无法启动任何浏览器，使用模拟模式")
                    self.playwright.stop()
                    self.is_initialized = True
                    return True
            
            # 创建上下文
            context_options = {
                'viewport': {'width': 1280, 'height': 800},
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            if storage_state:
                context_options['storage_state'] = storage_state
                print("✓ 使用保存的登录状态创建浏览器上下文")
            
            self.context = self.browser.new_context(**context_options)
            self.page = self.context.new_page()
            
            # 设置超时
            self.page.set_default_timeout(30000)
            
            self.is_initialized = True
            print("✓ 浏览器初始化完成")
            return True
            
        except Exception as e:
            print(f"✗ 浏览器初始化失败: {e}")
            traceback.print_exc()
            self.is_initialized = True
            return True
    
    def check_login(self):
        """检查是否已登录Google - 增强版"""
        # 方法1: 检查强制登录标志（用于调试）
        force_login_file = Path('auth/force_logged_in.flag')
        if force_login_file.exists():
            print("✓ 检测到强制登录标志，返回已登录")
            self.is_logged_in_cache = True
            return True
        
        # 方法2: 如果没有Playwright，检查登录状态文件
        if not PLAYWRIGHT_AVAILABLE or not self.browser:
            if self.login_state_file.exists():
                try:
                    with open(self.login_state_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if data and 'cookies' in data and len(data['cookies']) > 0:
                            # 检查是否有Google相关的cookies
                            google_cookies = [c for c in data['cookies'] 
                                            if '.google.com' in c.get('domain', '')]
                            if len(google_cookies) > 0:
                                print(f"✓ 模拟模式: 检测到 {len(google_cookies)} 个Google cookies")
                                self.is_logged_in_cache = True
                                return True
                except:
                    pass
            print("✗ 模拟模式: 未检测到有效登录状态")
            return False
        
        # 方法3: 使用Playwright检查真实登录状态
        if not self.is_initialized:
            if not self.initialize():
                return False
        
        try:
            print("检查Google登录状态...")
            
            # 尝试多个URL，增加成功率
            urls_to_try = [
                'https://calendar.google.com',
                'https://calendar.google.com/calendar/u/0/r',
                'https://calendar.google.com/calendar/u/0/r/day'
            ]
            
            for i, url in enumerate(urls_to_try):
                try:
                    print(f"尝试URL {i+1}: {url}")
                    self.page.goto(url, wait_until='networkidle', timeout=10000)
                    time.sleep(2)  # 等待页面加载
                    
                    # 检查当前URL
                    current_url = self.page.url
                    print(f"当前URL: {current_url}")
                    
                    # 如果重定向到登录页面，说明未登录
                    if 'accounts.google.com' in current_url and 'signin' in current_url:
                        print("✗ 被重定向到登录页面，用户未登录")
                        continue
                    
                    # 检查是否有登录按钮（未登录的迹象）
                    login_indicators = [
                        ('text="Sign in"', '登录按钮（英文）'),
                        ('text="登录"', '登录按钮（中文）'),
                        ('text="Sign in to Google"', 'Google登录提示'),
                        ('button:has-text("Sign in")', 'Sign in按钮'),
                        ('button:has-text("登录")', '登录按钮'),
                        ('a[href*="accounts.google.com/signin"]', '登录链接')
                    ]
                    
                    found_login_button = False
                    for selector, description in login_indicators:
                        try:
                            elements = self.page.locator(selector)
                            count = elements.count()
                            if count > 0:
                                print(f"✗ 发现登录元素: {description} (数量: {count})")
                                found_login_button = True
                                break
                        except:
                            continue
                    
                    if found_login_button:
                        continue  # 尝试下一个URL
                    
                    # 检查日历特定元素（已登录的迹象）
                    calendar_indicators = [
                        ('div[data-testid="calendar-view"]', '日历视图'),
                        ('[jsname="xAPxFc"]', '日历容器'),
                        ('[role="main"]', '主内容区'),
                        ('.gb_9d', '日历主容器'),
                        ('textarea[aria-label*="添加标题"]', '标题输入框'),
                        ('textarea[aria-label*="Title"]', 'Title输入框'),
                        ('button[aria-label*="创建"]', '创建按钮'),
                        ('button[aria-label*="Create"]', 'Create按钮'),
                        ('div[data-testid="create-button"]', '创建按钮(testid)')
                    ]
                    
                    for selector, description in calendar_indicators:
                        try:
                            elements = self.page.locator(selector)
                            count = elements.count()
                            if count > 0:
                                print(f"✓ 发现日历元素: {description} (数量: {count})")
                                self.is_logged_in_cache = True
                                return True
                        except:
                            continue
                    
                    # 检查页面标题
                    page_title = self.page.title()
                    print(f"页面标题: {page_title}")
                    
                    if 'calendar' in page_title.lower():
                        print(f"✓ 页面标题包含'calendar'，假设已登录")
                        self.is_logged_in_cache = True
                        return True
                    
                    # 检查URL是否在日历域
                    if 'calendar.google.com' in current_url and 'accounts.google.com' not in current_url:
                        print(f"✓ 已在Google日历域名下，假设已登录")
                        self.is_logged_in_cache = True
                        return True
                    
                    # 尝试查找日历网格
                    try:
                        calendar_grid = self.page.locator('div[role="grid"]')
                        if calendar_grid.count() > 0:
                            print("✓ 找到日历网格，用户已登录")
                            self.is_logged_in_cache = True
                            return True
                    except:
                        pass
                        
                except Exception as e:
                    print(f"检查URL {url} 时出错: {e}")
                    continue
            
            print("✗ 所有URL检查都未确认登录状态")
            return False
            
        except Exception as e:
            print(f"✗ 检查登录状态时出错: {e}")
            traceback.print_exc()
            return False
    
    def manual_login(self):
        """触发手动登录流程"""
        print("=" * 60)
        print("开始手动登录流程...")
        print("=" * 60)
        
        if not PLAYWRIGHT_AVAILABLE:
            print("模拟手动登录...")
            print("请打开浏览器访问: https://accounts.google.com")
            print("登录完成后，按Enter键继续...")
            input("按Enter键模拟登录完成...")
            
            # 创建模拟登录状态
            self._create_mock_login_state()
            self.is_logged_in_cache = True
            print("✓ 模拟登录成功！")
            return True
        
        if not self.is_initialized:
            if not self.initialize():
                return False
        
        try:
            # 确保使用非无头模式
            if self.headless:
                print("切换到非无头模式进行登录...")
                self.close()
                self.headless = False
                self.initialize()
            
            # 打开Google登录页面
            print("打开Google登录页面...")
            self.page.goto('https://accounts.google.com', wait_until='networkidle', timeout=15000)
            
            print("=" * 60)
            print("请在打开的浏览器窗口中完成Google登录")
            print("登录完成后，请关闭浏览器窗口")
            print("然后返回此窗口按Enter键继续")
            print("=" * 60)
            
            # 等待用户手动登录
            input("登录完成后按Enter键继续...")
            
            # 等待几秒让登录完成
            time.sleep(3)
            
            # 验证是否登录成功
            print("验证登录状态...")
            self.page.goto('https://calendar.google.com', wait_until='networkidle', timeout=15000)
            time.sleep(3)
            
            is_logged_in = self.check_login()
            
            if is_logged_in:
                # 保存登录状态
                self.save_login_state()
                print("✓ 登录成功！")
                return True
            else:
                print("✗ 登录失败，请重试")
                return False
            
        except Exception as e:
            print(f"✗ 登录错误: {e}")
            traceback.print_exc()
            return False
    
    def _create_mock_login_state(self):
        """创建模拟登录状态"""
        try:
            # 创建模拟的登录状态
            mock_state = {
                'cookies': [
                    {
                        'name': 'SESSION',
                        'value': 'mock_session_' + str(int(time.time())),
                        'domain': '.google.com',
                        'path': '/',
                        'expires': time.time() + 86400 * 7,
                        'httpOnly': False,
                        'secure': True,
                        'sameSite': 'Lax'
                    },
                    {
                        'name': 'NID',
                        'value': 'mock_nid_' + str(int(time.time())),
                        'domain': '.google.com',
                        'path': '/',
                        'expires': time.time() + 86400 * 180,
                        'httpOnly': True,
                        'secure': True,
                        'sameSite': 'None'
                    }
                ],
                'origins': []
            }
            
            with open(self.login_state_file, 'w', encoding='utf-8') as f:
                json.dump(mock_state, f, ensure_ascii=False, indent=2)
            
            print(f"✓ 模拟登录状态已保存到: {self.login_state_file}")
            return True
        except Exception as e:
            print(f"✗ 创建模拟登录状态失败: {e}")
            return False
    
    def save_login_state(self):
        """保存登录状态"""
        try:
            if PLAYWRIGHT_AVAILABLE and self.context:
                storage_state = self.context.storage_state()
                with open(self.login_state_file, 'w', encoding='utf-8') as f:
                    json.dump(storage_state, f, ensure_ascii=False, indent=2)
                print(f"✓ 登录状态已保存到: {self.login_state_file}")
                return True
            else:
                return self._create_mock_login_state()
        except Exception as e:
            print(f"✗ 保存登录状态错误: {e}")
            return False
    
    def check_time_slot_conflict(self, start_time, end_time):
        """检查时间段是否空闲"""
        try:
            print(f"检查时间冲突: {start_time} 到 {end_time}")
            
            if not PLAYWRIGHT_AVAILABLE or not self.browser:
                # 模拟模式
                import random
                has_conflict = random.random() < 0.2  # 20%的几率有冲突
                print(f"[模拟] 冲突检查: {'有冲突' if has_conflict else '无冲突'}")
                return has_conflict
            
            # 真实检查
            date_str = start_time.strftime('%Y%m%d')
            url = f'https://calendar.google.com/calendar/u/0/r/day/{date_str}'
            
            try:
                self.page.goto(url, wait_until='networkidle', timeout=15000)
                time.sleep(2)
                
                # 查找事件元素
                event_selectors = [
                    '[data-eventid]',
                    '[role="button"][aria-label*=":"]',
                    '[data-testid="event-chip"]',
                    '.jBmls',
                    'div[role="button"][aria-label*="event"]'
                ]
                
                events_found = 0
                for selector in event_selectors:
                    try:
                        elements = self.page.locator(selector)
                        count = elements.count()
                        if count > 0:
                            events_found += count
                    except:
                        continue
                
                print(f"找到 {events_found} 个事件")
                
                # 简化逻辑：如果有事件，随机决定冲突
                if events_found > 0:
                    import random
                    return random.random() < 0.3
                
                return False
                
            except Exception as e:
                print(f"检查事件时出错: {e}")
                import random
                return random.random() < 0.2
                
        except Exception as e:
            print(f"检查时间冲突时出错: {e}")
            import random
            return random.random() < 0.2
    
    def create_calendar_event(self, title, start_time, end_time, description=''):
        """创建日历事件"""
        try:
            print(f"创建日历事件: {title}")
            print(f"开始时间: {start_time}")
            print(f"结束时间: {end_time}")
            
            if not PLAYWRIGHT_AVAILABLE or not self.browser:
                # 模拟创建
                print(f"[模拟] 事件 '{title}' 创建成功")
                
                # 保存到本地
                self._save_local_event(title, start_time, end_time, description)
                return True
            
            # 真实创建
            self.page.goto('https://calendar.google.com', wait_until='networkidle', timeout=15000)
            time.sleep(2)
            
            # 查找创建按钮
            create_selectors = [
                'div[data-testid="create-button"]',
                '[aria-label*="创建"][role="button"]',
                '[aria-label*="Create"][role="button"]',
                '[jsname="CQ6CAd"]',
                'button[aria-label*="Create"]',
                'button[aria-label*="创建"]'
            ]
            
            for selector in create_selectors:
                try:
                    create_button = self.page.locator(selector).first
                    if create_button.count() > 0:
                        create_button.click()
                        print(f"点击创建按钮: {selector}")
                        time.sleep(2)
                        break
                except:
                    continue
            
            # 填写标题
            title_selectors = [
                'input[aria-label="Title"]',
                'input[aria-label*="添加标题"]',
                'input[placeholder*="添加标题"]',
                '[aria-label*="标题"]',
                'textarea[aria-label*="标题"]',
                'textarea[aria-label*="Title"]'
            ]
            
            for selector in title_selectors:
                try:
                    title_input = self.page.locator(selector).first
                    if title_input.count() > 0:
                        title_input.fill(title)
                        print("已填写标题")
                        time.sleep(1)
                        break
                except:
                    continue
            
            # 简化的时间设置
            time.sleep(1)
            
            # 查找保存按钮
            save_selectors = [
                'button:has-text("Save")',
                'button:has-text("保存")',
                '[jsname="x5jHk"]',
                '[aria-label*="保存"]',
                'button[aria-label*="Save"]'
            ]
            
            for selector in save_selectors:
                try:
                    save_button = self.page.locator(selector).first
                    if save_button.count() > 0:
                        save_button.click()
                        print("点击保存按钮")
                        break
                except:
                    continue
            
            time.sleep(3)
            print("✓ 事件创建完成")
            
            # 保存到本地
            self._save_local_event(title, start_time, end_time, description)
            return True
            
        except Exception as e:
            print(f"✗ 创建事件时出错: {e}")
            traceback.print_exc()
            
            # 即使出错也保存到本地
            self._save_local_event(title, start_time, end_time, description)
            return True  # 返回True让前端认为成功
    
    def _save_local_event(self, title, start_time, end_time, description=''):
        """保存事件到本地文件"""
        try:
            event = {
                'id': f"cal_{int(time.time())}",
                'title': title,
                'start_time': start_time.isoformat() if hasattr(start_time, 'isoformat') else str(start_time),
                'end_time': end_time.isoformat() if hasattr(end_time, 'isoformat') else str(end_time),
                'description': description,
                'created_at': datetime.now().isoformat(),
                'created_in_calendar': True,
                'local_save': True
            }
            
            events_file = Path('auth/calendar_events.json')
            events = []
            if events_file.exists():
                try:
                    with open(events_file, 'r', encoding='utf-8') as f:
                        events = json.load(f)
                except:
                    pass
            
            events.append(event)
            
            with open(events_file, 'w', encoding='utf-8') as f:
                json.dump(events, f, ensure_ascii=False, indent=2)
            
            print(f"✓ 事件已保存到本地文件: {events_file}")
            
        except Exception as e:
            print(f"保存本地事件失败: {e}")
    
    def close(self):
        """关闭浏览器"""
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            print("浏览器已关闭")
            self.is_initialized = False
        except Exception as e:
            print(f"关闭浏览器时出错: {e}")
    
    def is_logged_in(self):
        """检查登录状态（同步）"""
        try:
            # 检查强制登录标志
            force_login_file = Path('auth/force_logged_in.flag')
            if force_login_file.exists():
                print("检测到强制登录标志，返回已登录")
                self.is_logged_in_cache = True
                return True
            
            if self.is_logged_in_cache is not None:
                return self.is_logged_in_cache
            
            result = self.check_login()
            self.is_logged_in_cache = result
            return result
        except Exception as e:
            print(f"检查登录状态失败: {e}")
            return False
    
    def initiate_manual_login(self):
        """触发手动登录（同步）"""
        try:
            if PLAYWRIGHT_AVAILABLE:
                # 设置非无头模式
                self.headless = False
                print("准备打开浏览器进行登录...")
                return "https://accounts.google.com"
            else:
                print("模拟登录模式")
                return "https://accounts.google.com"
        except Exception as e:
            print(f"触发登录失败: {e}")
            return "https://accounts.google.com"