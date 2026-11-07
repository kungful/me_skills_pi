# 项目镜像（projects/）

本目录和 `skills/`、`apks/` 平级，放**完整项目的源码 + 部署文档**——目标是换一台电脑、
甚至换一个人，照着文档就能把它重新跑起来。

| 项目 | 是什么 | 文档 |
| --- | --- | --- |
| [`flashvsr/`](flashvsr/) | 仙宫云 GPU 一键实例：FlashVSR+ 视频超分（2 倍高清放大），带抗断线 WebUI、文件库、自动分片解码 | [README](flashvsr/README.md) · [部署](flashvsr/DEPLOY.md) · [运维](flashvsr/MAINTENANCE.md) · [版本](flashvsr/CHANGELOG.md) |
| [`courseware-factory/`](courseware-factory/) | 小红书少儿美术课件生产线：26 页教学链条 + 16 张 AI 配图 + PPTX/PDF 导出 + 审图台 WebUI + 选题台（`选题.py`，爆款证据驱动 + 自检 + 自动/弹窗人工两种定稿） | [README](courseware-factory/README.md) · [清单](courseware-factory/_mirror.json) |

约定：

- 每个项目一个目录，里面**自带** `README.md`（这是什么）+ `DEPLOY.md`（怎么从零部署）+
  `MAINTENANCE.md`（怎么运维排障）+ `CHANGELOG.md`（版本与镜像 id）。
- 文档里的命令要能**在任意一台新电脑上直接复制执行**，不要依赖作者本机的绝对路径。
- 密钥、令牌、密码一律不进仓库：`~/.xgc_token` 这类放在用户目录，文档只写怎么生成。
- `courseware-factory/` 是**自动镜像**（`~/.pi/agent/skills/skills-github-sync/scripts/projects_sync.py`），
  只同步代码 / 文档 / 小数据。`项目/*/img|img_sell|out`（单套 116MB 的课件图）、`模板/*.pptx`、
  爆款库的抓图都按规则排除，**目录内容以源机为准**；`_mirror.json` 记录源路径、文件数、跳过了什么。
