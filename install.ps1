Write-Host "========================================" -ForegroundColor Cyan
Write-Host "语音驱动日程助手 - 安装脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 检查Python版本
Write-Host "检查Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Python not found"
    }
    Write-Host "检测到: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "错误：未找到Python，请先安装Python 3.8或更高版本" -ForegroundColor Red
    Write-Host "下载地址: https://www.python.org/downloads/" -ForegroundColor Yellow
    Read-Host "按Enter键退出"
    exit
}

# 检查是否在项目目录中
if (-not (Test-Path "requirements.txt")) {
    Write-Host "警告：未找到requirements.txt文件" -ForegroundColor Yellow
    Write-Host "请确保在项目根目录中运行此脚本" -ForegroundColor Yellow
    $confirm = Read-Host "是否继续？(y/n)"
    if ($confirm -ne 'y') {
        exit
    }
}

# 创建虚拟环境（如果不存在）
if (-not (Test-Path "venv")) {
    Write-Host "创建虚拟环境..." -ForegroundColor Yellow
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "创建虚拟环境失败" -ForegroundColor Red
        exit
    }
}

# 激活虚拟环境
Write-Host "激活虚拟环境..." -ForegroundColor Yellow
try {
    .\venv\Scripts\Activate.ps1
} catch {
    Write-Host "激活虚拟环境失败，尝试使用其他方法..." -ForegroundColor Yellow
    # 尝试使用CMD方式
    cmd /c "venv\Scripts\activate.bat && echo Virtual environment activated"
}

# 检查是否已激活
if (-not $env:VIRTUAL_ENV) {
    Write-Host "警告：虚拟环境可能未正确激活" -ForegroundColor Yellow
    Write-Host "请手动运行: .\venv\Scripts\Activate" -ForegroundColor Yellow
}

# 升级pip
Write-Host "升级pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# 安装依赖（使用国内镜像加速）
Write-Host "安装Python依赖..." -ForegroundColor Yellow
$dependencies = @(
    "Flask==2.3.3",
    "Flask-CORS==4.0.0",
    "python-dotenv==1.0.0",
    "playwright==1.39.0",
    "SpeechRecognition==3.10.0",
    "pyttsx3==2.90",
    "dateparser==1.1.8",
    "jieba==0.42.1",
    "pytz==2023.3"
)

foreach ($dependency in $dependencies) {
    Write-Host "正在安装: $dependency" -ForegroundColor Gray
    pip install $dependency -i https://pypi.tuna.tsinghua.edu.cn/simple
    if ($LASTEXITCODE -ne 0) {
        Write-Host "安装失败: $dependency" -ForegroundColor Red
    }
}

# 安装Playwright浏览器
Write-Host "安装Playwright浏览器..." -ForegroundColor Yellow
python -m playwright install chromium

# 创建必要的目录
Write-Host "创建项目目录结构..." -ForegroundColor Yellow
$directories = @("static", "templates", "modules", "auth")
foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "创建目录: $dir" -ForegroundColor Gray
    }
}

# 创建.env文件
if (-not (Test-Path ".env")) {
    Write-Host "创建.env配置文件..." -ForegroundColor Yellow
    "SECRET_KEY=dev-secret-key-123-change-this-in-production`nFLASK_ENV=development`nDEBUG=True" | Out-File -FilePath .env -Encoding UTF8
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "安装完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "`n接下来步骤：" -ForegroundColor Yellow
Write-Host "1. 激活虚拟环境: .\venv\Scripts\Activate" -ForegroundColor White
Write-Host "2. 运行应用: python app.py" -ForegroundColor White
Write-Host "3. 访问: http://localhost:5000" -ForegroundColor White

Write-Host "`n如果激活失败，可以尝试：" -ForegroundColor Yellow
Write-Host "  - 以管理员身份运行PowerShell" -ForegroundColor White
Write-Host "  - 运行: Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser" -ForegroundColor White
Write-Host "  - 然后再次运行激活命令" -ForegroundColor White

Read-Host "`n按Enter键退出"