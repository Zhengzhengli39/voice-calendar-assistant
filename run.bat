@echo off
echo ========================================
echo 语音驱动日程助手 - 启动脚本
echo ========================================

REM 检查虚拟环境
if not exist "venv\Scripts\activate.bat" (
    echo 错误：未找到虚拟环境
    echo 请先运行: python -m venv venv
    pause
    exit /b 1
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 检查依赖
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo 警告：Flask未安装，正在安装...
    pip install Flask Flask-CORS python-dotenv
)

REM 运行应用
echo 正在启动语音驱动日程助手...
echo 访问地址: http://localhost:5000
echo 按 Ctrl+C 停止应用
echo ========================================
python app.py

pause