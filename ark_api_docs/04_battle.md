# 战斗系统接口

## 一、核心概念

### 战斗签名机制

战斗系统使用签名验证防止作弊:

1. **开始战斗**: 服务端返回 `sign` (签名)
2. **结束战斗**: 客户端携带 `seed` (种子) 和战斗数据
3. **服务端验证**: 使用 `sign` + `seed` 验证战斗数据完整性

```csharp
// 接口定义
public interface IStartBattleReqWithSign
{
    void SetSeed(string seed);
}

public interface IStartBattleRespWithSign
{
    string GetSign();
}
```

---

## 二、普通关卡战斗

### 2.1 开始战斗

**ServiceCode**: `/quest/battleStart`

**请求**: `DefaultStartBattleRequest` (继承 `CommonStartBattleRequest`)

```json
{
  "stageId": "main_01-01",           // 关卡ID
  "usePracticeTicket": false,        // 是否使用练习券
  "isRetro": false,                  // 是否复刻关卡
  "pry": 1,                          // 理智倍率 (1=正常, 2=双倍)
  "battleType": "COMMON",            // 战斗类型
  // battleType 枚举:
  // "COMMON"      - 普通战斗
  // "CONTINUOUS"  - 连续战斗
  // "MULTIPLE"    - 多次战斗

  "squad": {                         // 编队
    "squadId": "squad_1",
    "name": "默认编队",
    "slots": [
      {
        "charInstId": 1,             // 干员实例ID
        "skillIndex": 0,             // 技能索引 (0/1/2)
        "currentTmpl": "",           // 当前模板 (阿米娅等多形态)
        "currentEquip": ""           // 当前模组ID
      }
    ]
  },
  "assistFriend": {                  // 助战干员 (可选)
    "uid": "friend_uid",
    "charInstId": 123,
    "skillIndex": 0
  },
  "isReplay": false,                 // 是否回放
  "startTs": 1234567890,             // 开始时间戳 (毫秒)
  "multiple": {                      // 多次战斗参数 (battleType=MULTIPLE时)
    "times": 6                       // 战斗次数
  }
}
```

**响应**: `DefaultStartBattleResponse` (继承 `CommonStartBattleResponse`)

```json
{
  "result": 0,                       // 0=成功
  "battleId": "battle_unique_id",    // 战斗唯一ID (结束战斗时需要)
  "sign": "battle_signature",        // 战斗签名 (验证用)
  "isApProtect": false,              // 是否理智保护
  "apFailReturn": 0,                 // 失败返还理智
  "inApProtectPeriod": false,        // 是否在理智保护期内
  "playerDataDelta": { ... }         // 玩家数据增量
}
```

### 2.2 结束战斗

**ServiceCode**: `/quest/battleFinish`

**请求**: `DefaultFinishBattleRequest` (继承 `CommonFinishBattleRequest`)

```json
{
  "battleId": "battle_unique_id",    // 战斗ID (来自开始战斗响应)
  "stageId": "main_01-01",           // 关卡ID
  "isCheat": false,                  // 是否作弊
  "completeTime": 1234567890,        // 完成时间戳
  "data": "encrypted_battle_data",   // 加密的战斗数据
  "battleData": {                    // 战斗统计数据
    "isCheat": "0",
    "completeTime": 1234567890,
    "stats": {
      "killCnt": "25",               // 击杀数
      "usage": "[]"                  // 干员使用情况 (JSON)
    }
  }
}
```

**响应**: `DefaultFinishBattleResponse` (继承 `CommonFinishBattleResponse`)

```json
{
  "result": 0,                       // 0=成功, 1=失败
  "apFailReturn": 10,                // 失败返还理智
  "rewards": [                       // 奖励列表
    {
      "id": "4001",                  // 物品ID
      "type": "GOLD",                // 物品类型
      "count": 1200                  // 数量
    }
  ],
  "itemReturn": [],                  // 物品返还
  "unusualRewards": [],              // 特殊奖励
  "overrideRewards": [],             // 覆盖奖励
  "additionalRewards": [],           // 附加奖励
  "diamondMaterialRewards": [],      // 合成玉素材奖励
  "furnitureRewards": [],            // 家具奖励
  "playerDataDelta": { ... }
}
```

---

## 三、剿灭作战

### 3.1 开始战斗

**ServiceCode**: `/campaignV2/battleStart`

**请求**: `CampaignBattleStartRequest`

```json
{
  "campaignId": "campaign_001",      // 剿灭ID
  "squad": { ... },                  // 编队 (同上)
  "usePracticeTicket": false
}
```

### 3.2 结束战斗

**ServiceCode**: `/campaignV2/battleFinish`

### 3.3 扫荡

**ServiceCode**: `/campaignV2/battleSweep`

```json
{
  "campaignId": "campaign_001",
  "times": 1
}
```

---

## 四、活动战斗

### 4.1 活动关卡开始

**ServiceCode**: `/activity/vecBreakV2/battleStart` (危机合约等活动)

### 4.2 活动关卡结束

**ServiceCode**: `/activity/vecBreakV2/battleFinish`

---

## 五、编队管理

### 5.1 编队配置

**ServiceCode**: `/quest/squadFormation`

**请求**: `SquadFormationRequest`

```json
{
  "squadId": "squad_1",              // 编队ID (squad_1 ~ squad_4)
  "slots": [
    {
      "charInstId": 1,               // 干员实例ID (0=空位)
      "skillIndex": 0,               // 技能索引
      "currentTmpl": "",             // 当前模板
      "currentEquip": ""             // 当前模组
    }
  ],
  "changeSkill": 1                   // 是否同时切换技能 (1=是, 0=否)
}
```

**注意**: `changeSkill` 是布尔值，但使用 `BoolToIntJsonConverter` 序列化为整数。

### 5.2 修改编队名

**ServiceCode**: `/quest/changeSquadName`

**请求**: `SquadRenameRequest`

```json
{
  "squadId": "squad_1",
  "name": "新编队名称"
}
```

**响应**: `SquadRenameResponse` (继承 `ExaminResponse`)

```json
{
  "result": "SUCCESS",               // 审核结果
  "playerDataDelta": { ... }
}
```

**注意**: 编队名需要内容审核，可能返回 `NEED_REVIEW`。

---

## 六、助战系统

### 6.1 获取助战列表

**ServiceCode**: `/quest/getAssistList`

**请求**: `GetAssistListRequest`

```json
{
  "stageId": "main_01-01"            // 关卡ID (可选)
}
```

**响应**: `GetAssistListResponse`

```json
{
  "assistList": [
    {
      "uid": "friend_uid",
      "nickName": "昵称",
      "level": 120,
      "char": {
        "charId": "char_002_amiya",
        "level": 90,
        "skillIndex": 2,
        "evolvePhase": 2
      }
    }
  ]
}
```

---

## 七、战斗回放

### 7.1 保存回放

**ServiceCode**: `/quest/saveBattleReplay`

**请求**: `SaveBattleReplayRequest`

```json
{
  "battleId": "battle_unique_id",
  "battleReplay": "replay_data_string"   // 回放数据 (编码后)
}
```

### 7.2 获取回放

**ServiceCode**: `/quest/getBattleReplay`

**请求**: `LoadBattleReplayRequest`

```json
{
  "stageId": "main_01-01"
}
```

**响应**: `LoadBattleReplayReponse`

```json
{
  "battleReplay": "replay_data_string"
}
```

---

## 八、关卡解锁

### 8.1 完成剧情关卡

**ServiceCode**: `/quest/finishStoryStage`

```json
{
  "stageId": "stage_id"
}
```

### 8.2 解锁迷雾关卡

**ServiceCode**: `/quest/unlockStageFog`

### 8.3 解锁隐藏关卡

**ServiceCode**: `/quest/unlockHideStage`

---

## 九、通用战斗类型

游戏使用泛型 ServiceConfig 模式管理不同类型的战斗:

```csharp
// 基类
public abstract class StartBattleServiceConfig<TRequest, TResponse>
{
    public abstract string serviceCode { get; }
    public abstract TRequest ParseRequest(...);
}

// 具体实现
public class CrisisV2StartServiceConfig : StartBattleServiceConfig<...>     // 危机合约
public class SandboxV2StartBattleServiceConfig : StartBattleServiceConfig<...>  // 沙盒
public class BossRushBattleStartConfig : StartBattleServiceConfig<...>      // Boss Rush
public class RogueLikeStartBattleServiceConfig : StartBattleServiceConfig<...> // 肉鸽
public class TowerStartBattleServiceConfig : StartBattleServiceConfig<...>  // 爬塔
```

每种战斗类型只需要实现 `serviceCode` 和 `ParseRequest()`，战斗流程逻辑复用基类。
