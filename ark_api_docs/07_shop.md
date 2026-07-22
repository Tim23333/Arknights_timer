# 商店/支付接口

## 一、时装商店

### 1.1 获取时装列表

**ServiceCode**: `shop/getSkinGoodList`

**响应**:

```json
{
  "skinList": [
    {
      "goodId": "skin_001",
      "skinId": "char_002_amiya#1",
      "charId": "char_002_amiya",
      "price": 18,                   // 价格 (源石)
      "currencyType": "DIAMOND",
      "startTime": "2024-01-01T00:00:00Z",
      "endTime": "2024-02-01T00:00:00Z"
    }
  ],
  "playerDataDelta": { ... }
}
```

### 1.2 购买时装

**ServiceCode**: `shop/buySkinGood`

**请求**: `ShopBuySkinGoodRequest`

```json
{
  "goodId": "skin_001"
}
```

**响应**: `ShopBuySkinGoodResponse`

```json
{
  "result": 0,
  "playerDataDelta": { ... }
}
```

---

## 二、源石商店

### 2.1 获取源石商品列表

**ServiceCode**: `shop/getCashGoodList`

**响应**: `ShopCashGoodListResponse`

```json
{
  "goodList": [
    {
      "productId": "com.hypergryph.arknights.diamond1",
      "productName": "至纯源石×6",
      "price": 6.00,
      "currency": "CNY",
      "diamondCount": 6,
      "bonusCount": 0,               // 首充赠送
      "boughtTimes": 0,              // 已购买次数
      "limitTimes": 0,               // 限购次数 (0=无限)
      "items": [],                   // 额外物品
      "checkInItems": []             // 签到物品
    }
  ],
  "playerDataDelta": { ... }
}
```

### 2.2 购买源石

**ServiceCode**: `shop/buyCashGood`

**请求**: `ShopCashGoodPurchaseRequest` (空请求)

```json
{}
```

**响应**: `ShopCashGoodPurchaseResponse`

```json
{
  "receiveCashGoodResult": [
    {
      "productId": "com.hypergryph.arknights.diamond1",
      "productName": "至纯源石×6",
      "items": [
        {
          "id": "4002",
          "type": "DIAMOND",
          "count": 6
        }
      ],
      "checkInItems": []
    }
  ],
  "playerDataDelta": { ... }
}
```

---

## 三、高级商店 (信用商店/绿票商店/黄票商店)

### 3.1 获取高级商品列表

**ServiceCode**: `shop/getHighGoodList`

**响应**:

```json
{
  "goodList": [
    {
      "goodId": "high_001",
      "itemId": "item_001",
      "price": 100,
      "priceType": "CREDIT",         // 货币类型
      // "CREDIT"    - 信用
      // "GREENCERT" - 绿票 (资质凭证)
      // "GOLDCERT"  - 黄票 (高级凭证)
      // "TOKEN"     - 代币
      "boughtTimes": 0,
      "limitTimes": 1,               // 限购次数
      "slot": 0                      // 槽位
    }
  ],
  "playerDataDelta": { ... }
}
```

### 3.2 购买高级商品

**ServiceCode**: `shop/buyHighGood`

```json
{
  "goodId": "high_001",
  "count": 1
}
```

---

## 四、家具商店

### 4.1 获取家具商品列表

**ServiceCode**: `shop/getFurniGoodList`

### 4.2 购买家具

**ServiceCode**: `shop/buyFurniGood`

```json
{
  "goodId": "furni_001",
  "count": 1
}
```

---

## 五、礼包商店

### 5.1 获取礼包列表

**ServiceCode**: `shop/getPackageGoodList`

### 5.2 购买礼包

**ServiceCode**: `shop/buyPackageGood`

```json
{
  "goodId": "package_001"
}
```

---

## 六、限时商店

### 6.1 获取限时商品列表

**ServiceCode**: `shop/getLimitGoodList`

### 6.2 购买限时商品

**ServiceCode**: `shop/buyLimitGood`

```json
{
  "goodId": "limit_001",
  "count": 1
}
```

---

## 七、支付系统

### 7.1 创建订单 (Android/通用)

**ServiceCode**: `/pay/createOrder`

**请求**: `PayCreateOrderRequest`

```json
{
  "storeId": 1,                      // 商店ID
  "goodId": "good_001"               // 商品ID
}
```

**响应**: `PayCreateOrderResponse`

```json
{
  "result": 0,
  "orderId": "order_unique_id",      // 订单ID
  "extension": "pay_extension_data", // 支付扩展数据
  "orderIdList": [],                 // 订单ID列表
  "alertMinor": false,               // 是否提醒未成年人
  "errMsg": ""                       // 错误信息
}
```

### 7.2 创建订单 (iOS App Store)

**ServiceCode**: `/pay/createOrderAppstore`

**请求**: `PayCreateOrderAppstoreRequest`

```json
{
  "storeId": 2,
  "goodId": "good_001"
}
```

### 7.3 确认订单

**ServiceCode**: `/pay/confirmOrder`

**请求**: `PayConfirmOrderRequest`

```json
{
  "orderId": "order_unique_id",
  "extension": "payment_result_data" // 支付结果数据
}
```

### 7.4 确认订单 (iOS)

**ServiceCode**: `/pay/confirmOrderAppstoreNew`

```json
{
  "orderId": "order_unique_id",
  "receipt": "appstore_receipt"      // App Store 收据
}
```

### 7.5 获取未确认订单

**ServiceCode**: `/pay/getUnconfirmedOrderIdList`

**响应**:

```json
{
  "orderIdList": ["order_1", "order_2"]
}
```

---

## 八、U8 SDK 支付接口

### 8.1 获取商品列表

**路径**: `pay/v1/get_all_product_list`

```json
{
  "worldId": "server_id"
}
```

**响应**:

```json
{
  "products": [
    {
      "productId": "product_001",
      "productName": "至纯源石×6",
      "price": 600,                  // 价格 (分)
      "currency": "CNY"
    }
  ]
}
```

### 8.2 创建订单

**路径**: `pay/order/v1/create`

```json
{
  "productId": "product_001",
  "serverId": "server_id",
  "roleId": "role_id",
  "token": "auth_token"
}
```

### 8.3 检查订单

**路径**: `pay/order/v1/check`

```json
{
  "orderId": "order_id"
}
```

### 8.4 确认订单状态

**路径**: `pay/order/v1/state`

```json
{
  "orderId": "order_id"
}
```

---

## 九、兑换码

### 9.1 使用兑换码

**ServiceCode**: `/code/useCode`

```json
{
  "code": "REDEEM_CODE_HERE"
}
```

---

## 十、数据结构

### RewardItemModel

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

### Good 结构

```json
{
  "goodId": "good_001",
  "itemId": "item_001",
  "price": 100,
  "priceType": "CREDIT",
  "count": 1,
  "boughtTimes": 0,
  "limitTimes": 0,
  "startTime": "2024-01-01T00:00:00Z",
  "endTime": "2024-02-01T00:00:00Z"
}
```
