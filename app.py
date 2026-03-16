"""
Flask 后端：提供 API 供 React UI 调用，使用轮询方式实时推送日志
"""
import sys
import json
import threading
import time as _time
from pathlib import Path
from flask import Flask, Response, send_from_directory, jsonify, request


def get_base_dir() -> Path:
    """EXE 模式返回 EXE 所在目录，开发模式返回源码目录"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent


# ── 全局日志状态 ──────────────────────────
_logs: list[str] = []
_running = False
_lock = threading.Lock()


def _put_log(msg: str):
    with _lock:
        _logs.append(msg)


def create_app(static_folder: str) -> Flask:
    app = Flask(__name__, static_folder=static_folder)
    app.config['JSON_AS_ASCII'] = False

    # ── 静态文件（React build）────────────
    @app.route('/')
    def index():
        return send_from_directory(static_folder, 'index.html')

    @app.route('/<path:path>')
    def static_files(path):
        file_path = Path(static_folder) / path
        if file_path.exists():
            return send_from_directory(static_folder, path)
        return send_from_directory(static_folder, 'index.html')

    # ── 获取日志（轮询）───────────────────
    @app.route('/api/logs')
    def get_logs():
        offset = int(request.args.get('offset', 0))
        with _lock:
            new_logs = _logs[offset:]
            running = _running
        return jsonify({'logs': new_logs, 'running': running})

    # ── 触发刷新 ──────────────────────────
    @app.route('/api/refresh', methods=['POST'])
    def refresh():
        global _running, _logs
        if _running:
            return jsonify({'status': 'already_running'}), 409

        with _lock:
            _logs = []
            _running = True

        threading.Thread(target=_do_refresh, daemon=True).start()
        return jsonify({'status': 'started'})

    return app


def _do_refresh():
    global _running
    try:
        from autodl_keeper import (
            AutoDLClient, BOOT_WAIT_SECONDS,
            hours_until_release, format_hours
        )

        _put_log(">>> 获取 Token ...")
        client = AutoDLClient()

        _put_log(">>> 获取实例列表 ...")
        instances = client.get_instances()
        if not instances:
            _put_log("✗ 未获取到任何实例")
            return

        _put_log(f"✓ 共找到 {len(instances)} 个实例：")
        for inst in instances:
            name = inst.get("instance_name") or inst.get("uuid", "?")
            hours = hours_until_release(inst)
            release_str = format_hours(hours) if hours is not None else "未知"
            _put_log(f"  {name}  |  释放时间: {release_str}")

        _put_log("\n>>> 开始串行无卡开关机 ...")
        for inst in instances:
            inst_id = inst.get("uuid", "?")
            name = inst.get("instance_name") or inst_id

            _put_log(f"\n[{name}] 无卡开机 ...")
            ok = client.power_on_no_gpu(inst_id)
            if not ok:
                _put_log(f"[{name}] ✗ 开机失败，跳过")
                continue

            _put_log(f"[{name}] 等待 {BOOT_WAIT_SECONDS}s ...")
            _time.sleep(BOOT_WAIT_SECONDS)

            ok = client.shutdown(inst_id)
            _put_log(f"[{name}] {'✓ 关机完成，释放时间已刷新' if ok else '✗ 关机失败'}")

        _put_log("\n>>> 全部实例处理完成！")

    except Exception as e:
        _put_log(f"✗ 出错: {e}")
    finally:
        _running = False
