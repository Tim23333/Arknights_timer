# 爬塔接口

## 一、创建游戏

**ServiceCode**: `/tower/createGame`

**请求**: `TowerCreateGameRequest`

```json
{
  "towerId": "tower_001",            // 塔ID
  "difficulty": 0                    // 难度
}
```

---

## 二、初始化游戏

**ServiceCode**: `/tower/initGame`

**请求**: `TowerInitGameRequest`

```json
{
  "towerId": "tower_001"
}
```

**响应**: `TowerInitGameResponse`

```json
{
  "gameState": {
    "towerId": "tower_001",
    "currentFloor": 1,               // 当前层数
    "maxFloor": 10,                  // 最大层数
    "chars": [                       // 可用干员
      {
        "charId": "char_002_amiya",
        "hp": 100,
        "maxHp": 100
      }
    ],
    "relics": [],                    // 藏品
    "gold": 0                        // 金币
  },
  "playerDataDelta": { ... }
}
```

---

## 三、战斗相关

### 3.1 开始战斗

**ServiceCode**: `/tower/battleStart`

**请求**: `TowerBattleStartRequest`

```json
{
  "stageId": "tower_stage_001",
  "squad": { ... },                  // 编队
  "startTs": 1234567890
}
```

### 3.2 结束战斗

**ServiceCode**: `/tower/battleFinish`

**请求**: `TowerBattleFinishRequest`

```json
{
  "battleId": "battle_id",
  "stageId": "tower_stage_001",
  "result": 1,
  "data": "encrypted_data",
  "completeTime": 1234567890
}
```

---

## 四、招募干员

**ServiceCode**: `/tower/recruit`

**请求**: `TowerRecruitRequest`

```json
{
  "charId": "char_002_amiya",
  "slotId": 0
}
```

---

## 五、扫荡

**ServiceCode**: `/tower/sweepGame`

**请求**: `TowerSweepRequest`

```json
{
  "towerId": "tower_001",
  "floor": 5                         // 扫荡到第几层
}
```

---

## 六、结算游戏

**ServiceCode**: `/tower/settleGame`

**请求**: `TowerSettleGameRequest`

```json
{
  "result": "WIN",
  "towerId": "tower_001"
}
```

**响应**: `TowerSettleGameResponse`

```json
{
  "rewards": [ ... ],                // 奖励
  "score": 1500,                     // 得分
  "playerDataDelta": { ... }
}
```

---

## 七、数据结构

### 塔游戏状态

```json
{
  "towerId": "tower_001",
  "currentFloor": 5,
  "maxFloor": 10,
  "chars": [
    {
      "charId": "char_002_amiya",
      "hp": 80,                      // 当前生命
      "maxHp": 100,
      "state": "NORMAL",             // 状态
      // "NORMAL"  - 正常
      // "WOUNDED" - 受伤
      // "DEAD"    - 死亡
      "skills": [                    // 技能
        {
          "skillId": "skill_001",
          "cooldown": 0
        }
      ]
    }
  ],
  "relics": [
    {
      "relicId": "relic_001",
      "name": "藏品名称"
    }
  ],
  "gold": 500,
  "progress": {
    "totalBattles": 10,
    "wins": 8,
    "losses": 2
  }
}
```

### 塔配置

```json
{
  "towerId": "tower_001",
  "name": "塔名称",
  "description": "塔描述",
  "maxFloor": 10,
  "difficulty": "NORMAL",
  "rewards": {
    "floorRewards": [                // 每层奖励
      {
        "floor": 1,
        "items": [ ... ]
      }
    ],
    "completionRewards": [ ... ],    // 通关奖励
    "scoreRewards": [ ... ]          // 分数奖励
  }
}
```

### 难度枚举

| 值 | 名称 | 说明 |
|----|------|------|
| 0 | NORMAL | 普通 |
| 1 | HARD | 困难 |
| 2 | NIGHTMARE | 噩梦 |
