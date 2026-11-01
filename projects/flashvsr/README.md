# FlashVSR+ 视频超分（仙宫云 GPU 一键实例）

把开源项目 [OpenImagingLab/FlashVSR_Plus](https://github.com/OpenImagingLab/FlashVSR_Plus)
打包成一个**按秒计费、用完即毁**的云 GPU 实例：开一台 RTX 4090 D，浏览器打开就能上传视频、
2 倍高清放大、在线预览和下载。跑一张图/一条片子通常 ¥0.02 ~ ¥0.30。

本文档的目标：**换一台电脑（甚至换一个人、换一个仙宫云账号）也能从零把这套东西重新跑起来。**

## 三种使用方式，按需要选

| 你想干什么 | 需要什么 | 看哪节 |
| --- | --- | --- |
| **只是想用**（放大视频） | 一台能开浏览器的电脑 + 一个还在跑的实例地址 | [DEPLOY.md §1](DEPLOY.md#1-最快路径直接开一台用现成镜像) |
| **换台电脑/换账号自己部署** | Python 3.9+、`paramiko`、仙宫云访问令牌 | [DEPLOY.md §1-§2](DEPLOY.md) |
| **想改代码 / 二次开发** | 上一行 + 能 SSH 到实例 | [DEPLOY.md §3](DEPLOY.md#3-改代码热更新另一台电脑接着干) |
| **连镜像都没有，要从零构建** | 一台 GPU 实例 + 40 分钟 | [DEPLOY.md §4](DEPLOY.md#4-从零构建镜像没有现成镜像时) |
| **日常运维 / 排障 / 成本** | — | [MAINTENANCE.md](MAINTENANCE.md) |
| **版本历史、镜像 id 清单** | — | [CHANGELOG.md](CHANGELOG.md) |

> 一句话：**用的时候只要浏览器，维护的时候才需要 Python。** 所有推理都在云上跑，
> 本地电脑再弱都行（手机都行）。

## 这套东西长什么样

```
浏览器 ──HTTPS──> 仙宫云反向代理 ──> 容器 7860 端口
                                    ├── /s      精简版 WebUI（默认，抗断线）
                                    │            ├── 上传（2MB 分片续传）/ 服务器下载 / 文件预览
                                    │            ├── 参数 + 后台任务 + 轮询进度
                                    │            └── 文件库：缩略图 / 预览 / 下载 / 删除
                                    ├── /g      Gradio 版（备用）
                                    ├── /up     分片上传台
                                    └── /api/*  短 JSON 接口
                                    容器内：FlashVSR_Plus 仓库 + 14 GB 权重 + torch 2.6
开机自启：/scripts/start.d/flashvsr-webui.sh（flock 保证只有一个实例）
```

## 目录

```
projects/flashvsr/
├── README.md              ← 你在这里
├── DEPLOY.md              部署手册（含从零构建、热更新、验收清单、坑）
├── MAINTENANCE.md         运维手册（接口、日志、排障、成本实测）
├── CHANGELOG.md           版本历史 + 镜像 id 清单
├── app/                   容器里 /root/app 的全部代码（WebUI 本体）
│   ├── app.py             后台任务 + 轮询 + 文件库 + 自动分片解码
│   ├── simple.html        精简版前端（抗断线）
│   ├── uploader.py        2 MB 分片续传上传台
│   ├── dl.py              多连接断点续传下载器（啃 HuggingFace）
│   └── README_FlashVSR.md 面向使用者的镜像说明（用法/参数/实测数据）
└── scripts/
    ├── 01_env.sh          构建 stage1：torch + flash-attn + triton 算子 + gradio
    ├── 02_weights.sh      构建 stage2：hf-mirror 拉权重（备用路径）
    ├── 04_weights.sh      构建 stage2'：多连接重试硬啃 HuggingFace（实际用的）
    ├── 03_smoke.sh        构建 stage3：冒烟测试 + 显存/耗时实测
    ├── flashvsr-webui.sh  容器自启钩子（部署到 /scripts/start.d/）
    ├── restart_webui.sh   只重启 WebUI（不重开机器）
    ├── xr.py              远端执行小工具（paramiko 密码登录，走 SSH）
    └── push.py            把本地 app/ 推上容器（自动转 LF 行尾）
```

## 关键地址（实例在运行时）

```
https://<实例ID>-7860.container.x-gpu.com/s    精简版 WebUI ← 日常用这个
https://<实例ID>-7860.container.x-gpu.com/g    Gradio 版（网络好时可用）
https://<实例ID>-7860.container.x-gpu.com/up   分片续传上传台
https://<实例ID>-8888.container.x-gpu.com/     Jupyter（带 token，控制台取）
ssh <实例ID>.ssh.x-gpu.com -p <控制台端口>      SSH（root + 控制台给的密码）
```

平台**只放行 7860 / 8888 两个端口**，所以别想着开 7861。

## 成本（实测，2026-11-01）

| 项 | 数字 |
| --- | --- |
| RTX 4090 D 24G | ¥1.59/h ≈ ¥0.000442/s，**只在「运行中」计费** |
| 开机 / 铺 49 GB 镜像 | **免费**（首次部署等几分钟也不花钱） |
| 单张 1536×1024 全流程（含 SSH/启动/下载/销毁 56 s） | ¥0.0247 |
| 594 帧 720×1280 → 2560×1408（19.8 s 片子） | ≈ ¥0.30（505 s 计费窗口） |
| 关机但保留 GPU（`shutdown`） | **仍在按原价计费**，坑！ |
| 关机并释放 GPU（`shutdown_release_gpu`） | GPU 停计费，只剩磁盘 ¥0.00003/GB/h |
| 忘记关机挂一天 | ¥38 |

**规矩：跑完立刻关机释放 GPU，镜像里的东西不会丢。**
