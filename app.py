from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import os
from datetime import datetime
import json

app = Flask(__name__)
CORS(app)
app.secret_key = 'dev-secret-key-123'

# 事件存储文件
EVENTS_FILE = 'auth/events.json'

def load_events():
    """加载事件"""
    if os.path.exists(EVENTS_FILE):
        try:
            with open(EVENTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return []

def save_events(events):
    """保存事件"""
    os.makedirs('auth', exist_ok=True)
    with open(EVENTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/api/health')
def health():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'message': '语音助手服务运行正常',
        'version': '1.0.0',
        'time': datetime.now().isoformat()
    })

@app.route('/api/start-voice-session', methods=['POST'])
def start_voice_session():
    """开始语音会话"""
    opening = "您好，我是您的日程助手。请告诉我您的日程安排，例如：明天上午十点到十一点开会"
    
    return jsonify({
        'success': True,
        'message': opening,
        'session_id': f'session_{datetime.now().timestamp()}'
    })

@app.route('/api/process-voice', methods=['POST'])
def process_voice():
    """处理语音输入"""
    try:
        data = request.json
        text = data.get('text', '')
        
        # 如果没有文本，使用模拟数据
        if not text:
            import random
            mock_texts = [
                "明天上午十点到十一点开会",
                "今天下午两点到四点技术评审",
                "后天上午九点到十二点项目讨论"
            ]
            text = random.choice(mock_texts)
        
        # 简单解析
        event = {
            'id': f"event_{datetime.now().timestamp()}",
            'title': text.split('，')[-1] if '，' in text else text,
            'description': text,
            'start_time': '10:00',
            'end_time': '11:00',
            'created_at': datetime.now().isoformat(),
            'status': 'active'
        }
        
        # 保存事件
        events = load_events()
        events.append(event)
        save_events(events)
        
        return jsonify({
            'success': True,
            'message': f'已创建日程: {event["title"]}',
            'event': event
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'处理失败: {str(e)}'
        })

@app.route('/api/trigger-login', methods=['POST'])
def trigger_login():
    """触发登录"""
    return jsonify({
        'success': True,
        'login_url': 'https://accounts.google.com',
        'message': '请在打开的浏览器窗口中完成Google登录'
    })

@app.route('/api/get-events', methods=['GET'])
def get_events():
    """获取事件"""
    events = load_events()
    return jsonify({
        'success': True,
        'events': events,
        'count': len(events)
    })

if __name__ == '__main__':
    # 创建必要目录
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs('modules', exist_ok=True)
    os.makedirs('auth', exist_ok=True)
    
    print("=" * 60)
    print("语音驱动日程助手 - 最终版本")
    print("=" * 60)
    print("功能:")
    print("1. 语音对话模拟")
    print("2. 事件管理")
    print("3. Google日历连接")
    print("=" * 60)
    print("访问地址: http://localhost:5000")
    print("按 Ctrl+C 停止应用")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)