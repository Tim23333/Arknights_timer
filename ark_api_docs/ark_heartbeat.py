#!/usr/bin/env python3
"""
明日方舟游戏服务器 API 客户端

流程:
  1. GET  /config/prod/official/network_config  — 获取服务器地址
  2. POST /account/login                        — 游戏登录
  3. POST /account/syncData                     — 同步玩家数据
  4. POST /account/syncStatus                   — 同步状态
  5. POST /account/syncPushMessage              — 同步推送消息
  6. POST /online/v1/ping                       — 每 10 秒心跳

用法:
  python ark_heartbeat.py --uid YOUR_UID --token YOUR_TOKEN
"""

import argparse
import json
import time
import sys
import uuid
from datetime import datetime

try:
    import requests
except ImportError:
    print("需要安装 requests: pip install requests")
    sys.exit(1)

# ============================================================
# 在这里填写你的配置
# ============================================================
UID = ""          # ← 填写 uid (从抓包获取)
TOKEN = ""        # ← 填写 token (从抓包获取)

# 心跳间隔 (秒)
HEARTBEAT_INTERVAL = 10
# ============================================================


def fetch_network_config() -> dict:
    """从远程获取服务器配置"""
    url = "https://ak-conf.hypergryph.com/config/prod/official/network_config"
    print(f"[CONFIG] GET {url}")
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    raw = resp.json()
    content = json.loads(raw["content"])
    network = content["configs"][content["funcVer"]]["network"]
    print(f"[CONFIG] 版本: {content['configVer']}/{content['funcVer']}")
    return network


def fetch_version(config: dict) -> dict:
    """获取版本信息"""
    version_url = config.get("hv", "").replace("{0}", "PC")
    if not version_url:
        version_url = "https://ak-conf.hypergryph.com/config/prod/official/PC/version"
    try:
        print(f"[VERSION] GET {version_url}")
        resp = requests.get(version_url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            print(f"[VERSION] clientVersion={data.get('clientVersion')}, resVersion={data.get('resVersion')}")
            return data
    except Exception as e:
        print(f"[VERSION] 失败: {e}")
    return {"clientVersion": "2.7.41", "resVersion": ""}


class ArknightsClient:
    """明日方舟游戏服务器客户端"""

    def __init__(self, config: dict, version: dict, uid: str, token: str):
        self.game_url = config["gs"].rstrip("/")
        self.session = requests.Session()
        self.session.headers["Content-Type"] = "application/json"

        self.uid = uid
        self.token = token
        self.client_version = version.get("clientVersion", "2.7.41")
        self.assets_version = version.get("resVersion", "")
        self.network_version = version.get("resVersion", "")

        self.device_id = uuid.uuid4().hex[:32]
        self.device_id2 = uuid.uuid4().hex[:32]
        self.device_id3 = uuid.uuid4().hex[:32]
        self.seq_num = 0

    def _base_payload(self) -> dict:
        """所有请求共用的基础字段"""
        return {
            "uid": self.uid,
            "token": self.token,
        }

    def post(self, path: str, payload: dict = None, timeout: int = 30) -> dict:
        url = f"{self.game_url}{path}"
        body = payload if payload is not None else {}
        data = json.dumps(body, separators=(",", ":"))
        resp = self.session.post(url, data=data, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    # --------------------------------------------------------
    # 1. 游戏登录
    # --------------------------------------------------------
    def login(self) -> dict:
        """
        POST /account/login

        必填字段 (逐步测试发现):
          uid, token, assetsVersion, clientVersion,
          networkVersion, deviceId, deviceId2, deviceId3, platform
        """
        payload = {
            **self._base_payload(),
            "assetsVersion": self.assets_version,
            "clientVersion": self.client_version,
            "networkVersion": self.network_version,
            "deviceId": self.device_id,
            "deviceId2": self.device_id2,
            "deviceId3": self.device_id3,
            "platform": 1,
        }

        print(f"\n{'='*50}")
        print(f"[1/5] POST /account/login")
        print(f"{'='*50}")
        resp = self.post("/account/login", payload)

        result = resp.get("result", -1)
        if result == 0:
            print(f"[LOGIN] ✓ 登录成功")
        else:
            print(f"[LOGIN] ✗ 失败, result={result}")
            if result == 3:
                print(f"[LOGIN] uid/token 无效或已过期，请重新抓包")
            print(f"[LOGIN] 响应: {json.dumps(resp, indent=2, ensure_ascii=False)[:500]}")
            sys.exit(1)

        return resp

    # --------------------------------------------------------
    # 2. 同步玩家数据
    # --------------------------------------------------------
    def sync_data(self) -> dict:
        """
        POST /account/syncData

        获取玩家完整数据 (干员/背包/编队/基建/关卡进度等)
        """
        print(f"\n{'='*50}")
        print(f"[2/5] POST /account/syncData")
        print(f"{'='*50}")
        resp = self.post("/account/syncData", self._base_payload())

        # 输出数据摘要
        user = resp.get("user", {})
        status = user.get("status", {})
        if status:
            print(f"[SYNC] 昵称: {status.get('nickName', 'N/A')}")
            print(f"[SYNC] 等级: {status.get('level', 'N/A')}")
            print(f"[SYNC] 理智: {status.get('ap', '?')}/{status.get('maxAp', '?')}")
            print(f"[SYNC] 龙门币: {status.get('gold', '?')}")
            print(f"[SYNC] 至纯源石: {status.get('diamond', '?')}")
            print(f"[SYNC] 合成玉: {status.get('diamondShard', '?')}")

        chars = user.get("chars", {})
        if chars:
            print(f"[SYNC] 干员数量: {len(chars)}")

        squads = user.get("squads", {})
        if squads:
            print(f"[SYNC] 编队数量: {len(squads)}")

        print(f"[SYNC] ✓ 同步完成")
        return resp

    # --------------------------------------------------------
    # 3. 同步状态
    # --------------------------------------------------------
    def sync_status(self, modules: int = 0xFFFFFFFF) -> dict:
        """
        POST /account/syncStatus

        按模块同步状态，比 syncData 更轻量
        modules: 64位掩码，指定要同步的模块
        """
        print(f"\n{'='*50}")
        print(f"[3/5] POST /account/syncStatus")
        print(f"{'='*50}")
        payload = {
            **self._base_payload(),
            "modules": modules,
            "params": {},
        }
        resp = self.post("/account/syncStatus", payload)

        ts = resp.get("ts", 0)
        result = resp.get("result", {})
        print(f"[STATUS] 服务器时间: {ts}")
        print(f"[STATUS] 返回模块数: {len(result)}")
        print(f"[STATUS] ✓ 同步完成")
        return resp

    # --------------------------------------------------------
    # 4. 同步推送消息
    # --------------------------------------------------------
    def sync_push_message(self) -> dict:
        """
        POST /account/syncPushMessage

        获取服务端推送的消息 (新邮件/好友申请等)
        """
        print(f"\n{'='*50}")
        print(f"[4/5] POST /account/syncPushMessage")
        print(f"{'='*50}")
        resp = self.post("/account/syncPushMessage", self._base_payload())

        messages = resp.get("pushMessage", [])
        print(f"[PUSH] 推送消息数: {len(messages)}")
        for i, msg in enumerate(messages[:5]):
            path = msg.get("path", "")
            print(f"[PUSH]   [{i+1}] {path}")
        if len(messages) > 5:
            print(f"[PUSH]   ... 还有 {len(messages)-5} 条")

        print(f"[PUSH] ✓ 同步完成")
        return resp

    # --------------------------------------------------------
    # 5. 心跳
    # --------------------------------------------------------
    def ping(self) -> dict:
        """
        POST /online/v1/ping

        注意: 该接口在 ak-gs-gf.hypergryph.com 返回 404
        可能实际路径不同，先尝试调用
        """
        ts = int(time.time())
        payload = {"ts": ts}

        try:
            resp = self.post("/online/v1/ping", payload, timeout=10)
            server_ts = resp.get("ts", 0)
            delta = server_ts - ts if server_ts else 0
            now = datetime.now().strftime("%H:%M:%S")
            print(f"[PING {now}] client={ts}  server={server_ts}  delta={delta:+d}s")
            return resp
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                # ping 路径可能不对，静默处理
                now = datetime.now().strftime("%H:%M:%S")
                print(f"[PING {now}] /online/v1/ping 返回 404，尝试其他路径...")
                # 尝试 syncStatus 作为心跳替代
                return self.sync_status()
            raise

    def run_heartbeat(self, interval: int = 10):
        """心跳循环"""
        print(f"\n{'='*50}")
        print(f"[5/5] 开始心跳循环 (间隔 {interval}s)")
        print(f"      按 Ctrl+C 停止")
        print(f"{'='*50}\n")

        count = 0
        fails = 0
        while True:
            try:
                self.ping()
                count += 1
                fails = 0
            except KeyboardInterrupt:
                print(f"\n[STOP] 用户中断，共发送 {count} 次心跳")
                break
            except Exception as e:
                fails += 1
                print(f"[ERROR] {e}  (连续失败 {fails} 次)")
                if fails >= 5:
                    print("[STOP] 连续失败 5 次，停止")
                    break
            time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="明日方舟游戏服务器 API 客户端")
    parser.add_argument("--uid", default=UID, help="用户 UID")
    parser.add_argument("--token", default=TOKEN, help="认证 Token")
    parser.add_argument("--interval", type=int, default=HEARTBEAT_INTERVAL, help="心跳间隔 (秒)")
    args = parser.parse_args()

    if not args.uid or not args.token:
        print("=" * 50)
        print("需要提供 uid 和 token")
        print("=" * 50)
        print()
        print("获取方式:")
        print("  1. 用 Fiddler/Charles 抓包游戏登录请求")
        print("  2. 找到 POST /account/login 请求")
        print("  3. 从请求体中复制 uid 和 token")
        print()
        print("用法:")
        print("  python ark_heartbeat.py --uid YOUR_UID --token YOUR_TOKEN")
        print()
        print("或直接编辑脚本顶部的 UID 和 TOKEN 变量")
        sys.exit(1)

    # Step 0: 获取服务器配置
    print("=" * 50)
    print("明日方舟游戏服务器 API 客户端")
    print("=" * 50)
    config = fetch_network_config()
    version = fetch_version(config)
    print(f"  游戏服务器: {config['gs']}")
    print("=" * 50)

    client = ArknightsClient(config, version, args.uid, args.token)

    # Step 1: 登录
    client.login()

    # Step 2: 同步数据
    client.sync_data()

    # Step 3: 同步状态
    client.sync_status()

    # Step 4: 同步推送消息
    client.sync_push_message()

    # Step 5: 心跳循环
    client.run_heartbeat(interval=args.interval)


if __name__ == "__main__":
    main()
