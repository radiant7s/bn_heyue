@echo off
chcp 65001 >nul
echo ============================================================
echo 币安合约异动检测系统 - 优化版启动器
echo ============================================================
echo.

echo [%time%] 检查Python环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python未找到，请先安装Python
    pause
    exit /b 1
)

echo [%time%] 检查网络连接...
python -c "import requests; requests.get('https://fapi.binance.com/fapi/v1/ping', timeout=5)" >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️  币安API连接异常，建议检查网络
    echo 继续启动可能遇到连接问题...
    echo.
)

echo [%time%] 设置环境变量...
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

echo [%time%] 启动系统...
echo.
echo 🚀 正在启动币安合约异动检测系统...
echo 📊 WebSocket数据收集器
echo 🔍 异动检测器  
echo 📈 数据更新器
echo 🌐 API服务器 (http://localhost:5000)
echo.
echo 按 Ctrl+C 停止系统
echo ============================================================
echo.

python main.py

echo.
echo ============================================================
echo 系统已停止
echo ============================================================
pause