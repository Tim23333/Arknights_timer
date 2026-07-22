# 明日方舟 API 接口文档

## 目录结构

```
ark_api_docs/
├── README.md                    # 本文件
├── 01_architecture.md           # 网络架构总览
├── 02_auth.md                   # 认证体系 (SDK登录/OAuth2/云认证)
├── 03_account.md                # 账户核心接口
├── 04_battle.md                 # 战斗系统接口
├── 05_gacha.md                  # 抽卡/招募接口
├── 06_building.md               # 基建系统接口
├── 07_shop.md                   # 商店/支付接口
├── 08_charbuild.md              # 角色养成接口
├── 09_social.md                 # 社交系统接口
├── 10_roguelike.md              # 肉鸽/集成战略接口
├── 11_crisis.md                 # 危机合约接口
├── 12_tower.md                  # 爬塔接口
├── 13_mail_mission.md           # 邮件/任务接口
├── 14_sync.md                   # 数据同步接口
└── 15_common_types.md           # 通用数据结构定义
```

## 快速参考

### 服务器地址配置

| 配置键 | 含义 |
|--------|------|
| `gs` | gameServerUrl - 游戏主服务器 |
| `as` | sdkServerUrl - SDK 认证服务器 |
| `u8` | u8ServerUrl - U8 SDK 服务器 |
| `hu` | hotUpdateUrl - 热更新服务器 |
| `an` | announceUrl - 公告服务器 |

### 认证流程

```
启动 → 远程拉取路由配置 → 解析服务器地址
  → SDK 认证 (OAuth2) → 获取服务器列表 → 确认服务器
  → 获取会话 Token (uid + secret)
  → 游戏内所有操作: HTTP POST 到 gameServerUrl
  → 使用 seqNum + secret 进行请求签名
```

### 请求格式

所有游戏接口使用 HTTP POST，Content-Type 为 `application/json`。

请求体结构：
```json
{
  "data": { ... }  // 具体请求数据
}
```

响应体结构：
```json
{
  "data": { ... },           // 具体响应数据
  "playerDataDelta": { ... } // 玩家数据增量 (修改类接口)
}
```
