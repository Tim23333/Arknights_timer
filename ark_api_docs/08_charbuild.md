# 角色养成接口

## 一、干员升级

**ServiceCode**: `/charBuild/upgradeChar`

**请求**: `UpgradeCharRequest`

```json
{
  "charInstId": 12345,               // 干员实例ID
  "exp": 10000,                      // 投入经验
  "itemId": "exp_card_001",          // 使用的经验卡ID (可选)
  "useStone": false                  // 是否使用源石
}
```

**响应**: `UpgradeCharResponse` (继承 `PlayerDeltaResponse`)

```json
{
  "result": 0,
  "playerDataDelta": { ... }
}
```

---

## 二、精英化

**ServiceCode**: `/charBuild/evolveChar`

**请求**: `EvolveCharRequest`

```json
{
  "charInstId": 12345,
  "evolvePhase": 1                   // 精英化阶段 (1=精英1, 2=精英2)
}
```

**响应**: `EvolveCharResponse`

```json
{
  "result": 0,
  "playerDataDelta": { ... }
}
```

---

## 三、技能升级

**ServiceCode**: `/charBuild/upgradeSkill`

**请求**: `UpgradeSkillRequest`

```json
{
  "charInstId": 12345,
  "skillIndex": 0,                   // 技能索引 (0/1/2)
  "targetLevel": 7                   // 目标等级
}
```

---

## 四、技能专精

**ServiceCode**: `/charBuild/upgradeSpecialization`

**请求**: `UpgradeSpecializationRequest`

```json
{
  "charInstId": 12345,
  "skillIndex": 0,                   // 技能索引
  "specializeLevel": 1               // 专精等级 (1/2/3)
}
```

---

## 五、潜能提升

**ServiceCode**: `/charBuild/boostPotential`

**请求**: `BoostPotentialRequest`

```json
{
  "charInstId": 12345,
  "potentialLevel": 2                // 目标潜能等级 (1-6)
}
```

---

## 六、模组系统

### 6.1 设置模组

**ServiceCode**: `/charBuild/setEquipment`

**请求**: `SetEquipmentRequest`

```json
{
  "charInstId": 12345,
  "equipId": "equip_001"             // 模组ID
}
```

### 6.2 升级模组

**ServiceCode**: `/charBuild/upgradeEquipment`

**请求**: `UpgradeEquipmentRequest`

```json
{
  "charInstId": 12345,
  "equipId": "equip_001",
  "targetLevel": 3                   // 目标等级 (1-3)
}
```

### 6.3 卸下模组

**ServiceCode**: `/charBuild/unequipEquipment`

```json
{
  "charInstId": 12345
}
```

---

## 七、皮肤系统

### 7.1 更换皮肤

**ServiceCode**: `/charBuild/changeCharSkin`

**请求**: `ChangeCharSkinRequest`

```json
{
  "charInstId": 12345,
  "skinId": "char_002_amiya#1"       // 皮肤ID
}
```

### 7.2 获取已拥有皮肤

**ServiceCode**: `/charBuild/getOwnedSkins`

```json
{}
```

---

## 八、信赖系统

### 8.1 获取信赖详情

**ServiceCode**: `/charBuild/getTrustInfo`

```json
{
  "charInstId": 12345
}
```

---

## 九、干员模板 (阿米娅等多形态)

### 9.1 切换模板

**ServiceCode**: `/charBuild/changeTemplate`

```json
{
  "charInstId": 12345,
  "templateId": "tmpl_002"           // 模板ID
}
```

---

## 十、批量操作

### 10.1 批量升级

**ServiceCode**: `/charBuild/batchUpgrade`

```json
{
  "charInstId": 12345,
  "targetLevel": 90,
  "useItems": [
    {
      "itemId": "exp_card_001",
      "count": 10
    }
  ]
}
```

---

## 十一、数据结构

### 干员实例数据

```json
{
  "instId": 12345,                   // 实例ID
  "charId": "char_002_amiya",        // 干员ID
  "level": 90,                       // 等级
  "exp": 0,                          // 当前经验
  "evolvePhase": 2,                  // 精英化阶段
  "favorPoint": 20000,               // 信赖值
  "potentialRank": 6,                // 潜能等级
  "mainSkillLvl": 7,                 // 主技能等级
  "skills": [                        // 技能列表
    {
      "skillId": "skchr_amiya_1",
      "unlock": 1,                   // 是否解锁
      "state": 0,                    // 状态
      "specializeLevel": 3,          // 专精等级
      "completeUpgradeTime": 0       // 专精完成时间
    }
  ],
  "equip": {                         // 模组
    "equipId": "equip_001",
    "level": 3,
    "locked": false
  },
  "currentSkin": "char_002_amiya#1", // 当前皮肤
  "voiceLan": "CN",                  // 语音语言
  "tmpl": {                          // 模板 (多形态干员)
    "currentTmpl": "tmpl_001",
    "templates": { ... }
  }
}
```

### 经验需求表

| 等级 | 经验需求 |
|------|----------|
| 1→30 | 15,000 |
| 30→40 | 30,000 |
| 40→50 | 60,000 |
| 50→60 | 120,000 |
| 60→70 | 240,000 |
| 70→80 | 480,000 |
| 80→90 | 960,000 |

### 潜能提升消耗

| 潜能等级 | 消耗 |
|----------|------|
| 1→2 | 1个同干员/信物 |
| 2→3 | 1个同干员/信物 |
| 3→4 | 1个同干员/信物 |
| 4→5 | 1个同干员/信物 |
| 5→6 | 1个同干员/信物 |
