# 抽卡/招募接口

## 一、公开招募

### 1.1 开始招募

**ServiceCode**: `/gacha/normalGacha`

**请求**: `NormalGachaRequest`

```json
{
  "slotId": 0,                       // 招募槽位 (0-3)
  "tagList": [1, 5, 12],             // 选择的标签ID列表
  "specialTagId": 0,                 // 特殊标签ID (高级资深等)
  "duration": 28800                  // 招募时长 (秒)
  // 常用时长:
  // 3600   = 1小时 (1星)
  // 5400   = 1.5小时 (2星)
  // 18000  = 5小时 (3星)
  // 28800  = 8小时 (4-6星)
  // 40000  = 约11小时
}
```

**响应**: `NormalGachaResponse` (继承 `PlayerDeltaResponse`)

```json
{
  "result": 0,
  "playerDataDelta": { ... }
}
```

### 1.2 完成招募

**ServiceCode**: `/gacha/finishNormalGacha`

**请求**: `FinishNormalGachaRequest`

```json
{
  "slotId": 0                        // 招募槽位
}
```

**响应**: `FinishNormalGachaResponse`

```json
{
  "result": 0,
  "charInstId": 12345,               // 获得的干员实例ID
  "charId": "char_002_amiya",        // 干员ID
  "isNew": false,                    // 是否为新干员
  "playerDataDelta": { ... }
}
```

### 1.3 刷新标签

**ServiceCode**: `/gacha/refreshTags`

**请求**: `RefreshTagsRequest`

```json
{
  "slotId": 0
}
```

### 1.4 加速招募

**ServiceCode**: `/gacha/speedUpNormalGacha`

```json
{
  "slotId": 0
}
```

---

## 二、寻访 (高级抽卡)

### 2.1 单次寻访

**ServiceCode**: `/gacha/advancedGacha`

**请求**: `AdvancedGachaRequest`

```json
{
  "poolId": "pool_001",              // 卡池ID
  "useTkt": "Diamond",               // 使用的票券类型
  // useTkt 枚举:
  // "None"              = -1  (无)
  // "Diamond"           = 0   (合成玉/至纯源石)
  // "SingleTicket"      = 1   (寻访凭证)
  // "TenTicket"         = 2   (十连寻访凭证)
  // "LimitSingle"       = 3   (限定寻访凭证)
  // "UseItem"           = 4   (使用指定物品)
  // "TenSingleTkt"      = 5   (10张单抽券)
  // "ClassicSingleTicket"  = 6  (经典寻访凭证)
  // "ClassicTenTicket"     = 7  (经典十连凭证)
  // "classicTenSingleTicket" = 8 (10张经典单抽券)
  // "CombineTenTicket"   = 9   (组合十连凭证)

  "itemId": ""                       // 物品ID (useTkt=UseItem时)
}
```

**响应**: `AdvancedGachaResponse`

```json
{
  "result": 0,                       // 0=成功
  "charGet": {
    "charInstId": 12345,             // 干员实例ID
    "charId": "char_002_amiya",      // 干员ID
    "isNew": true,                   // 是否为新干员
    "itemGet": [                     // 获得的物品
      {
        "id": "4001",
        "type": "GOLD",
        "count": 100
      }
    ],
    "potent": {                      // 潜能信息
      "delta": 1,                    // 潜能增量
      "now": 2                       // 当前潜能
    }
  },
  "playerDataDelta": { ... }
}
```

### 2.2 十连寻访

**ServiceCode**: `/gacha/tenAdvancedGacha`

**请求**: `TenAdvancedGachaRequest`

```json
{
  "poolId": "pool_001",
  "useTkt": "TenTicket"              // 通常使用十连凭证或合成玉
}
```

**响应**: `TenAdvancedGachaResponse`

```json
{
  "result": 0,
  "charGet": [                       // 10个结果
    {
      "charInstId": 12345,
      "charId": "char_002_amiya",
      "isNew": true,
      "itemGet": [],
      "potent": { "delta": 1, "now": 1 }
    }
    // ... 共10个
  ],
  "playerDataDelta": { ... }
}
```

### 2.3 获取卡池详情

**ServiceCode**: `/gacha/getPoolDetail`

**请求**: `GetDetailGachaRequest`

```json
{
  "poolId": "pool_001",
  "gachaObjGroupType": "NORMAL"      // 卡池对象组类型
}
```

**响应**: `GetDetailGachaResponse`

```json
{
  "detailInfo": {
    "poolId": "pool_001",
    "poolName": "限定寻访",
    "startTime": "2024-01-01T00:00:00Z",
    "endTime": "2024-02-01T00:00:00Z",
    "rateUpChars": [                 // UP干员
      {
        "charId": "char_002_amiya",
        "rarity": 5,
        "rate": 0.5                  // UP概率
      }
    ],
    "lmtGacha": { ... }              // 限定信息 (如果是限定池)
  },
  "gachaObjGroupType": "NORMAL",
  "hasRateUp": true
}
```

### 2.4 选择 UP 池

**ServiceCode**: `/gacha/choosePoolUp`

```json
{
  "poolId": "pool_001",
  "charId": "char_002_amiya"         // 选择的UP干员 (双UP池时)
}
```

---

## 三、凭证兑换

### 3.1 凭证寻访

**ServiceCode**: `/depot/voucherGacha`

```json
{
  "voucherId": "voucher_001",
  "count": 1
}
```

### 3.2 使用选择券

**ServiceCode**: `/depot/useOptionVoucher`

```json
{
  "voucherId": "voucher_001",
  "charId": "char_002_amiya"         // 选择的干员
}
```

---

## 四、数据结构

### GachaResult

```json
{
  "charInstId": 12345,               // 干员实例ID
  "charId": "char_002_amiya",        // 干员ID
  "isNew": true,                     // 是否为新干员
  "itemGet": [                       // 额外获得的物品 (潜能溢出转碎片等)
    {
      "id": "4001",
      "type": "GOLD",
      "count": 100
    }
  ],
  "potent": {                        // 潜能信息
    "delta": 1,                      // 本次增加的潜能
    "now": 2                         // 当前潜能等级
  }
}
```

### GachaType 枚举

| 值 | 名称 | 说明 |
|----|------|------|
| -1 | None | 无 |
| 0 | Diamond | 合成玉/至纯源石 |
| 1 | SingleTicket | 寻访凭证 |
| 2 | TenTicket | 十连寻访凭证 |
| 3 | LimitSingle | 限定寻访凭证 |
| 4 | UseItem | 使用指定物品 |
| 5 | TenSingleTkt | 10张单抽券 |
| 6 | ClassicSingleTicket | 经典寻访凭证 |
| 7 | ClassicTenTicket | 经典十连凭证 |
| 8 | classicTenSingleTicket | 10张经典单抽券 |
| 9 | CombineTenTicket | 组合十连凭证 |
