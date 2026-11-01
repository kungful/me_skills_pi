# 企业知识库问答系统（部署版） 中文快速上手

## 0. 前置
Docker + docker compose v2。检查：`docker compose version`

## 1. 三步启动
```bash
cd deploy
cp .env.example .env      # 按需改端口/密钥
./install.sh
```

## 2. 验证
浏览器打开 `http://<你的IP>:8080`，能出界面即成功。

## 3. 常见报错
| 现象 | 原因 | 处理 |
|---|---|---|
| 端口被占用 | 8080 被别的服务占了 | 改 `.env` 的 PORT |
| 容器起不来 | 内存不足/架构不匹配 | `docker compose logs` 看第一行错误 |
| 页面 502 | 服务还在初始化 | 等 30–60 秒再看日志 |
| 拉镜像失败 | 网络/代理 | 配镜像加速或手动导入 |

## 4. 备份
`docker compose down` 前把 `data/` 整个目录复制走即可；恢复反过来。

## 5. 升级
```bash
docker compose pull && docker compose up -d
```
升级前先备份；大版本升级看上游 CHANGELOG。
