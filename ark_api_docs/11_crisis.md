# 危机合约接口

## 一、危机合约 V2

### 1.1 获取快照

**ServiceCode**: `/crisisV2/getSnapshot`

**请求**: `CrisisV2GetSnapshotRequest`

```json
{
  "seasonId": "season_001"           // 赛季ID
}
```

**响应**: `CrisisV2GetSnapshotResponse`

```json
{
  "snapshot": {
    "seasonId": "season_001",
    "crisisList": [                  // 危机列表
      {
        "crisisId": "crisis_001",
        "name": "危机名称",
        "level": 0,                  // 已选择的等级
        "maxLevel": 3,               // 最大可选等级
        "completed": false
      }
    ],
    "missions": [                    // 任务列表
      {
        "missionId": "mission_001",
        "name": "任务名称",
        "progress": 0,
        "target": 100,
        "completed": false,
        "rewarded": false
      }
    ],
    "score": 0,                      // 当前分数
    "rank": 0                        // 排名
  },
  "playerDataDelta": { ... }
}
```

### 1.2 开始战斗

**ServiceCode**: `/crisisV2/battleStart`

**请求**: `CrisisV2BattleStartRequest`

```json
{
  "seasonId": "season_001",
  "stageId": "crisis_stage_001",
  "crisisIds": ["crisis_001", "crisis_002"],  // 选择的危机ID列表
  "squad": { ... },                  // 编队
  "startTs": 1234567890
}
```

### 1.3 结束战斗

**ServiceCode**: `/crisisV2/battleFinish`

**请求**: `CrisisV2BattleFinishRequest`

```json
{
  "battleId": "battle_id",
  "stageId": "crisis_stage_001",
  "result": 1,                       // 1=胜利, 0=失败
  "data": "encrypted_data",
  "completeTime": 1234567890
}
```

### 1.4 确认任务

**ServiceCode**: `/crisisV2/confirmMissions`

```json
{
  "missionIds": ["mission_001", "mission_002"]
}
```

---

## 二、危机合约 V1 (旧版)

### 2.1 获取信息

**ServiceCode**: `/crisis/getInfo`

**响应**:

```json
{
  "seasonId": "season_001",
  "crisisList": [ ... ],
  "score": 0,
  "rank": 0,
  "playerDataDelta": { ... }
}
```

### 2.2 开始战斗

**ServiceCode**: `/crisis/battleStart`

```json
{
  "stageId": "crisis_stage_001",
  "crisisIds": ["crisis_001"],
  "squad": { ... }
}
```

### 2.3 结束战斗

**ServiceCode**: `/crisis/battleFinish`

```json
{
  "battleId": "battle_id",
  "result": 1,
  "data": "encrypted_data"
}
```

### 2.4 获取商品列表

**ServiceCode**: `/crisis/getGoodList`

**响应**:

```json
{
  "goodList": [
    {
      "goodId": "crisis_good_001",
      "itemId": "item_001",
      "price": 100,
      "priceType": "CRISIS_TOKEN",
      "limitTimes": 1,
      "boughtTimes": 0
    }
  ],
  "playerDataDelta": { ... }
}
```

### 2.5 购买商品

**ServiceCode**: `/crisis/buyGood`

```json
{
  "goodId": "crisis_good_001",
  "count": 1
}
```

---

## 三、数据结构

### 危机数据

```json
{
  "crisisId": "crisis_001",
  "name": "危机名称",
  "description": "危机描述",
  "level": 0,                        // 当前选择的等级
  "maxLevel": 3,                     // 最大可选等级
  "modifiers": [                     // 修饰器列表
    {
      "modifierId": "mod_001",
      "name": "修饰器名称",
      "description": "效果描述",
      "level": 1,
      "scoreBonus": 50               // 分数加成
    }
  ],
  "completed": false,
  "bestScore": 0                     // 历史最高分
}
```

### 赛季数据

```json
{
  "seasonId": "season_001",
  "name": "赛季名称",
  "startTime": "2024-01-01T00:00:00Z",
  "endTime": "2024-02-01T00:00:00Z",
  "stages": [                        // 关卡列表
    {
      "stageId": "crisis_stage_001",
      "name": "关卡名称",
      "difficulty": "NORMAL"
    }
  ],
  "rewards": [                       // 奖励列表
    {
      "score": 100,
      "items": [ ... ]
    }
  ]
}
```

### 危机等级

| 等级 | 分数倍率 | 说明 |
|------|----------|------|
| 0 | 1.0x | 基础 |
| 1 | 1.5x | 中等 |
| 2 | 2.0x | 困难 |
| 3 | 3.0x | 极限 |
