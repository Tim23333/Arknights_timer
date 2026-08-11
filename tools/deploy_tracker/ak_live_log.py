"""代理作战序列 实时监控 + 导出 (控制台版)

读取 BattleLogger.m_logs 实时操作日志, 关卡内每一次 部署/技能/撤退/CHEAT
都会在发生约 0.5 秒内打印出来, 并自动保存 JSON (每 10 条事件增量落盘,
Ctrl+C 或战斗结束时最终落盘)。

用法:
    python -m tools.deploy_tracker.ak_live_log [--out deploy_log.json] [--interval 0.5]

前提: MuMu 模拟器已启动且 adb root 可用, 并已进入关卡。尚无任何操作记录时
也可定位空日志容器。首次定位需全堆扫描约 2 分钟, 之后即实时。
"""

import argparse
import json
import os
import sys
import time

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from tools.deploy_tracker.ak_deploy_reader import (  # noqa: E402
    DeployTrackerReader, BATTLE_STATE_NAMES)
from tools.enemy_health.memcore import MemCore  # noqa: E402

_DIR_ARROW = {0: "UP", 1: "RIGHT", 2: "DOWN", 3: "LEFT", 4: "-"}
_OP_CN = {0: "部署", 1: "撤退", 2: "技能", 3: "CHEAT"}


def fmt_event(ev):
    arrow = _DIR_ARROW.get(ev["direction"], "?")
    op = _OP_CN.get(ev["op"], ev["opName"])
    name = ev["charName"] or ev["charId"]
    pos = f"({ev['gridCol']},{ev['gridRow']})"  # (列,行)
    extra = f" extra={ev['extraInfo']}" if ev.get("extraInfo") else ""
    return f"[{ev['timestamp']:8.3f}s] {op:<4} {name:<12} {arrow} {pos}{extra}"


def export_json(path, reader, events, squad):
    stage = reader.get_stage_info()
    payload = {
        "source": "live",
        "exportTime": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stageId": stage.get("stageId", ""),
        "levelId": stage.get("levelId", ""),
        "stage": stage,
        "battle": reader.get_battle_state(),
        "squad": squad,
        "events": events,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser(description="实时操作日志监控 + 导出")
    ap.add_argument("--out", default="", help="导出 JSON 路径 (默认 deploy_log_<时间>.json)")
    ap.add_argument("--interval", type=float, default=0.5, help="轮询间隔秒 (默认 0.5)")
    args = ap.parse_args()

    out_path = args.out or os.path.join(
        _PROJECT_ROOT, f"deploy_log_{time.strftime('%Y%m%d_%H%M%S')}.json")

    print("[*] 连接游戏进程 ...", flush=True)
    mc = MemCore()
    pid = mc.connect()
    print(f"[*] 已连接 {mc.package} (pid {pid})", flush=True)

    reader = DeployTrackerReader(mc)
    print("[*] 定位 BattleLogger (首次需全堆扫描, 约 2 分钟) ...", flush=True)
    t0 = time.time()
    if not reader.locate():
        print("[!] 定位失败 — 请确认游戏进程正常且已进入作战关卡后重试", flush=True)
        return 1
    print(f"[*] 定位成功 ({time.time() - t0:.0f}s), 开始实时监控 "
          f"(Ctrl+C 结束并导出)", flush=True)

    stage = reader.get_stage_info()
    if stage:
        label = " ".join(x for x in (stage.get("code"), stage.get("name")) if x)
        print(f"[*] 当前关卡: {label or stage.get('levelId', '')} "
              f"({stage.get('stageId', '')})", flush=True)

    squad = reader.get_squad()
    if squad:
        names = "、".join(c["charName"] or c["charId"] for c in squad)
        print(f"[*] 编队 {len(squad)} 人: {names}", flush=True)

    seen = 0
    last_save = time.time()
    last_state = -1
    events = []
    try:
        while True:
            if not reader.is_chain_valid():
                print("[!] 地址链失效 (关卡已结束?), 停止监控", flush=True)
                break
            events = reader.get_events()
            for ev in events[seen:]:
                print(fmt_event(ev), flush=True)
            seen = len(events)

            st = reader.get_battle_state()
            if st and st["state"] != last_state:
                last_state = st["state"]
                print(f"[*] 战斗状态: {st['stateName']} "
                      f"playTime={st['playTime']}s speed=x{st['speedLevel']}", flush=True)
                if st["state"] == 3:  # FINISHED
                    print("[*] 战斗结束", flush=True)
                    break
            # 增量落盘 (防崩溃丢失)
            if events and time.time() - last_save > 5:
                export_json(out_path, reader, events, squad)
                last_save = time.time()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[*] 手动停止", flush=True)

    events = reader.get_events() or events
    export_json(out_path, reader, events, squad)
    print(f"[*] 已导出 {len(events)} 条操作 -> {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
