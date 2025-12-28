// 语音录制功能
let mediaRecorder = null;
let audioChunks = [];
let currentSessionId = null;

// 开始录音
async function startRecording() {
    try {
        // 请求麦克风权限
        const stream = await navigator.mediaDevices.getUserMedia({ 
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                sampleRate: 44100
            }
        });
        
        // 创建MediaRecorder
        mediaRecorder = new MediaRecorder(stream, {
            mimeType: 'audio/webm;codecs=opus'
        });
        
        audioChunks = [];
        
        // 收集音频数据
        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };
        
        // 录音结束处理
        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            await sendAudioToServer(audioBlob);
            
            // 停止所有音频轨道
            stream.getTracks().forEach(track => track.stop());
        };
        
        // 开始录音
        mediaRecorder.start();
        log("开始录音...");
        updateRecordingUI(true);
        
    } catch (error) {
        log("录音失败: " + error.message);
        alert("无法访问麦克风，请检查权限设置");
    }
}

// 停止录音
function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        updateRecordingUI(false);
        log("录音结束");
    }
}

// 更新录音UI
function updateRecordingUI(isRecording) {
    const startBtn = document.getElementById('start-btn');
    const status = document.getElementById('voice-status');
    
    if (isRecording) {
        startBtn.innerHTML = '<i class="fas fa-stop-circle"></i> 停止录音';
        startBtn.classList.add('recording');
        status.textContent = '录音中...';
        status.className = 'status-value status-ok';
    } else {
        startBtn.innerHTML = '<i class="fas fa-microphone"></i> 开始语音对话';
        startBtn.classList.remove('recording');
        status.textContent = '待命';
        status.className = 'status-value';
    }
}

// 发送音频到服务器
async function sendAudioToServer(audioBlob) {
    try {
        log("正在处理语音...");
        
        // 转换为base64
        const reader = new FileReader();
        reader.readAsDataURL(audioBlob);
        
        reader.onloadend = async () => {
            const base64Audio = reader.result;
            
            // 发送到后端
            const response = await fetch('/api/process-voice', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: currentSessionId,
                    audio_data: base64Audio
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                log("✓ " + data.message);
                updateStatus('calendar-status', 'ok', '日程创建成功');
                
                // 播放语音回复
                if (data.audio_url) {
                    playAudio(data.audio_url);
                }
                
                // 刷新事件列表
                await loadEvents();
            } else {
                log("✗ " + data.message);
                
                if (data.is_conflict) {
                    log("检测到时间冲突，请说出新的时间安排");
                }
                
                // 播放错误提示
                if (data.audio_url) {
                    playAudio(data.audio_url);
                }
            }
        };
        
    } catch (error) {
        log("发送音频失败: " + error.message);
    }
}

// 播放音频
function playAudio(audioUrl) {
    if (audioUrl) {
        const audio = new Audio(audioUrl);
        audio.play().catch(e => console.warn('音频播放失败:', e));
    }
}

// 加载事件列表
async function loadEvents() {
    try {
        const response = await fetch('/api/get-events');
        if (response.ok) {
            const data = await response.json();
            if (data.success && data.events.length > 0) {
                updateStatus('calendar-status', 'ok', `${data.count}个日程`);
                log(`已加载 ${data.count} 个日程`);
            }
        }
    } catch (error) {
        console.log("加载事件失败:", error);
    }
}

// 更新状态函数
function updateStatus(elementId, status, message) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = message;
        element.className = 'status-value status-' + status;
    }
}

// 主按钮点击事件
document.getElementById('start-btn').addEventListener('click', async function() {
    const btn = this;
    
    if (btn.classList.contains('recording')) {
        // 停止录音
        stopRecording();
    } else {
        // 开始新的会话
        log("开始新的语音会话...");
        
        // 检查系统状态
        try {
            const statusResponse = await fetch('/api/system-status');
            const statusData = await statusResponse.json();
            
            if (!statusData.success) {
                alert("系统状态异常，请刷新页面重试");
                return;
            }
        } catch (error) {
            alert("检查系统状态失败");
            return;
        }
        
        // 开始语音会话
        try {
            const response = await fetch('/api/start-voice-session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: `session_${Date.now()}`
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                currentSessionId = data.session_id;
                log("✓ " + data.message);
                
                // 播放开场白
                if (data.audio_url) {
                    playAudio(data.audio_url);
                }
                
                // 2秒后开始录音
                setTimeout(() => {
                    startRecording();
                }, 2000);
                
            } else {
                log("✗ 启动会话失败: " + (data.error || data.message));
                alert("启动语音会话失败，请重试");
            }
        } catch (error) {
            log("启动会话失败: " + error.message);
            alert("网络错误，请检查连接");
        }
    }
});

// 连接Google日历按钮
document.getElementById('login-btn').addEventListener('click', async function() {
    log("连接Google日历...");
    
    try {
        const response = await fetch('/api/trigger-login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            log("✓ " + data.message);
            
            if (data.login_url) {
                // 在新窗口打开登录页面
                window.open(data.login_url, '_blank');
                log("请在新窗口中完成登录，完成后返回此页面");
            }
        } else {
            log("✗ 连接失败: " + data.error);
        }
    } catch (error) {
        log("连接失败: " + error.message);
    }
});

// 检查日历状态
async function checkCalendar() {
    try {
        log("正在检查日历连接...");
        const response = await fetch('/api/check-login');
        if (response.ok) {
            const data = await response.json();
            if (data.success) {
                if (data.is_logged_in) {
                    updateStatus('calendar-status', 'ok', '已连接');
                    log("✓ 日历连接正常");
                } else {
                    updateStatus('calendar-status', 'error', '未连接');
                    log("⚠ 日历未连接，请点击'连接Google日历'按钮");
                }
            }
        }
    } catch (error) {
        updateStatus('calendar-status', 'error', '检查失败');
        log("✗ 日历状态检查失败");
    }
}

// 页面加载时初始化
window.addEventListener('load', async () => {
    log("系统启动完成");
    log("开始初始化检查...");
    
    // 检查所有服务
    await checkBackend();
    await checkVoice();
    checkBrowser();
    await checkCalendar();
    
    log("初始化检查完成！");
    log("请点击'开始语音对话'按钮添加日程");
    
    // 加载已有事件
    await loadEvents();
});

// 从之前代码中保留的其他函数
function log(message) {
    const console = document.getElementById('console');
    if (console) {
        const line = document.createElement('div');
        line.className = 'console-line';
        line.textContent = '> ' + message;
        console.appendChild(line);
        console.scrollTop = console.scrollHeight;
    }
}

async function checkBackend() {
    try {
        log('正在检查后端服务...');
        const response = await fetch('/api/health');
        if (response.ok) {
            const data = await response.json();
            updateStatus('backend-status', 'ok', '运行正常');
            log('✓ 后端服务正常: ' + data.message);
            return true;
        } else {
            updateStatus('backend-status', 'error', '服务异常');
            log('✗ 后端服务异常');
            return false;
        }
    } catch (error) {
        updateStatus('backend-status', 'error', '连接失败');
        log('✗ 无法连接到后端: ' + error.message);
        return false;
    }
}

async function checkVoice() {
    try {
        log('正在检查语音功能...');
        const response = await fetch('/api/test-voice');
        if (response.ok) {
            const data = await response.json();
            updateStatus('voice-status', data.status === 'ok' ? 'ok' : 'warning', data.status === 'ok' ? '可用' : '模拟模式');
            log('✓ 语音功能: ' + data.message);
            return true;
        }
    } catch (error) {
        updateStatus('voice-status', 'warning', '模拟模式');
        log('⚠ 语音功能检查失败，使用模拟模式');
        return false;
    }
}

function checkBrowser() {
    log('正在检查浏览器支持...');
    const hasMediaDevices = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
    const hasWebkitSpeechRecognition = 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;
    
    if (hasMediaDevices && hasWebkitSpeechRecognition) {
        updateStatus('browser-status', 'ok', '支持语音');
        log('✓ 浏览器支持语音功能');
    } else if (hasMediaDevices) {
        updateStatus('browser-status', 'warning', '部分支持');
        log('⚠ 浏览器部分支持语音功能');
    } else {
        updateStatus('browser-status', 'error', '不支持');
        log('✗ 浏览器不支持语音功能');
    }
    
    return hasMediaDevices;
}