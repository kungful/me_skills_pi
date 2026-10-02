# grsai Nano Banana — 旧版 API 文档（原文）

## 节点信息

| Host | 地址 |
|---|---|
| 海外 | `https://grsaiapi.com` |
| 国内直连 | `https://grsai.dakka.com.cn` |

使用方式：Host + 接口，例如 `https://grsai.dakka.com.cn/v1/draw/nano-banana`

## 支持 Gemini 官方接口格式

基础地址替换为 Grsai 的地址，模型名称 `gemini-2.5-flash-image` 改为 `nano-banana-fast`。

```
https://grsai.dakka.com.cn/v1beta/models/nano-banana-fast:generateContent
```

## Nano Banana 绘画接口

`POST /v1/draw/nano-banana`

响应方式：stream 或 回调接口

### 请求头 Headers

```json
{
  "Content-Type": "application/json",
  "Authorization": "Bearer apikey"
}
```

### 请求参数 (JSON)

```json
{
  "model": "nano-banana-fast",
  "prompt": "提示词",
  "aspectRatio": "auto",
  "imageSize": "1K",
  "urls": [
    "https://example.com/example.png"
  ],
  "webHook": "https://example.com/callback",
  "shutProgress": false
}
```

| 参数 | 必填 | 类型 | 示例 | 描述 |
|---|---|---|---|---|
| model | 是 | string | `nano-banana-fast` | 支持模型：`nano-banana-2`、`nano-banana-2-cl`、`nano-banana-2-2k-cl`、`nano-banana-2-4k-cl`、`nano-banana-fast`、`nano-banana`、`nano-banana-pro`、`nano-banana-pro-vt`、`nano-banana-pro-cl`、`nano-banana-pro-vip`、`nano-banana-pro-4k-vip` |
| urls | 否 | array | `["https://example.com/example.png"]` | 参考图 URL 或 Base64 |
| prompt | 是 | string | `一只可爱的猫咪在草地上玩耍` | 提示词 |
| aspectRatio | 否 | string | `auto` | 默认 `auto`。支持：`auto`、`1:1`、`16:9`、`9:16`、`4:3`、`3:4`、`3:2`、`2:3`、`5:4`、`4:5`、`21:9`；`nano-banana-2`、`nano-banana-2-cl`、`nano-banana-2-2k-cl`、`nano-banana-2-4k-cl` 额外支持 `1:4`、`4:1`、`1:8`、`8:1` |
| imageSize | 否 | string | `1K` | 默认 `1K`。`nano-banana-2-cl` 只支持 1K，`nano-banana-2-2k-cl` 只支持 2K，`nano-banana-2-4k-cl` 只支持 4K，`nano-banana-pro`/`-vt` 支持 1K/2K/4K，`nano-banana-pro-cl` 只支持 1K，`nano-banana-pro-vip` 支持 1K/2K，`nano-banana-pro-4k-vip` 只支持 4K。注意：分辨率越高，生成时间越长 |
| webHook | 否 | string | `https://your-webhook-url.com/callback` | 进度与结果回调链接。默认以 Stream 流式响应；填写 webHook 后改为 POST 回调（`Content-Type: application/json`）。若不使用回调而想轮询 result 接口，填 `"-1"`，接口立即返回 id |
| shutProgress | 否 | boolean | `false` | 关闭进度回复，直接回复最终结果，建议搭配 webHook 使用。默认 `false` |

### webHook 提交结果（使用流式响应请跳过）

```json
{
  "code": 0,
  "msg": "success",
  "data": { "id": "id" }
}
```

| 字段 | 类型 | 描述 |
|---|---|---|
| code | number | 0 为成功 |
| msg | string | 状态信息 |
| data | object | 数据 |
| data.id | string | 程序任务 id，对应回调数据 |

### 响应参数（流式响应与 webHook 响应相同）

```json
{
  "id": "xxxxx",
  "results": [
    {
      "url": "https://example.com/example.png",
      "content": "这是一只可爱的猫咪在草地上玩耍"
    }
  ],
  "progress": 100,
  "status": "succeeded",
  "failure_reason": "",
  "error": ""
}
```

| 字段 | 类型 | 描述 |
|---|---|---|
| id | string | Id（webHook 回调可用该 id 对应数据） |
| results | array | 结果；`content` 回复内容，`url` 图片 URL（有效期 2 小时） |
| progress | number | 任务进度 0~100 |
| status | string | `running` 进行中 / `succeeded` 成功 / `failed` 失败 |
| failure_reason | string | `output_moderation` 输出违规 / `input_moderation` 输入违规 / `error` 其他错误 |
| error | string | 失败详细信息 |

提示：当触发 `error` 时，可尝试重新提交任务来确保系统稳定性。

## 获取结果接口

`POST /v1/draw/result`

### 请求参数

```json
{ "id": "xxxxx" }
```

### 响应结果

```json
{
  "code": 0,
  "data": {
    "id": "xxxxx",
    "results": [
      {
        "url": "https://example.com/example.png",
        "content": "这是一只可爱的猫咪在草地上玩耍"
      }
    ],
    "progress": 100,
    "status": "succeeded",
    "failure_reason": "",
    "error": ""
  },
  "msg": "success"
}
```

| 字段 | 类型 | 描述 |
|---|---|---|
| code | number | 0 成功，-22 任务不存在 |
| msg | string | 状态信息 |
| data | object | 绘画结果，格式同上 |
