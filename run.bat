@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ================================================
echo   粤路慧养 v2.0
echo   公路养护决策系统
echo ================================================
echo.
echo 启动中...
echo.
python main.py
if errorlevel 1 (
    echo.
    echo 启动失败！请检查Python环境和依赖。
    echo 安装依赖：pip install -r requirements.txt
    echo.
    pause
)
