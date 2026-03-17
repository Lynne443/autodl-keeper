"""
自动监控线程：每 24 小时检查一次实例剩余天数，不足 3 天时自动刷新
"""
import threading
import time as _time
from datetime import datetime, timedelta
from pathlib import Path
import json as _json


def _has_valid_token() -> bool:
    token_file = Path(__file__).parent / "token.json"
    if token_file.exists():
        try:
            data = _json.loads(token_file.read_text())
            t = data.get("token", "")
            return bool(t and t.startswith("eyJ"))
        except Exception:
            pass
    return False


class AutoMonitor:
    CHECK_INTERVAL = 24 * 3600  # 24 小时
    THRESHOLD_HOURS = 72        # 3 天

    def __init__(self, log_fn, acquire_fn, release_fn):
        self._log = log_fn
        self._acquire = acquire_fn
        self._release = release_fn
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._next_check: datetime | None = None

    @property
    def enabled(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def next_check_time(self) -> str | None:
        if self._next_check and self.enabled:
            return self._next_check.strftime("%Y-%m-%d %H:%M:%S")
        return None

    def start(self):
        if self.enabled:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._next_check = None

    def _run(self):
        self._log("[监控] 自动监控已启动，每 24 小时检查一次")

        # 启动时如果没有 token，先执行一次完整刷新（会弹浏览器登录）
        if not _has_valid_token():
            self._log("[监控] 未找到有效 Token，先执行一次刷新以完成登录 ...")
            self._do_full_refresh()
            if self._stop_event.is_set():
                self._log("[监控] 自动监控已停止")
                return
        else:
            # 有 token，启动时也立即检查一次
            self._log("[监控] 检测到本地 Token，立即执行首次检查 ...")
            self._check_instances()
            if self._stop_event.is_set():
                self._log("[监控] 自动监控已停止")
                return

        # 进入 24h 循环
        while not self._stop_event.is_set():
            self._next_check = datetime.now() + timedelta(seconds=self.CHECK_INTERVAL)
            self._log(f"[监控] 下次检查时间: {self._next_check.strftime('%Y-%m-%d %H:%M:%S')}")
            if self._stop_event.wait(self.CHECK_INTERVAL):
                break
            self._check_instances()

        self._log("[监控] 自动监控已停止")

    def _do_full_refresh(self):
        """执行完整刷新：获取 token + 刷新所有实例"""
        if not self._acquire():
            self._log("[监控] 有任务正在运行，跳过")
            return
        try:
            from autodl_keeper import (
                AutoDLClient, BOOT_WAIT_SECONDS,
                hours_until_release, format_hours,
            )
            self._log("[监控] 获取 Token ...")
            client = AutoDLClient()
            self._log("[监控] ✓ Token 获取成功")

            self._log("[监控] 获取实例列表 ...")
            instances = client.get_instances()
            if not instances:
                self._log("[监控] ✗ 未获取到任何实例")
                return

            self._log(f"[监控] ✓ 共找到 {len(instances)} 个实例")
            for inst in instances:
                name = inst.get("instance_name") or inst.get("uuid", "?")
                hours = hours_until_release(inst)
                label = format_hours(hours) if hours is not None else "未知"
                self._log(f"[监控]   {name}  |  释放时间: {label}")
            self._log("[监控] 开始刷新所有实例 ...")
            for inst in instances:
                inst_id = inst.get("uuid", "?")
                name = inst.get("instance_name") or inst_id
                self._log(f"[监控] [{name}] 无卡开机 ...")
                if not client.power_on_no_gpu(inst_id):
                    self._log(f"[监控] [{name}] ✗ 开机失败，跳过")
                    continue
                self._log(f"[监控] [{name}] 等待 {BOOT_WAIT_SECONDS}s ...")
                _time.sleep(BOOT_WAIT_SECONDS)
                ok = client.shutdown(inst_id)
                self._log(f"[监控] [{name}] {'✓ 关机完成' if ok else '✗ 关机失败'}")
            self._log("[监控] 首次刷新完成")
        except Exception as e:
            self._log(f"[监控] 出错: {e}")
        finally:
            self._release()

    def _check_instances(self):
        if not _has_valid_token():
            self._log("[监控] Token 已失效，请手动点击「立刻刷新」重新登录")
            return

        if not self._acquire():
            self._log("[监控] 有任务正在运行，跳过本次检查")
            return
        try:
            from autodl_keeper import (
                AutoDLClient, BOOT_WAIT_SECONDS,
                hours_until_release, format_hours,
            )

            self._log("[监控] 开始自动检查 ...")
            client = AutoDLClient()
            instances = client.get_instances()
            if not instances:
                self._log("[监控] 未获取到实例")
                return

            need_refresh = []
            for inst in instances:
                hours = hours_until_release(inst)
                name = inst.get("instance_name") or inst.get("uuid", "?")
                if hours is not None and hours <= self.THRESHOLD_HOURS:
                    self._log(f"[监控] {name} 剩余 {format_hours(hours)}，需要刷新")
                    need_refresh.append(inst)
                else:
                    label = format_hours(hours) if hours is not None else "未知"
                    self._log(f"[监控] {name} 剩余 {label}，无需刷新")

            if not need_refresh:
                self._log("[监控] 所有实例释放时间充足，无需操作")
                return

            for inst in need_refresh:
                inst_id = inst.get("uuid", "?")
                name = inst.get("instance_name") or inst_id
                self._log(f"[监控] [{name}] 无卡开机 ...")
                if not client.power_on_no_gpu(inst_id):
                    self._log(f"[监控] [{name}] 开机失败，跳过")
                    continue
                self._log(f"[监控] [{name}] 等待 {BOOT_WAIT_SECONDS}s ...")
                _time.sleep(BOOT_WAIT_SECONDS)
                ok = client.shutdown(inst_id)
                self._log(f"[监控] [{name}] {'关机完成' if ok else '关机失败'}")

            self._log("[监控] 本次自动检查完成")
        except Exception as e:
            self._log(f"[监控] 出错: {e}")
        finally:
            self._release()

