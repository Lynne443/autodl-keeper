"""
AutoDL 容器释放时间自动刷新脚本
当容器释放时间不足 1 天时，自动开机后立刻关机以刷新释放时间
"""

import time
import logging
import threading
import requests
from datetime import datetime, timezone, timedelta
from get_token import get_token, refresh_token

# 需要监控的实例 ID 列表（留空则监控账号下全部实例）
# 示例: WATCH_INSTANCE_IDS = ["i-xxxxxxxx", "i-yyyyyyyy"]
WATCH_INSTANCE_IDS = []

# 释放时间阈值（小时），低于此值时触发开/关机操作
THRESHOLD_HOURS = 24

# 轮询间隔（小时）
CHECK_INTERVAL_HOURS = 6

# 开机后等待多少秒再关机（给容器一点启动时间）
BOOT_WAIT_SECONDS = 15
# ─────────────────────────────────────────

BASE_URL = "https://www.autodl.com/api/v1"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


class AutoDLClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self._load_token()

    def _load_token(self):
        token = get_token()
        self.session.headers.update({"Authorization": token})

    def _handle_auth_failure(self):
        log.warning("Token 已过期，重新登录获取新 Token ...")
        token = refresh_token()
        self.session.headers.update({"Authorization": token})
        log.info("Token 已更新，继续执行")

    # ── 获取实例列表 ──────────────────────
    def get_instances(self) -> list:
        url = f"{BASE_URL}/instance"
        try:
            resp = self.session.get(url, timeout=15)
            data = resp.json()
        except Exception as e:
            log.error(f"获取实例列表失败: {e}")
            return []

        if data.get("code") == "Success":
            return data.get("data", {}).get("list", [])

        if data.get("code") == "AuthorizeFailed":
            self._handle_auth_failure()
            return self.get_instances()  # 重试一次

        log.error(f"获取实例列表异常: {data.get('msg', data)}")
        return []

    # ── 普通开机 ──────────────────────────
    def power_on(self, instance_id: str) -> bool:
        url = f"{BASE_URL}/instance/power_on"
        payload = {"instance_uuid": instance_id}
        try:
            resp = self.session.post(url, json=payload, timeout=15)
            data = resp.json()
        except Exception as e:
            log.error(f"[{instance_id}] 开机请求失败: {e}")
            return False

        if data.get("code") == "Success":
            log.info(f"[{instance_id}] 普通开机指令已发送")
            return True

        msg = data.get("msg", "")
        log.warning(f"[{instance_id}] 普通开机失败: {msg}")
        # 返回 None 表示"失败但可以尝试无卡开机"
        return None if self._is_gpu_shortage(msg) else False

    # ── 无卡开机 ──────────────────────────
    def power_on_no_gpu(self, instance_id: str) -> bool:
        """无卡模式开机（GPU 资源不足时的降级方案）"""
        url = f"{BASE_URL}/instance/power_on"
        payload = {"instance_uuid": instance_id, "payload": "non_gpu"}
        try:
            resp = self.session.post(url, json=payload, timeout=15)
            data = resp.json()
        except Exception as e:
            log.error(f"[{instance_id}] 无卡开机请求失败: {e}")
            return False

        if data.get("code") == "Success":
            log.info(f"[{instance_id}] 无卡开机指令已发送")
            return True

        log.error(f"[{instance_id}] 无卡开机也失败: {data.get('msg', data)}")
        return False

    @staticmethod
    def _is_gpu_shortage(msg: str) -> bool:
        """判断失败原因是否为 GPU 资源不足"""
        keywords = ["gpu", "显卡", "资源不足", "insufficient", "no resource", "售罄"]
        msg_lower = msg.lower()
        return any(kw in msg_lower for kw in keywords)

    # ── 关机 ─────────────────────────────
    def shutdown(self, instance_id: str) -> bool:
        url = f"{BASE_URL}/instance/power_off"
        payload = {"instance_uuid": instance_id}
        try:
            resp = self.session.post(url, json=payload, timeout=15)
            data = resp.json()
        except Exception as e:
            log.error(f"[{instance_id}] 关机请求失败: {e}")
            return False

        ok = data.get("code") == "Success"
        if ok:
            log.info(f"[{instance_id}] 关机指令已发送")
        else:
            log.error(f"[{instance_id}] 关机失败: {data.get('msg', data)}")
        return ok


def format_hours(hours: float) -> str:
    total_min = int(abs(hours) * 60)
    d, rem = divmod(total_min, 1440)
    h, m = divmod(rem, 60)
    if hours < 0:
        return f"已过期 {d}天{h}小时{m}分"
    return f"{d}天{h}小时{m}分后释放"


def hours_until_release(instance: dict) -> float | None:
    """
    计算距释放时间还有多少小时。
    AutoDL 规则：从上次关机时间(stopped_at)起计 15 天后释放实例。
    """
    stopped_at = instance.get("stopped_at", {})
    if not stopped_at.get("Valid"):
        return None
    stopped_str = stopped_at.get("Time")
    if not stopped_str:
        return None

    stopped = datetime.fromisoformat(stopped_str)
    release_time = stopped + timedelta(days=15)
    now = datetime.now(timezone.utc)
    return (release_time - now).total_seconds() / 3600


def _refresh_one(client: AutoDLClient, inst: dict):
    inst_id = inst.get("uuid") or inst.get("instance_uuid") or inst.get("id", "?")
    inst_name = inst.get("instance_name") or inst.get("name") or inst_id

    hours_left = hours_until_release(inst)
    if hours_left is None:
        log.info(f"[{inst_name}] 未找到释放时间字段，跳过")
        return

    log.info(f"[{inst_name}] 距释放剩余 {hours_left:.1f} 小时")

    if hours_left >= THRESHOLD_HOURS:
        log.info(f"[{inst_name}] 释放时间充足，无需操作")
        return

    log.info(f"[{inst_name}] 不足 {THRESHOLD_HOURS}h，开始刷新释放时间（无卡模式）...")
    result = client.power_on_no_gpu(inst_id)

    if result:
        log.info(f"[{inst_name}] 等待 {BOOT_WAIT_SECONDS}s 后关机 ...")
        time.sleep(BOOT_WAIT_SECONDS)
        client.shutdown(inst_id)
        log.info(f"[{inst_name}] 释放时间刷新完成")
    else:
        log.error(f"[{inst_name}] 开机失败，本次刷新跳过，下次轮询再试")


def check_and_refresh(client: AutoDLClient):
    instances = client.get_instances()
    if not instances:
        log.warning("未获取到任何实例，跳过本次检查")
        return

    targets = [
        inst for inst in instances
        if not WATCH_INSTANCE_IDS
        or (inst.get("uuid") or inst.get("instance_uuid") or inst.get("id")) in WATCH_INSTANCE_IDS
    ]

    # 串行处理：同一时刻只允许一个无卡实例开机
    for inst in targets:
        _refresh_one(client, inst)


def main():
    log.info("AutoDL 释放时间守护脚本启动")
    log.info(f"轮询间隔: {CHECK_INTERVAL_HOURS}h  |  阈值: {THRESHOLD_HOURS}h")

    client = AutoDLClient()

    while True:
        log.info("─" * 50)
        check_and_refresh(client)

        next_check = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log.info(f"下次检查将在 {CHECK_INTERVAL_HOURS}h 后 (当前时间: {next_check})")
        time.sleep(CHECK_INTERVAL_HOURS * 3600)


if __name__ == "__main__":
    main()
