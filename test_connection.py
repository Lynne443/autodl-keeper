"""
连通性测试：获取实例列表 + 对所有实例执行开机→等待→关机
"""
import time
from autodl_keeper import AutoDLClient, hours_until_release, format_hours, BOOT_WAIT_SECONDS

client = AutoDLClient()

# 1. 获取实例列表
print(">>> 获取实例列表 ...")
instances = client.get_instances()
if not instances:
    print("✗ 未获取到任何实例")
    exit(1)

print(f"✓ 共找到 {len(instances)} 个实例：\n")
for inst in instances:
    inst_id   = inst.get("uuid", "?")
    inst_name = inst.get("instance_name") or inst_id
    hours     = hours_until_release(inst)
    release_str = format_hours(hours) if hours is not None else "未知"
    print(f"  {inst_name}  |  ID: {inst_id}  |  释放时间: {release_str}")

# 2. 对每个实例做开关机测试（串行）
def refresh_one(inst):
    inst_id   = inst.get("uuid", "?")
    inst_name = inst.get("instance_name") or inst_id

    print(f"  [{inst_name}] 发送无卡开机指令 ...")
    result = client.power_on_no_gpu(inst_id)

    if not result:
        print(f"  [{inst_name}] ✗ 开机失败，跳过")
        return

    print(f"  [{inst_name}] ✓ 开机指令已发送，等待 {BOOT_WAIT_SECONDS}s ...")
    time.sleep(BOOT_WAIT_SECONDS)

    print(f"  [{inst_name}] 发送关机指令 ...")
    ok = client.shutdown(inst_id)
    print(f"  [{inst_name}] {'✓ 关机指令已发送' if ok else '✗ 关机失败'}")

print("\n>>> 开始开关机测试（串行）...")
for inst in instances:
    refresh_one(inst)

print("\n>>> 测试完成")
