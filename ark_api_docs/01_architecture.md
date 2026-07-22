# 网络架构总览

## 核心组件

### Networker 类 (行 1244635)

命名空间: `Torappu.Network`

单例模式的 MonoBehaviour，是整个网络通信的核心。

```csharp
// 关键字段
private Networker.LoginInfo m_loginInfo;    // 登录信息
private bool m_lastSeqNumFailed;            // 上一个序列号是否失败
private int m_seqNum;                       // 当前序列号
private int m_latestSucceedSeqNum;          // 最后成功的序列号

// 常量
public const string CONTENT_TYPE_JSON = "application/json";
public const string CONTENT_TYPE_IMG_JPEG = "image/jpeg";
public const string CONTENT_TYPE_MULTI_FORM = "multipart/form-data";
public const string CONTENT_ENCODING_GZIP = "gzip";
public const int GENERAL_TIMEOUT = 30;                    // 超时 30 秒
public const int LARGE_REQUEST_THRESHOLD = 61440;         // 大请求阈值 60KB
```

### 核心方法

```csharp
// 发送 JSON 请求
public RequestResult<T> SendRequest<T>(Request request)

// 发送 multipart 请求 (带文件)
public RequestResult<T> SendMultiFormRequest<T>(Request request, BinaryData[] binaryDatas)

// HTTP GET/POST
public WebHttpResult SendGet(string url, string param)
public WebHttpResult SendPost(string url, string param, string contentType)
public WebHttpResult SendPost(string url, string param, string contentType, Dictionary<string, string> header)

// 初始化登录信息
public void InitLoginInfo(Networker.LoginInfo loginInfo)
```

## 请求发送流程

```
1. UISender.SendRequest<T>(Request)           -- UI 层入口
2. Networker.SendRequest<T>(Request)          -- 发起协程
3. _RequestOnNextFrame<T>(...)                -- 下一帧执行
4. _GenerateRequestHeader(Request)            -- 生成请求头
5. _ParseServiceUrl(entry, serviceCode)       -- 拼接 URL
6. NetworkSecurity.SecureUrl(url, ...)        -- URL 安全处理
7. _SendPostCoroutine(url, param, ...)        -- 发送 POST 协程
8. _PostWithBestHttp(...) 或 _PostWithUnityWebRequest(...)
```

## 传输方式选择

| 条件 | 使用方式 |
|------|----------|
| 请求体 < 60KB | UnityWebRequest |
| 请求体 >= 60KB | BestHTTP |
| 需要重试 | BestHTTP |

## 错误码定义

| 错误码 | 含义 |
|--------|------|
| 10000 | 超时 |
| 10010 | 连接关闭 |
| 10020 | TLS 错误 |
| 20000 | 安全系统错误基准 |
| 30000 | 客户端错误基准 |

## ResponseStatus 枚举

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
