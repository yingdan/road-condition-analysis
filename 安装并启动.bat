@echo off
chcp 65001 >nul
echo ================================================
echo  公路路况分析系统 - 依赖安装脚本
echo ================================================
echo.
echo 正在安装所需Python包...
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
echo.
echo ================================================
echo  安装完成！按任意键启动程序...
echo ================================================
pause
start "" "dist\公路路况分析系统\公路路况分析系统.exe"
