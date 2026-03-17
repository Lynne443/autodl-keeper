"""
入口文件：启动 Flask 服务器，用 PyWebView 打开界面
关闭窗口时最小化到系统托盘，后台继续运行
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


def _create_icon_image():
    """用 Pillow 生成一个简单的蓝色圆形图标"""
    from PIL import Image, ImageDraw
    size = 64
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, size - 4, size - 4], fill='#2563eb')
    draw.text((size // 2 - 8, size // 2 - 8), 'A', fill='white')
    return img


def _run_tray(window):
    """创建系统托盘图标"""
    import pystray

    def on_show(icon, item):
        window.show()

    def on_quit(icon, item):
        icon.stop()
        window.destroy()

    icon = pystray.Icon(
        'AutoDL Keeper',
        _create_icon_image(),
        'AutoDL 释放时间守护',
        menu=pystray.Menu(
            pystray.MenuItem('打开窗口', on_show, default=True),
            pystray.MenuItem('退出', on_quit),
        ),
    )
    icon.run()


def _run_tray_with_quit(window, quit_fn):
    """创建系统托盘图标，使用外部传入的退出回调"""
    import pystray

    def on_show(icon, item):
        window.show()

    icon = pystray.Icon(
        'AutoDL Keeper',
        _create_icon_image(),
        'AutoDL 释放时间守护',
        menu=pystray.Menu(
            pystray.MenuItem('打开窗口', on_show, default=True),
            pystray.MenuItem('退出', lambda icon, item: quit_fn(icon, item)),
        ),
    )
    icon.run()


if __name__ == '__main__':
    bundle_dir = get_bundle_dir()
    static_folder = str(bundle_dir / 'ui' / 'dist')

    # 确保 get_token.py / autodl_keeper.py 可被 import
    sys.path.insert(0, str(bundle_dir))

    from app import create_app
    flask_app = create_app(static_folder)

    port = 17890

    def start_flask():
        flask_app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)

    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()
    time.sleep(2.0)  # 等 Flask 启动好

    import webview

    _window = None
    _tray_thread = None

    # JS: 自定义两按钮弹框，通过 pywebview JS-Python bridge 回调
    _CLOSE_DIALOG_JS = '''
(function() {
    if (document.getElementById('_close_overlay')) return;
    const overlay = document.createElement('div');
    overlay.id = '_close_overlay';
    Object.assign(overlay.style, {
        position:'fixed', top:0, left:0, width:'100%', height:'100%',
        background:'rgba(0,0,0,0.5)', display:'flex',
        alignItems:'center', justifyContent:'center', zIndex:99999
    });
    const box = document.createElement('div');
    Object.assign(box.style, {
        background:'#1e293b', borderRadius:'12px', padding:'28px 32px',
        color:'#f1f5f9', fontFamily:'system-ui, sans-serif', minWidth:'320px',
        boxShadow:'0 8px 30px rgba(0,0,0,0.6)', textAlign:'center'
    });
    box.innerHTML = '<div style="font-size:16px;font-weight:600;margin-bottom:20px">选择关闭方式</div>';
    const mkBtn = (text, val, bg) => {
        const b = document.createElement('button');
        b.textContent = text;
        Object.assign(b.style, {
            background:bg, color:'#fff', border:'none', borderRadius:'8px',
            padding:'10px 28px', fontSize:'14px', fontWeight:600,
            cursor:'pointer', margin:'0 8px'
        });
        b.onclick = () => {
            document.body.removeChild(overlay);
            fetch('/api/_close_action', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action:val})});
        };
        return b;
    };
    box.appendChild(mkBtn('最小化到托盘', 'minimize', '#2563eb'));
    box.appendChild(mkBtn('退出程序', 'quit', '#475569'));
    overlay.appendChild(box);
    document.body.appendChild(overlay);
})()
'''

    _closing_action = [None]

    def on_closing():
        """始终阻止关闭，改为弹出自定义对话框"""
        if _closing_action[0] == 'quit':
            return True
        # 在新线程中注入 JS 弹框，避免死锁
        threading.Thread(target=lambda: _window.evaluate_js(_CLOSE_DIALOG_JS), daemon=True).start()
        return False

    def on_tray_quit(icon, item):
        _closing_action[0] = 'quit'
        icon.stop()
        _window.destroy()

    _window = webview.create_window(
        'AutoDL 释放时间守护',
        f'http://127.0.0.1:{port}',
        width=960,
        height=700,
        resizable=True,
        min_size=(640, 480),
    )
    _window.events.closing += on_closing

    # 注册关闭回调：前端弹框按钮点击后通过 Flask API 回调到这里
    def _handle_close_action(action):
        if action == 'minimize':
            _window.hide()
        else:
            _closing_action[0] = 'quit'
            _window.destroy()

    flask_app.set_close_callback(_handle_close_action)

    # 在后台线程启动系统托盘（传入 on_tray_quit 以共享 _closing_action）
    _tray_thread = threading.Thread(
        target=_run_tray_with_quit, args=(_window, on_tray_quit), daemon=True
    )
    _tray_thread.start()

    webview.start()
