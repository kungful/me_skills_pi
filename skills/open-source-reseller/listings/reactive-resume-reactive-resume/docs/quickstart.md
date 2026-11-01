# 私人简历生成站（部署版） · 中文快速上手

> 基于开源项目 Reactive Resume（MIT）做的部署/汉化/答疑包。上游文档：`docs/self-hosting/docker.mdx`

## 0. 前置（先自查，能省一次返工）

```bash
docker --version          # 20.10+
docker compose version    # v2（带 - 的 v1 不行）
docker info               # 有输出说明引擎在跑（Docker Desktop 要点开）
```

资源：1 vCPU / 1 GB 只跑应用；数据库同机建议 2 GB 内存，磁盘 10 GB 起。

## 1. 三步启动

```bash
cd deploy
bash install.sh
```

`install.sh` 会自动从 `.env.example` 生成 `.env`（随机数据库密码 + AUTH_SECRET），
然后 `docker compose up -d --wait`，等两个容器都 healthy 才返回。

想手动做也行：

```bash
cp .env.example .env
# 编辑 .env：APP_URL、POSTGRES_PASSWORD、DATABASE_URL 里的密码要一致、AUTH_SECRET 用 openssl rand -hex 32
docker compose up -d --wait --wait-timeout 300
```

## 2. 验证（三个都得过）

1. `docker compose ps` → postgres 和 reactive-resume 都是 `healthy`
2. 浏览器打开 `http://localhost:3000`（或你 `.env` 里的 APP_URL）能出首页
3. 注册一个账号 → 建一份简历 → 导出 PDF 成功

## 3. 首次必做

- 自己账号建好后，`.env` 加 `FLAG_DISABLE_SIGNUPS="true"`，再 `docker compose up -d`，别人就注册不了
- `APP_URL` 必须和浏览器地址栏一模一样（含 `https://`），否则登录会跳错、cookie 不生效
- 要发验证邮件再配 `SMTP_*`；不配的话验证链接只打在日志里：
  `docker compose logs reactive-resume | grep verify-email`

## 4. 常见报错（照这个表查，90% 在这）

| 现象 | 原因 | 处理 |
|---|---|---|
| `docker: command not found` | 没装 Docker | 装 Docker Engine / Docker Desktop |
| `docker info` 报 500 或 pipe 不存在 | Docker Desktop 没起完 | 等它转完；Windows 上等托盘图标变绿 |
| 容器反复重启，日志 `wrong DATABASE_URL` | 密码对不上或库还没起 | `POSTGRES_PASSWORD` 与 `DATABASE_URL` 里密码必须一致；`depends_on: service_healthy` 别删 |
| 日志说 `/app/data` 不可写 | volume 权限 | 删掉 volume 重来：`docker compose down -v && docker compose up -d` |
| 打开 502/连接被拒 | 应用还在跑迁移 | 首次启动要 1–3 分钟，`docker compose logs -f reactive-resume` 等 "listening" |
| 登录后立刻退回登录页 | `APP_URL` 和实际地址不一致 | 改 `.env` 的 `APP_URL` 再 `docker compose up -d` |
| 拉镜像超时 | 网络 | 换 `ghcr.io/reactive-resume/reactive-resume:latest`，或配镜像加速 |
| 端口 3000 被占 | 本机已有服务 | 改 compose 的 `ports: "8080:3000"`，同时改 `APP_URL` |

## 5. 备份 / 恢复

数据在两处：`postgres_data`（账号和简历）和 `reactive_resume_data`（上传的图片）。

```bash
# 备份（数据库导出更稳，不用停服务）
docker compose exec -T postgres pg_dump -U postgres postgres > backup-$(date +%F).sql
docker run --rm -v reactive_resume_data:/d -v "$PWD":/b alpine tar czf /b/uploads-$(date +%F).tgz -C /d .

# 恢复
cat backup-2026-11-01.sql | docker compose exec -T postgres psql -U postgres -d postgres
```

## 6. 升级

```bash
docker compose pull && docker compose up -d
```

启动时会自动跑数据库迁移。要稳就固定小版本：image 用 `amruthpillai/reactive-resume:v6`。
跨大版本升级前先备份 + 读 `docs/self-hosting/upgrading-to-v6.mdx`。

## 7. 售后边界（商品页也这么写）

- 含：部署跑通、中文说明、7 天内环境问题免费修、1 次与原始需求一致的修改
- 不含：服务器费用、SMTP/AI 等第三方服务费用、上游大版本变更适配、你历史环境的污染清理
