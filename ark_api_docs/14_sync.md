# 数据同步接口

## 一、玩家数据同步

### 1.1 同步玩家数据

**ServiceCode**: `/account/syncData`

这是最核心的数据同步接口，获取玩家的完整数据。

**请求**: 空请求

**响应**: `SyncDataResponse` (继承 `PlayerInitResponse`)

```json
{
  "user": {
    "status": {                      // 玩家状态
      "uid": "user_uid",
      "nickName": "昵称",
      "level": 120,
      "exp": 1234567,
      "ap": 135,                     // 当前理智
      "maxAp": 135,                  // 最大理智
      "apLastUpTime": 1234567890,    // 上次理智恢复时间
      "gold": 999999,                // 龙门币
      "diamond": 100,                // 至纯源石
      "diamondShard": 5000,          // 合成玉
      "socialPoint": 300,            // 信用
      "gachaTicket": 10,             // 寻访凭证
      "tenGachaTicket": 1,           // 十连凭证
      "recruitLicense": 3,           // 招聘许可
      "lastOnlineTime": 1234567890,
      "registerTime": 1234567890,
      "mainStageProgress": "main_10-01",  // 主线进度
      "flags": { ... },              // 标记
      "infoShare": { ... }           // 信息共享状态
    },
    "inventory": {                   // 背包物品
      "items": {
        "item_001": {                // 物品ID
          "id": "item_001",
          "count": 100,
          "type": "MATERIAL"
        }
      }
    },
    "chars": {                       // 干员数据
      "12345": {                     // 干员实例ID
        "instId": 12345,
        "charId": "char_002_amiya",
        "level": 90,
        "exp": 0,
        "evolvePhase": 2,
        "favorPoint": 20000,
        "potentialRank": 6,
        "mainSkillLvl": 7,
        "skills": [ ... ],
        "equip": { ... },
        "currentSkin": "char_002_amiya#1",
        "voiceLan": "CN"
      }
    },
    "squads": {                      // 编队数据
      "squad_1": {
        "squadId": "squad_1",
        "name": "默认编队",
        "slots": [
          {
            "charInstId": 12345,
            "skillIndex": 2,
            "currentTmpl": "",
            "currentEquip": "equip_001"
          }
        ]
      }
    },
    "building": {                    // 基建数据
      "rooms": { ... },
      "chars": { ... },
      "manufacture": { ... },
      "trading": { ... },
      "dormitory": { ... },
      "control": { ... },
      "meeting": { ... }
    },
    "shop": {                        // 商店数据
      "skins": { ... },
      "cash": { ... },
      "credit": { ... },
      "high": { ... },
      "furni": { ... }
    },
    "social": {                      // 社交数据
      "friends": { ... },
      "assistChars": { ... },
      "nameCard": { ... }
    },
    "quest": {                       // 关卡进度
      "stages": {
        "main_01-01": {
          "stageId": "main_01-01",
          "state": "COMPLETE",
          "completeTimes": 10,
          "startTimes": 10,
          "practiceTimes": 0,
          "hasBattleReplay": false
        }
      },
      "farming": { ... }             // 代理作战
    },
    "campaign": {                    // 剿灭进度
      "records": { ... },
      "reward": { ... }
    },
    "activity": {                    // 活动数据
      "activities": { ... },
      "checkIn": { ... }
    },
    "mail": {                        // 邮件
      "mails": { ... }
    },
    "mission": {                     // 任务
      "missions": { ... },
      "rewards": { ... }
    },
    "gacha": {                       // 抽卡数据
      "poolInfo": { ... },
      "newSection": { ... },
      "freeGacha": { ... }
    },
    "recruit": {                     // 公开招募
      "slots": { ... },
      "refreshCount": 0
    },
    "rlv2": {                        // 集成战略
      "current": { ... },
      "records": { ... },
      "relics": { ... }
    },
    "crisis": {                      // 危机合约
      "current": { ... },
      "records": { ... }
    },
    "tower": {                       // 爬塔
      "current": { ... },
      "records": { ... }
    },
    "rogue": {                       // 旧肉鸽
      "current": { ... },
      "records": { ... }
    },
    "story": {                       // 剧情进度
      "stories": { ... },
      "reviewed": { ... }
    },
    "dexNav": {                      // 图鉴
      "chars": { ... },
      "enemies": { ... }
    },
    "homeTheme": {                   // 主页主题
      "current": "theme_001",
      "owned": { ... }
    },
    "medal": {                       // 勋章
      "medals": { ... },
      "display": { ... }
    },
    "openServer": {                  // 开服活动
      "checkIn": { ... }
    },
    "tshop": {                       // 代币商店
      "items": { ... }
    },
    "templateSquad": {               // 模板编队
      "squads": { ... }
    }
  },
  "pushMessage": []
}
```

---

## 二、增量同步

### 2.1 PlayerDataDelta

大部分修改类接口都会返回 `playerDataDelta`，包含本次操作导致的数据变化:

```json
{
  "playerDataDelta": {
    "modified": {                    // 修改的数据
      "status": {
        "ap": 120,                   // 理智变化
        "gold": 999000               // 龙门币变化
      },
      "inventory": {
        "items": {
          "item_001": {
            "count": 90              // 物品数量变化
          }
        }
      },
      "chars": {
        "12345": {
          "level": 91                // 干员等级变化
        }
      }
    },
    "deleted": { ... }               // 删除的数据
  }
}
```

客户端收到 `playerDataDelta` 后，需要将其合并到本地缓存的玩家数据中。

---

## 三、状态同步

### 3.1 同步状态

**ServiceCode**: `/account/syncStatus`

用于同步特定模块的状态数据，比完整同步更轻量。

**请求**: `PlayerSyncStatusRequest`

```json
{
  "modules": 4294967295,             // 64位模块掩码
  "params": {
    "1234567890": {                  // 模块ID
      "param1": "value1"
    }
  }
}
```

**模块掩码说明**:

| 位 | 模块 |
|----|------|
| 0 | 基础状态 |
| 1 | 背包 |
| 2 | 干员 |
| 3 | 编队 |
| 4 | 基建 |
| 5 | 商店 |
| 6 | 社交 |
| 7 | 关卡 |
| ... | ... |

**响应**: `PlayerSyncStatusResponse`

```json
{
  "ts": 1234567890,
  "result": {
    "0": {                           // 模块ID
      "status": 0,
      "data": { ... }
    }
  }
}
```

---

## 四、推送消息同步

### 4.1 同步推送消息

**ServiceCode**: `/account/syncPushMessage`

获取服务端推送的消息，如新邮件通知、好友申请等。

**响应**: `SyncPushMessageResponse`

```json
{
  "pushMessage": [
    {
      "path": "mail/new",
      "payload": {
        "mailId": "mail_001",
        "title": "新邮件"
      }
    },
    {
      "path": "social/friendRequest",
      "payload": {
        "uid": "applicant_uid",
        "nickName": "申请人"
      }
    }
  ]
}
```

---

## 五、心跳机制

### 5.1 心跳检测

**ServiceCode**: `/online/v1/ping`

定期发送心跳保持连接，同时获取服务器时间。

**请求**: `PingRequest`

```json
{
  "ts": 1234567890
}
```

**响应**: `PingResponse`

```json
{
  "ts": 1234567890                   // 服务器时间戳
}
```

### 5.2 空闲探测

`IdelPeriodGameServerProbe` 类在空闲期间定期向游戏服务器发送 Ping 探测，保持连接活跃。

---

## 六、数据同步最佳实践

### 6.1 启动时完整同步

```
1. /account/login          - 登录获取完整数据
2. /account/syncPushMessage - 获取未读推送消息
```

### 6.2 游戏中增量同步

```
1. 每次操作后，合并响应中的 playerDataDelta
2. 定期调用 /account/syncStatus 检查关键数据
3. 切换场景时调用 /account/syncData 获取最新完整数据
```

### 6.3 心跳保持

```
1. 每 30 秒发送 /online/v1/ping
2. 使用 IdelPeriodGameServerProbe 在空闲时保持连接
```
