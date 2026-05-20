@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ================================================
echo  粤路公司公路养护需求预测系统
echo ================================================
echo.
start "" "dist\公路路况分析系统\公路路况分析系统.exe"
if errorlevel 1 (
    echo.
    echo 启动失败，请检查exe是否存在
    pause
)
