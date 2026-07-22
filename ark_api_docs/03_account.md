# 账户核心接口

## 一、登录

**ServiceCode**: `/account/login`

详见 `02_auth.md` 中的"游戏内登录"部分。

---

## 二、同步玩家数据

**ServiceCode**: `/account/syncData`

**请求**: `SyncDataRequest`

```json
{}
```

**响应**: `SyncDataResponse` (继承 `PlayerInitResponse`)

```json
{
  "user": {
    "status": { ... },         // 玩家状态
    "inventory": { ... },      // 背包物品
    "chars": { ... },          // 干员数据
    "squads": { ... },         // 编队数据
    "building": { ... },       // 基建数据
    "shop": { ... },           // 商店数据
    "social": { ... },         // 社交数据
    "quest": { ... },          // 关卡进度
    "campaign": { ... },       // 剿灭进度
    "activity": { ... },       // 活动数据
    "mail": { ... },           // 邮件
    "mission": { ... },        // 任务
    "gacha": { ... },          // 抽卡数据
    "recruit": { ... },        // 公开招募
    "rlv2": { ... },           // 肉鸽数据
    "crisis": { ... },         // 危机合约
    "tower": { ... },          // 爬塔数据
    "rogue": { ... },          // 旧肉鸽
    "story": { ... }           // 剧情进度
  },
  "pushMessage": []
}
```

---

## 三、同步状态

**ServiceCode**: `/account/syncStatus`

**请求**: `PlayerSyncStatusRequest`

```json
{
  "modules": 4294967295,       // 模块掩码 (64位，每个bit代表一个模块)
  "params": {                  // 可选参数
    "1234567890": {            // 模块ID (long)
      "param1": "value1"
    }
  }
}
```

**响应**: `PlayerSyncStatusResponse`

```json
{
  "ts": 1234567890,            // 服务器时间戳
  "result": {                  // 各模块结果
    "1234567890": {            // 模块ID
      "status": 0,
      "data": { ... }
    }
  }
}
```

---

## 四、同步推送消息

**ServiceCode**: `/account/syncPushMessage`

**请求**: `SyncPushMessageRequest`

**响应**: `SyncPushMessageResponse`

```json
{
  "pushMessage": [
    {
      "path": "message/path",
      "payload": { ... }
    }
  ]
}
```

---

## 五、获取版本

**ServiceCode**: `/admin/getVersion`

**响应**:

```json
{
  "version": "version_string"
}
```

---

## 六、设置相关

### 6.1 低功耗模式

**ServiceCode**: `/setting/perf/setLowPower`

```json
{
  "enabled": true
}
```

---

## 七、剧情相关

### 7.1 完成剧情

**ServiceCode**: `/story/finishStory`

**请求**: `FinishStoryRequest`

```json
{
  "storyId": "story_id"
}
```
