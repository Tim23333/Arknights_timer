# 邮件/任务接口

## 一、邮件系统

详见 `09_social.md` 中的"邮件系统"部分。

---

## 二、任务系统

### 2.1 获取任务列表

**ServiceCode**: `/mission/getMissionList`

**响应**:

```json
{
  "missions": {
    "DAILY": [                       // 每日任务
      {
        "missionId": "daily_001",
        "sortId": 1,
        "name": "完成3次作战",
        "description": "完成任意作战3次",
        "progress": 1,               // 当前进度
        "target": 3,                 // 目标值
        "state": "RUNNING",          // 状态
        // "RUNNING"    - 进行中
        // "COMPLETE"   - 已完成
        // "REWARDED"   - 已领奖
        "rewards": [                 // 奖励
          {
            "id": "4001",
            "type": "GOLD",
            "count": 10000
          }
        ]
      }
    ],
    "WEEKLY": [ ... ],               // 每周任务
    "MAIN": [ ... ],                 // 主线任务
    "ACTIVITY": [ ... ],             // 活动任务
    "ACHIEVEMENT": [ ... ]           // 成就
  },
  "playerDataDelta": { ... }
}
```

### 2.2 领取任务奖励

**ServiceCode**: `/mission/exchangeMissionRewards`

**请求**: `ExchangeMissionRewardsRequest`

```json
{
  "missionId": "daily_001"
}
```

**响应**: `ExchangeMissionRewardsResponse`

```json
{
  "result": 0,
  "rewards": [ ... ],
  "playerDataDelta": { ... }
}
```

### 2.3 确认任务

**ServiceCode**: `/mission/confirmMission`

**请求**: `ConfirmMissionRequest`

```json
{
  "missionId": "daily_001"
}
```

### 2.4 一键领取所有任务奖励

**ServiceCode**: `/mission/receiveAllMissionRewards`

**请求**:

```json
{
  "missionType": "DAILY"             // 任务类型
  // "DAILY"       - 每日任务
  // "WEEKLY"      - 每周任务
  // "MAIN"        - 主线任务
  // "ACTIVITY"    - 活动任务
  // "ACHIEVEMENT" - 成就
}
```

---

## 三、签到系统

### 3.1 获取签到信息

**ServiceCode**: `/activity/getCheckInInfo`

**响应**:

```json
{
  "checkInInfo": {
    "currentDay": 15,                // 当前签到天数
    "totalDays": 30,                 // 总天数
    "rewards": [                     // 奖励列表
      {
        "day": 1,
        "items": [ ... ],
        "received": true
      }
    ],
    "lastCheckInTime": 1234567890    // 上次签到时间
  }
}
```

### 3.2 签到

**ServiceCode**: `/activity/checkIn`

```json
{}
```

### 3.3 链式登录奖励

**ServiceCode**: `/activity/getChainLogInReward`

**请求**: `GetChainLogInRewardRequest`

```json
{
  "index": 0                         // 奖励索引
}
```

### 3.4 链式登录最终奖励

**ServiceCode**: `/activity/getChainLogInFinalRewards`

```json
{}
```

### 3.5 开服签到奖励

**ServiceCode**: `/activity/getOpenServerCheckInReward`

**请求**: `GetOpenServerCheckInRewardRequest`

```json
{
  "index": 0
}
```

---

## 四、活动系统

### 4.1 获取活动列表

**ServiceCode**: `/activity/getActivityList`

**响应**:

```json
{
  "activities": [
    {
      "activityId": "activity_001",
      "name": "活动名称",
      "type": "CHECK_IN",            // 活动类型
      "startTime": "2024-01-01T00:00:00Z",
      "endTime": "2024-02-01T00:00:00Z",
      "rewardEndTime": "2024-02-08T00:00:00Z",
      "state": "OPEN",
      "rewards": [ ... ]
    }
  ]
}
```

### 4.2 获取活动奖励

**ServiceCode**: `/activity/getActivityReward`

```json
{
  "activityId": "activity_001",
  "rewardId": "reward_001"
}
```

---

## 五、公告系统

### 5.1 获取公告列表

**ServiceCode**: `/announcement/getList`

**响应**:

```json
{
  "announcements": [
    {
      "announcementId": "ann_001",
      "title": "公告标题",
      "content": "公告内容",
      "type": "SYSTEM",              // 公告类型
      "startTime": "2024-01-01T00:00:00Z",
      "endTime": "2024-02-01T00:00:00Z",
      "isRead": false,
      "hasReward": false,
      "bannerId": "banner_001"
    }
  ]
}
```

### 5.2 标记公告已读

**ServiceCode**: `/announcement/read`

```json
{
  "announcementId": "ann_001"
}
```

---

## 六、数据结构

### 任务数据

```json
{
  "missionId": "daily_001",
  "sortId": 1,
  "name": "任务名称",
  "description": "任务描述",
  "type": "DAILY",
  "progress": 0,
  "target": 1,
  "state": "RUNNING",
  "rewards": [
    {
      "id": "4001",
      "type": "GOLD",
      "count": 10000
    }
  ],
  "startTime": "2024-01-01T00:00:00Z",
  "endTime": "2024-02-01T00:00:00Z"
}
```

### 任务状态枚举

| 值 | 说明 |
|----|------|
| RUNNING | 进行中 |
| COMPLETE | 已完成 (可领奖) |
| REWARDED | 已领奖 |

### 任务类型枚举

| 值 | 说明 |
|----|------|
| DAILY | 每日任务 |
| WEEKLY | 每周任务 |
| MAIN | 主线任务 |
| SIDE | 支线任务 |
| ACTIVITY | 活动任务 |
| ACHIEVEMENT | 成就 |
| OPEN_SERVER | 开服任务 |
