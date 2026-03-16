"""
入口文件：启动 Flask 服务器，用 PyWebView 打开界面
打包命令见 build.bat
"""
import sys
import time
import threading
from pathlib import Path

# Windows 打包后 stdout 默认 GBK，强制改为 UTF-8 避免特殊字符报错
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass


def get_bundle_dir() -> Path:
    """PyInstaller 打包后返回临时解压目录，开发时返回源码目录"""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent


if __name__ == '__main__':
    bundle_dir = get_bundle_dir()
    static_folder = str(bundle_dir / 'ui' / 'dist')

    # 确保 get_token.py / autodl_keeper.py 可被 import
    sys.path.insert(0, str(bundle_dir))

    from app import create_app
    flask_app = create_app(static_folder)

    port = 7890

    def start_flask():
        flask_app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)

    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()
    time.sleep(2.0)  # 等 Flask 启动好

    import webview
    webview.create_window(
        'AutoDL 释放时间守护',
        f'http://127.0.0.1:{port}',
        width=960,
        height=700,
        resizable=True,
        min_size=(640, 480),
    )
    webview.start()
