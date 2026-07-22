# 社交系统接口

## 一、好友系统

### 1.1 发送好友申请

**ServiceCode**: `/social/sendFriendRequest`

**请求**: `SendFriendRequestRequest`

```json
{
  "friendUid": "target_user_uid"     // 目标用户UID
}
```

### 1.2 处理好友申请

**ServiceCode**: `/social/processFriendRequest`

**请求**: `ProcessFriendRequestRequest`

```json
{
  "friendUid": "applicant_uid",
  "accept": true                     // true=接受, false=拒绝
}
```

### 1.3 删除好友

**ServiceCode**: `/social/deleteFriend`

**请求**: `DeleteFriendRequest`

```json
{
  "friendUid": "friend_uid"
}
```

### 1.4 获取好友列表

**ServiceCode**: `/social/getFriendList`

**响应**: `GetFriendListResponse`

```json
{
  "friendList": [
    {
      "uid": "friend_uid",
      "nickName": "昵称",
      "level": 120,
      "avatarId": "avatar_001",      // 头像ID
      "avatar": {                    // 头像详情
        "type": "ASSISTANT",
        "id": "char_002_amiya"
      },
      "lastOnlineTime": 1234567890,  // 最后在线时间
      "assistCharList": [            // 助战干员
        {
          "charId": "char_002_amiya",
          "level": 90,
          "evolvePhase": 2,
          "skillIndex": 2
        }
      ],
      "permit": 1,                   // 许可状态
      "canInvite": true              // 是否可邀请
    }
  ]
}
```

### 1.5 搜索玩家

**ServiceCode**: `/social/searchPlayer`

**请求**: `SearchPlayerRequest`

```json
{
  "searchId": "target_uid"           // 搜索的UID
}
```

**响应**: `SearchPlayerResponse`

```json
{
  "result": {
    "uid": "target_uid",
    "nickName": "昵称",
    "level": 120,
    "avatarId": "avatar_001",
    "avatar": { ... },
    "isFriend": false                // 是否已是好友
  }
}
```

### 1.6 获取好友申请列表

**ServiceCode**: `/social/getFriendRequestList`

**响应**:

```json
{
  "requestList": [
    {
      "uid": "applicant_uid",
      "nickName": "昵称",
      "level": 120,
      "requestTime": 1234567890
    }
  ]
}
```

### 1.7 获取黑名单

**ServiceCode**: `/social/getBlacklist`

### 1.8 添加黑名单

**ServiceCode**: `/social/addToBlacklist`

```json
{
  "uid": "target_uid"
}
```

### 1.9 移除黑名单

**ServiceCode**: `/social/removeFromBlacklist`

```json
{
  "uid": "target_uid"
}
```

---

## 二、名片系统

### 2.1 编辑名片

**ServiceCode**: `/businessCard/editNameCard`

**请求**: `EditNameCardRequest`

```json
{
  "nameCard": {
    "nickName": "我的昵称",
    "avatarId": "avatar_001",
    "avatar": {
      "type": "ASSISTANT",
      "id": "char_002_amiya"
    },
    "sign": "个性签名",              // 签名 (需要审核)
    "assistCharList": [              // 助战干员展示
      {
        "charId": "char_002_amiya",
        "skillIndex": 2,
        "skinId": "char_002_amiya#1"
      },
      {
        "charId": "char_1011_silverAsh",
        "skillIndex": 1,
        "skinId": ""
      },
      {
        "charId": "char_291_aglarm",
        "skillIndex": 0,
        "skinId": ""
      }
    ],
    "themeId": "theme_001",          // 主题ID
    "representMedal": { ... },       // 展示勋章
    "displayConfig": {               // 显示配置
      "showRarity": true,
      "showLevel": true
    }
  }
}
```

**响应**: `EditNameCardResponse` (继承 `ExaminResponse`)

```json
{
  "result": "SUCCESS",               // 审核结果
  "playerDataDelta": { ... }
}
```

### 2.2 获取他人名片

**ServiceCode**: `/businessCard/getOtherPlayerNameCard`

**请求**: `GetOtherPlayerNameCardRequest`

```json
{
  "otherUid": "target_uid"
}
```

**响应**: `GetOtherPlayerNameCardResponse`

```json
{
  "nameCard": { ... },               // 名片数据 (同上)
  "playerDataDelta": { ... }
}
```

### 2.3 获取好友名片列表

**ServiceCode**: `/businessCard/getFriendNameCardList`

```json
{}
```

---

## 三、助战系统

### 3.1 设置助战干员

在名片编辑中通过 `assistCharList` 字段设置。

### 3.2 获取助战干员详情

**ServiceCode**: `/social/getAssistCharDetail`

```json
{
  "uid": "friend_uid",
  "charInstId": 12345
}
```

---

## 四、邮件系统

### 4.1 获取邮件列表

**ServiceCode**: `/mail/listMailBox`

**请求**: `ListMailBoxRequest`

```json
{
  "type": "ALL"                      // 邮件类型
  // "ALL"     - 全部
  // "SYSTEM"  - 系统邮件
  // "FRIEND"  - 好友邮件
}
```

**响应**: `ListMailBoxResponse`

```json
{
  "mailList": [
    {
      "mailId": "mail_001",
      "type": "SYSTEM",
      "sender": "系统",
      "title": "邮件标题",
      "content": "邮件内容",
      "hasItem": true,               // 是否有附件
      "items": [                     // 附件列表
        {
          "id": "4001",
          "type": "GOLD",
          "count": 10000
        }
      ],
      "receiveTimestamp": 1234567890,
      "expireTimestamp": 1234567890,
      "isRead": false                // 是否已读
    }
  ],
  "playerDataDelta": { ... }
}
```

### 4.2 领取邮件附件

**ServiceCode**: `/mail/receiveMail`

**请求**: `ReceiveMailRequest`

```json
{
  "mailId": "mail_001"
}
```

**响应**: `ReceiveMailResponse`

```json
{
  "result": 0,
  "items": [                         // 领取的物品
    {
      "id": "4001",
      "type": "GOLD",
      "count": 10000
    }
  ],
  "playerDataDelta": { ... }
}
```

### 4.3 一键领取所有邮件

**ServiceCode**: `/mail/receiveAllMail`

**请求**: `ReceiveAllMailRequest`

```json
{
  "type": "ALL"                      // 邮件类型筛选
}
```

**响应**: `ReceiveAllMailResponse`

```json
{
  "result": 0,
  "mailList": [                      // 领取的邮件
    {
      "mailId": "mail_001",
      "items": [ ... ]
    }
  ],
  "playerDataDelta": { ... }
}
```

### 4.4 删除邮件

**ServiceCode**: `/mail/deleteMail`

```json
{
  "mailId": "mail_001"
}
```

### 4.5 标记已读

**ServiceCode**: `/mail/readMail`

```json
{
  "mailId": "mail_001"
}
```

---

## 五、数据结构

### 名片数据 (NameCard)

```json
{
  "nickName": "昵称",
  "avatarId": "avatar_001",
  "avatar": {
    "type": "ASSISTANT",
    "id": "char_002_amiya"
  },
  "sign": "签名",
  "assistCharList": [
    {
      "charId": "char_002_amiya",
      "skillIndex": 2,
      "skinId": "char_002_amiya#1"
    }
  ],
  "themeId": "theme_001",
  "representMedal": {
    "medalId": "medal_001",
    "template": "default"
  },
  "displayConfig": {
    "showRarity": true,
    "showLevel": true,
    "showSkin": true
  }
}
```

### 邮件数据 (Mail)

```json
{
  "mailId": "mail_001",
  "type": "SYSTEM",
  "sender": "发送者",
  "title": "标题",
  "content": "内容",
  "hasItem": false,
  "items": [],
  "receiveTimestamp": 1234567890,
  "expireTimestamp": 1234567890,
  "isRead": false
}
```

### 审核结果枚举 (ExaminResultType)

| 值 | 说明 |
|----|------|
| SUCCESS | 成功 |
| NEED_REVIEW | 需要审核 |
| REJECTED | 被拒绝 |
