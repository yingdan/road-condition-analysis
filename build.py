"""
PyInstaller打包脚本
运行: python build.py
生成位置: dist/公路路况分析系统/
"""
import subprocess
import sys
import os

def build():
    # 确保pyinstaller已安装
    subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller', '-q'], check=True)

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name=公路路况分析系统',
        '--windowed',              # 无控制台窗口
        '--onedir',                # 单目录模式（比onefile启动快）
        '--clean',
        '--noconfirm',
        f'--add-data=src{os.pathsep}src',      # 包含src目录
        f'--add-data=config.json{os.pathsep}.',  # 包含配置文件
        '--hidden-import=pandas',
        '--hidden-import=openpyxl',
        '--hidden-import=matplotlib',
        '--hidden-import=matplotlib.backends.backend_agg',
        '--hidden-import=numpy',
        '--hidden-import=docx',
        '--hidden-import=openai',
        '--collect-all=matplotlib',
        '--collect-all=docx',
        'main.py'
    ]

    print('开始打包...')
    result = subprocess.run(cmd, capture_output=False)

    if result.returncode == 0:
        print('\n✅ 打包成功！')
        print(f'程序位于: dist/公路路况分析系统/')
        print('将整个目录复制给用户即可使用，无需安装Python。')
    else:
        print('\n❌ 打包失败，请检查错误信息。')

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    build()
