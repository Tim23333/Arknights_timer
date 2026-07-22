# 肉鸽/集成战略接口

## 一、集成战略 (Rlv2)

### 1.1 创建游戏

**ServiceCode**: `/rlv2/createGame`

**请求**: `Rlv2CreateGameRequest`

```json
{
  "topicId": "topic_001",            // 主题ID
  "difficulty": 0,                   // 难度 (0=普通, 1=困难)
  "initParams": {                    // 初始参数
    "teamId": "team_001"             // 队伍ID
  }
}
```

### 1.2 移动节点

**ServiceCode**: `/rlv2/moveTo`

**请求**: `Rlv2MoveToRequest`

```json
{
  "nodeId": "node_001"               // 目标节点ID
}
```

### 1.3 移动并开始战斗

**ServiceCode**: `/rlv2/moveAndBattleStart`

**请求**: `Rlv2MoveAndBattleStartRequest`

```json
{
  "nodeId": "node_001",
  "squad": { ... },                  // 编队
  "startTs": 1234567890
}
```

### 1.4 结束战斗

**ServiceCode**: `/rlv2/battleFinish`

**请求**: `Rlv2BattleFinishRequest`

```json
{
  "battleId": "battle_id",
  "stageId": "stage_id",
  "result": 1,                       // 1=胜利, 0=失败
  "data": "encrypted_data",
  "completeTime": 1234567890
}
```

### 1.5 选择初始藏品

**ServiceCode**: `/rlv2/chooseInitialRelic`

**请求**: `Rlv2ChooseInitialRelicRequest`

```json
{
  "relicId": "relic_001"             // 藏品ID
}
```

### 1.6 选择初始招募组合

**ServiceCode**: `/rlv2/chooseInitialRecruitSet`

**请求**: `Rlv2ChooseInitialRecruitSetRequest`

```json
{
  "setId": "set_001"                 // 组合ID
}
```

### 1.7 招募干员

**ServiceCode**: `/rlv2/recruitChar`

**请求**: `Rlv2RecruitCharRequest`

```json
{
  "charId": "char_002_amiya",
  "teamId": "team_001"
}
```

### 1.8 招募助战干员

**ServiceCode**: `/rlv2/recruitAssistChar`

```json
{
  "charId": "char_002_amiya",
  "assistUid": "assist_uid"
}
```

### 1.9 商店操作

**ServiceCode**: `/rlv2/shopAction`

**请求**: `Rlv2ShopActionRequest`

```json
{
  "action": "BUY",                   // 操作类型
  // "BUY"    - 购买
  // "SELL"   - 出售
  // "REFRESH" - 刷新
  "itemId": "item_001",
  "count": 1
}
```

### 1.10 刷新商店

**ServiceCode**: `/rlv2/refreshShop`

```json
{}
```

### 1.11 存钱

**ServiceCode**: `/rlv2/bankPut`

```json
{
  "amount": 100                      // 存入数量
}
```

### 1.12 取钱

**ServiceCode**: `/rlv2/bankWithdraw`

```json
{
  "amount": 100
}
```

### 1.13 选择事件

**ServiceCode**: `/rlv2/chooseEventOption`

```json
{
  "eventId": "event_001",
  "optionId": "option_001"
}
```

### 1.14 丢弃藏品

**ServiceCode**: `/rlv2/discardRelic`

```json
{
  "relicId": "relic_001"
}
```

### 1.15 结算游戏

**ServiceCode**: `/rlv2/settleGame`

```json
{
  "result": "WIN"                    // 结果
  // "WIN"   - 胜利
  // "LOSE"  - 失败
  // "ABORT" - 中途放弃
}
```

---

## 二、旧版肉鸽 (RogueLike)

### 2.1 进入肉鸽

**ServiceCode**: `/rogue/startGame`

```json
{
  "topicId": "rogue_topic_001"
}
```

### 2.2 选择节点

**ServiceCode**: `/rogue/chooseNode`

```json
{
  "nodeId": "node_001"
}
```

### 2.3 战斗开始

**ServiceCode**: `/rogue/battleStart`

```json
{
  "stageId": "stage_id",
  "squad": { ... }
}
```

### 2.4 战斗结束

**ServiceCode**: `/rogue/battleFinish`

```json
{
  "battleId": "battle_id",
  "result": 1,
  "data": "encrypted_data"
}
```

### 2.5 选择藏品

**ServiceCode**: `/rogue/chooseRelic`

```json
{
  "relicId": "relic_001"
}
```

### 2.6 招募干员

**ServiceCode**: `/rogue/recruitChar`

```json
{
  "charId": "char_002_amiya",
  "position": 0
}
```

---

## 三、数据结构

### 肉鸽游戏状态

```json
{
  "topicId": "topic_001",
  "difficulty": 0,
  "currentNode": "node_001",
  "progress": {
    "floor": 3,                      // 当前层数
    "nodeIndex": 5                   // 节点索引
  },
  "team": {
    "chars": [                       // 队伍干员
      {
        "charId": "char_002_amiya",
        "hp": 100,                   // 当前生命值
        "maxHp": 100,
        "state": "NORMAL"            // 状态
      }
    ]
  },
  "inventory": {
    "gold": 500,                     // 金币
    "relics": [                      // 藏品
      {
        "relicId": "relic_001",
        "name": "藏品名称",
        "description": "藏品描述"
      }
    ]
  },
  "bank": {
    "deposited": 200                 // 银行存款
  }
}
```

### 藏品 (Relic)

```json
{
  "relicId": "relic_001",
  "name": "藏品名称",
  "description": "藏品描述",
  "rarity": 3,                       // 稀有度
  "iconId": "icon_001",
  "effects": [                       // 效果
    {
      "type": "STAT_BOOST",
      "target": "ALL",
      "stat": "ATK",
      "value": 0.1
    }
  ]
}
```

### 节点类型

| 类型 | 说明 |
|------|------|
| BATTLE | 战斗节点 |
| ELITE | 精英战斗 |
| BOSS | Boss战斗 |
| EVENT | 事件节点 |
| SHOP | 商店节点 |
| REST | 休息节点 |
| RECRUIT | 招募节点 |
| TREASURE | 宝箱节点 |
