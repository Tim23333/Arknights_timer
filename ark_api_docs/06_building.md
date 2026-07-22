# 基建系统接口

## 一、数据同步

**ServiceCode**: `building/sync`

**请求**: `BuildingSyncRequest`

```json
{}
```

**响应**: `BuildingSyncResponse` (继承 `PlayerDeltaResponse`)

```json
{
  "playerDataDelta": {
    "building": {
      "rooms": { ... },              // 房间数据
      "chars": { ... },              // 干员分配
      "manufacture": { ... },        // 制造站
      "trading": { ... },            // 贸易站
      "workshop": { ... },           // 加工站
      "hire": { ... },               // 人力办公室
      "dormitory": { ... },          // 宿舍
      "control": { ... },            // 控制中心
      "meeting": { ... }             // 会客室
    }
  }
}
```

---

## 二、房间管理

### 2.1 建造房间

**ServiceCode**: `building/buildRoom`

**请求**: `BuildingBuildRoomRequest`

```json
{
  "slotId": "slot_3_2",              // 房间槽位ID
  "roomId": "room_manufacture",      // 房间类型ID
  "level": 1                         // 初始等级
}
```

### 2.2 升级房间

**ServiceCode**: `building/upgradeRoom`

**请求**: `BuildingUpgradeRoomRequest`

```json
{
  "slotId": "slot_3_2"               // 房间槽位ID
}
```

### 2.3 降级房间

**ServiceCode**: `building/degradeRoom`

**请求**: `BuildingDegradeRoomRequest`

```json
{
  "slotId": "slot_3_2"
}
```

### 2.4 清理房间

**ServiceCode**: `building/cleanRoom`

**请求**: `BuildingCleanRoomRequest`

```json
{
  "slotId": "slot_3_2"
}
```

---

## 三、干员分配

### 3.1 分配干员

**ServiceCode**: `building/assignChar`

**请求**: `BuildingAssignCharRequest`

```json
{
  "slotId": "slot_3_2",              // 房间槽位
  "charInstId": 12345,               // 干员实例ID
  "index": 0                         // 位置索引 (宿舍等多位置房间)
}
```

### 3.2 批量分配

**ServiceCode**: `building/assignAllChar`

```json
{
  "assignments": [
    {
      "slotId": "slot_3_2",
      "charInstId": 12345,
      "index": 0
    }
  ]
}
```

---

## 四、制造站

### 4.1 收取制造产物

**ServiceCode**: `building/settleManufacture`

**请求**: `BuildingSettleManufactRequest`

```json
{
  "slotId": "slot_3_2"               // 制造站槽位
}
```

### 4.2 更换制造配方

**ServiceCode**: `building/changeManufactureSolution`

**请求**: `BuildingChangeManufactRequest`

```json
{
  "slotId": "slot_3_2",
  "solutionId": "solution_001"       // 配方ID
}
```

---

## 五、贸易站

### 5.1 收取订单

**ServiceCode**: `building/settleSale`

**请求**: `BuildingSettleSaleRequest`

```json
{
  "slotId": "slot_3_2"
}
```

### 5.2 交付订单

**ServiceCode**: `building/tradingDelivery`

**请求**: `BuildingTradingDeliveryRequest`

```json
{
  "slotId": "slot_3_2",
  "orderId": "order_001"             // 订单ID
}
```

### 5.3 更换贸易策略

**ServiceCode**: `building/changeSaleSolution`

```json
{
  "slotId": "slot_3_2",
  "solutionId": "solution_001"
}
```

### 5.4 更换订单策略

**ServiceCode**: `building/tradingChangeStrategy`

```json
{
  "slotId": "slot_3_2",
  "strategy": "ORDER_STRATEGY"       // 策略类型
}
```

---

## 六、加工站

### 6.1 合成

**ServiceCode**: `building/workshopSynthesis`

**请求**: `BuildingWorkshopSynthesisRequest`

```json
{
  "formulaId": "formula_001",        // 合成公式ID
  "count": 1                         // 合成数量
}
```

### 6.2 分解

**ServiceCode**: `building/workshopDecomposition`

```json
{
  "itemId": "item_001",
  "count": 1
}
```

---

## 七、宿舍

### 7.1 安排休息

**ServiceCode**: `building/setRest`

```json
{
  "slotId": "slot_dorm_1",
  "charInstIds": [12345, 67890]      // 干员实例ID列表
}
```

---

## 八、会客室

### 8.1 发送线索

**ServiceCode**: `building/sendClue`

```json
{
  "friendUid": "friend_uid",
  "clueId": "clue_001"
}
```

### 8.2 放置线索

**ServiceCode**: `building/putClueToTheBoard`

```json
{
  "clueId": "clue_001",
  "position": 0                      // 位置 (0-6)
}
```

### 8.3 开始信息共享

**ServiceCode**: `building/startInfoShare`

```json
{}
```

### 8.4 领取信息共享奖励

**ServiceCode**: `building/getInfoShareReward`

```json
{}
```

---

## 九、人力办公室

### 9.1 开始招聘

**ServiceCode**: `building/startHire`

```json
{
  "slotId": "slot_hire_1",
  "tagList": [1, 5, 12]             // 标签列表
}
```

### 9.2 刷新招聘标签

**ServiceCode**: `building/refreshHire`

```json
{
  "slotId": "slot_hire_1"
}
```

---

## 十、家具

### 10.1 购买家具

**ServiceCode**: `building/buyFurnitureGood`

**请求**: `BuildingBuyFurnitureGoodRequest`

```json
{
  "goodId": "furni_001",
  "count": 1
}
```

### 10.2 布置家具

**ServiceCode**: `building/changeFurniture`

```json
{
  "slotId": "slot_dorm_1",
  "furnitureLayout": { ... }         // 家具布局数据
}
```

---

## 十一、基建技能

### 11.1 专精基建技能

**ServiceCode**: `building/upgradeSpecialization`

```json
{
  "charInstId": 12345,
  "skillIndex": 0                    // 基建技能索引
}
```
