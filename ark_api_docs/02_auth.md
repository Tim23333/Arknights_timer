# 认证体系

## 一、LoginInfo 结构

```csharp
public struct Networker.LoginInfo
{
    string uid;                      // 用户唯一标识
    string secret;                   // 认证密钥/token
    int serviceLicenseVersion;       // 服务许可版本号
    string majorVersion;             // 主版本号
}
```

所有游戏接口请求时，`uid` 和 `secret` 会通过请求头传递给服务端进行身份验证。

---

## 二、SDK 登录接口

### 2.1 密码登录

**ServiceCode**: `/user/login` (SDK 服务器)

**请求类**: `HGSDK.LoginParam`

```json
{
  "accout": "username",       // 账号 (注意: 源码拼写为 accout)
  "password": "password",     // 密码
  "message": "captcha_data"   // 验证码数据 (可选)
}
```

**响应**: `HGSDK.LoginResponse`

```json
{
  "result": 0,                // 0=成功
  "uid": "user_id",
  "token": "auth_token",
  "isAuthenticate": true,
  "isMinor": false            // 是否未成年
}
```

### 2.2 短信验证码登录

**ServiceCode**: `/user/loginBySmsCode`

**请求**: `HGSDK.SmsCodeLoginParam`

```json
{
  "phoneNumber": "13800138000",
  "code": "123456"
}
```

### 2.3 游客登录

**ServiceCode**: `/user/v1/guestLogin`

**请求**: 无参数

### 2.4 发送短信验证码

**ServiceCode**: `/user/sendSmsCode`

**请求**: `HGSDK.SendSmsCodeParam`

```json
{
  "phoneNumber": "13800138000",
  "act": 1                    // 操作类型 (1=登录, 2=注册, 3=换绑)
}
```

### 2.5 用户注册

**ServiceCode**: `/user/register`

**请求**: `HGSDK.RegisterParam`

```json
{
  "accout": "username",
  "password": "password",
  "phoneNumber": "13800138000",
  "code": "123456"            // 短信验证码
}
```

### 2.6 修改密码

**ServiceCode**: `/user/changePassword`

```json
{
  "oldPassword": "old_pwd",
  "newPassword": "new_pwd"
}
```

### 2.7 换绑手机

**ServiceCode**: `/user/changePhoneCheck` (验证原手机)

```json
{
  "code": "123456"            // 原手机验证码
}
```

**ServiceCode**: `/user/changePhone` (绑定新手机)

```json
{
  "phoneNumber": "new_phone",
  "code": "123456"            // 新手机验证码
}
```

---

## 三、实名认证

### 3.1 身份认证

**ServiceCode**: `/user/authenticateUserIdentity`

**请求**: `HGSDK.UserIdentityAuthParam`

```json
{
  "name": "真实姓名",
  "idCardNum": "身份证号"
}
```

### 3.2 身份证校验

**ServiceCode**: `/user/checkIdCard`

```json
{
  "idCardNum": "身份证号"
}
```

---

## 四、云认证流程

云认证用于防沉迷系统，流程如下:

### 4.1 检查是否需要云认证

**ServiceCode**: `/user/info/v1/need_cloud_auth`

**请求**: `NeedCloudAuthRequest`

```json
{
  "token": "auth_token"
}
```

### 4.2 发起云认证

**ServiceCode**: `/user/info/v1/cloud_auth`

**请求**: `CloudAuthRequest`

```json
{
  "token": "auth_token"
}
```

**响应**: `CloudAuthResponse`

```json
{
  "token": "cloud_token",
  "bizId": "business_id"
  // STATUS_NEED_AUTH = 100  需要认证
  // STATUS_TOO_OFTEN = 102  请求过于频繁
}
```

### 4.3 验证云认证结果

**ServiceCode**: `/user/info/v1/verify_cloud_auth_result`

**请求**: `VerifyCloudAuthRequest`

```json
{
  "token": "cloud_token",
  "bizId": "business_id"
}
```

**响应**: `VerifyCloudAuthResponse`

```json
{
  "verifyStatus": 0           // STATUS_AUTH_FAIL = 101 认证失败
}
```

---

## 五、OAuth2 授权

### 5.1 获取授权信息

**ServiceCode**: `/user/oauth2/v1/grant`

### 5.2 解绑授权

**ServiceCode**: `/user/oauth2/v1/unbind_grant`

---

## 六、U8 SDK 认证接口

U8 SDK 用于渠道服认证和支付。

### 6.1 通过渠道 Token 获取会话

**路径**: `user/auth/v2/token_by_channel_token`

```json
{
  "channelToken": "渠道token",
  "channelCode": "渠道代码"
}
```

### 6.2 OAuth2 授权

**路径**: `user/auth/v2/grant`

```json
{
  "code": "oauth2_code"
}
```

### 6.3 获取服务器列表

**路径**: `game/server/v1/server_list`

**响应**:

```json
{
  "servers": [
    {
      "serverId": "server_id",
      "serverName": "服务器名称",
      "serverDomain": "服务器域名",
      "roleId": "角色ID",
      "nickName": "昵称",
      "level": 120
    }
  ]
}
```

### 6.4 确认选择服务器

**路径**: `game/role/v1/confirm_server`

```json
{
  "serverId": "server_id",
  "roleId": "role_id"
}
```

### 6.5 获取 Token

**路径**: `user/v1/getToken`

---

## 七、游戏内登录

### 7.1 游戏登录

**ServiceCode**: `/account/login`

**请求**: `LoginRequest`

```json
{
  "platform": "platform_key",
  "deviceId": "device_id",
  "version": "client_version"
}
```

**响应**: `PlayerInitResponse`

```json
{
  "user": { ... },             // 完整用户数据 (JSON)
  "pushMessage": []
}
```

登录成功后，服务端返回的 `uid` 和 `token` 会通过 `Networker.InitLoginInfo()` 设置到网络层，后续所有请求自动携带。

---

## 八、心跳/在线

### 8.1 心跳检测

**ServiceCode**: `/online/v1/ping`

**请求**: `PingRequest`

```json
{
  "ts": 1234567890             // 时间戳
}
```

### 8.2 登出

**ServiceCode**: `/online/v1/loginout`

**请求**: `LoginoutRequest`

---

## 九、HGSDK APIV2 验证码机制

APIV2 接口支持验证码保护:

```csharp
public abstract class APIV2RequestBase
{
    JObject captcha;    // 验证码数据
    string token;       // 认证令牌
}

public abstract class APIV2ResponseBase
{
    // 状态码
    const int BUSINESS_SUC = 0;           // 成功
    const int NEED_CAPTCHA_STATUS = 1;    // 需要验证码
    const int CAPTCHA_AUTH_FAIELD = 4;    // 验证码验证失败
    const int INVALID_PHONE_CODE = 5;     // 无效的手机验证码

    JObject captcha;
}
```

当响应状态为 `NEED_CAPTCHA_STATUS` 时，客户端需要展示验证码，用户完成验证后将 `captcha` 数据附加到重试请求中。
