# 通用数据结构定义

## 一、请求/响应基础结构

### Request 结构体

```csharp
public struct Request
{
    string serviceCode;                      // 服务码
    IMsgBundle body;                         // 消息体
    string overrideUrl;                      // 可选URL覆盖
    bool isRetry;                            // 是否重试
    Dictionary<string, string> header;       // 额外请求头
    bool isGameService { get; }              // 是否游戏服务
}
```

### Response<T> 结构体

```csharp
public struct Response<T>
{
    ResponseStatus status;                   // 响应状态
    ResponseError error;                     // 错误信息
    RespMsgBundle<T> body;                   // 响应体
}
```

### ResponseStatus 枚举

| 值 | 名称 | 含义 |
|----|------|------|
| 0 | OK | 成功 |
| 1 | ERROR_IGNORE | 忽略错误 |
| 2 | ERROR_RETRY | 需要重试 |
| 3 | ERROR_SYNC_DATA | 需要同步数据 |
| 4 | ERROR_RELOGIN | 需要重新登录 |
| 5 | ERROR_TIMEOUT | 超时 |
| 6 | ERROR_CLIENT | 客户端错误 |
| 7 | CANCEL | 取消 |
| 8 | ERROR_SECURE_SYS | 安全系统错误 |
| 9 | ERROR_UNKNOW | 未知错误 |

### ResponseError 结构体

```json
{
  "statusCode": 200,
  "error": "error_type",
  "message": "错误描述",
  "code": 0,
  "level": 0,
  "errorStatus": 0
}
```

---

## 二、物品系统

### ItemBundle

```json
{
  "id": "4001",                      // 物品ID
  "type": "GOLD",                    // 物品类型
  "count": 100                       // 数量
}
```

### ItemType 枚举

| 值 | 说明 |
|----|------|
| NONE | 无 |
| CHAR | 干员 |
| CARD | 招聘许可 |
| SKIN | 皮肤 |
| FURN | 家具 |
| GOLD | 龙门币 |
| DIAMOND | 至纯源石 |
| SHD | 合成玉 |
| EXP | 经验 |
| MATERIAL | 材料 |
| ITEM | 通用物品 |
| GACHA_TICKET | 寻访凭证 |
| RECRUIT_LICENSE | 招聘许可 |
| SOCIAL_POINT | 信用点 |
| HGG_SHOP_COIN | 高级凭证 |
| LGG_SHOP_COIN | 资质凭证 |
| EPG_SHOP_COIN | 模组数据块 |

### RewardModel

```json
{
  "id": "4001",
  "type": "GOLD",
  "count": 100,
  "charGet": {                       // 如果是干员
    "charInstId": 12345,
    "charId": "char_002_amiya",
    "isNew": true,
    "itemGet": [],
    "potent": { "delta": 1, "now": 1 }
  }
}
```

---

## 三、干员相关

### 干员实例 (CharacterData)

```json
{
  "instId": 12345,                   // 实例ID
  "charId": "char_002_amiya",        // 干员ID
  "level": 90,                       // 等级
  "exp": 0,                          // 经验
  "evolvePhase": 2,                  // 精英化阶段 (0/1/2)
  "favorPoint": 20000,               // 信赖值
  "potentialRank": 6,                // 潜能等级 (1-6)
  "mainSkillLvl": 7,                 // 主技能等级 (1-7)
  "skills": [                        // 技能
    {
      "skillId": "skchr_amiya_1",
      "unlock": 1,                   // 是否解锁
      "state": 0,
      "specializeLevel": 3,          // 专精等级 (0-3)
      "completeUpgradeTime": 0
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

### 编队槽位 (SquadSlot)

```json
{
  "charInstId": 12345,               // 干员实例ID (0=空位)
  "skillIndex": 2,                   // 技能索引
  "currentTmpl": "",                 // 当前模板
  "currentEquip": "equip_001"        // 当前模组
}
```

---

## 四、战斗相关

### 战斗类型 (BattleType)

| 值 | 说明 |
|----|------|
| COMMON | 普通战斗 |
| CONTINUOUS | 连续战斗 |
| MULTIPLE | 多次战斗 |

### 战斗结果

```json
{
  "result": 1,                       // 1=胜利, 0=失败
  "battleId": "battle_unique_id",
  "stageId": "stage_id",
  "completeTime": 1234567890,
  "data": "encrypted_battle_data"
}
```

---

## 五、货币类型

| ID | 名称 | 说明 |
|----|------|------|
| 4001 | GOLD | 龙门币 |
| 4002 | DIAMOND | 至纯源石 |
| 4003 | SHD | 合成玉 |
| 4004 | EXP_PLAYER | 经验 |
| 4005 | TKT_GACHA | 寻访凭证 |
| 4006 | TKT_RECRUIT | 招聘许可 |
| 4007 | SOCIAL_POINT | 信用点 |
| 4008 | HGG_SHOP_COIN | 高级凭证 (黄票) |
| 4009 | LGG_SHOP_COIN | 资质凭证 (绿票) |

---

## 六、时间格式

所有时间使用 Unix 时间戳 (秒) 或 ISO 8601 格式:

```json
{
  "timestamp": 1234567890,           // Unix 时间戳 (秒)
  "datetime": "2024-01-01T00:00:00Z" // ISO 8601
}
```

---

## 七、错误处理

### 服务端业务错误

```json
{
  "statusCode": 200,
  "result": {
    "error": "NOT_ENOUGH_AP",
    "message": "理智不足",
    "code": 1001
  }
}
```

### 常见业务错误码

| 错误码 | 说明 |
|--------|------|
| 0 | 成功 |
| 1 | 通用错误 |
| 1001 | 理智不足 |
| 1002 | 龙门币不足 |
| 1003 | 至纯源石不足 |
| 1004 | 合成玉不足 |
| 1005 | 物品不足 |
| 2001 | 干员不存在 |
| 2002 | 干员等级已满 |
| 2003 | 干员已精英化 |
| 3001 | 关卡未解锁 |
| 3002 | 关卡已完成 |
| 4001 | 好友已满 |
| 4002 | 已是好友 |
| 5001 | 商品已售罄 |
| 5002 | 限购已达上限 |
| 6001 | 验证码错误 |
| 6002 | 账号或密码错误 |

---

## 八、JSON 序列化配置

游戏使用 Newtonsoft.Json 序列化，配置如下:

```csharp
// 序列化设置
JsonSerializerSettings settings = new JsonSerializerSettings
{
    NullValueHandling = NullValueHandling.Ignore,      // 忽略 null 值
    DefaultValueHandling = DefaultValueHandling.Ignore, // 忽略默认值
    ContractResolver = new CamelCasePropertyNamesContractResolver()  // 驼峰命名
};

// 特殊转换器
[JsonConverter(typeof(BoolToIntJsonConverter))]  // bool -> int
[JsonProperty("skillIndex")]                    // 指定属性名
```

---

## 九、网络配置

### LoginInfo

```json
{
  "uid": "user_uid",
  "secret": "auth_token",
  "serviceLicenseVersion": 1,
  "majorVersion": "1.0.0"
}
```

### 请求头

```json
{
  "Content-Type": "application/json",
  "uid": "user_uid",
  "secret": "auth_token",
  "seqNum": 12345,                   // 请求序列号
  "platform": "android",            // 平台
  "version": "1.0.0",               // 客户端版本
  "deviceId": "device_id"           // 设备ID
}
```

### 服务器 URL 配置

```json
{
  "gs": "https://game.arknights.com",           // 游戏服务器
  "as": "https://sdk.arknights.com",            // SDK服务器
  "u8": "https://u8.arknights.com",             // U8服务器
  "hu": "https://update.arknights.com",         // 热更新
  "an": "https://announce.arknights.com"        // 公告
}
```
