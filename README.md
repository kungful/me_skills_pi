# Pi Skills

本仓库由 [`skills-github-sync`](skills/skills-github-sync/) 自动从本机 Pi 镜像同步。
最后同步：**2026-10-18 23:28:28**

共 **39** 个 skill。

## 安装

```bash
# 全部 skills 复制到本机 Pi
git clone <repo-url> /tmp/pi-skills
cp -r /tmp/pi-skills/skills/* ~/.pi/agent/skills/
```

## 清单

| Skill | 说明 | 源 |
|---|---|---|
| [`apk-github-sync`](skills/apk-github-sync/) | 把本机 Pi 开发出来的 Android APK 软件包和源代码镜像备份到 GitHub 仓库（自动提交 + 推送 + 定时/实时自动备份）。当用户说"备份 apk / 把 apk 传到 GitHub / apk 自动上传 / 新做的安卓 app 传上去 / 备份安卓源码 / apks 文件夹更新一下 / 查 a... | pi |
| [`awesome-reverse-engineering`](skills/awesome-reverse-engineering/) | 逆向工程工具与学习资源选型索引（二进制、App、固件、文件格式、协议）。当需要"逆向 / 反编译 / 反汇编 / 脱壳 / 抓包分析协议 / 分析固件 / 分析恶意样本 / 该用哪个工具 / 有没有 xx 逆向工具"，或要在 IDA、Ghidra、radare2、Frida、JADX、Hopper、x64dbg、... | pi |
| [`blender-motion-state-inspection`](skills/blender-motion-state-inspection/) | Use this skill when inspecting Blender characters, rigs, poses, animation retargeting, ground contact, facing direction, or model-vs-motion alignment where s... | pi |
| [`bw16-flash`](skills/bw16-flash/) | Ai-Thinker BW16 / RTL8720DN (Realtek AmebaD) 设备的识别、编译、烧录与救砖。含环境一键搭建、串口自动识别、源码编译、擦除+写入+校验全流程，以及「半写砖头」救援、SoftAP 不广播、抓包误报等已知坑的修法。当用户说「烧录/刷 BW16」「RTL8720DN 刷机」「抓... | pi |
| [`courseware-factory`](skills/courseware-factory/) | 生产小红书售卖的少儿美术课件（PPTX + PDF 双交付），含 WebUI 审图台 + 多课件工作台。**作用域仅限「少儿美术课件生产」，不是通用找图/做图工具。** 用于：做新课件（“做课件/新课题/出一套 XX 岁课件/范画/教学课件”）；改已有课件的图片/版式/文案/品牌名；导出 PDF/PPTX/单张图... | pi |
| [`design-and-review-circuit`](skills/design-and-review-circuit/) | Design, audit, or correct an electronic circuit from a product brief, native schematic, netlist, block diagram, or circuit description. Use for architecture ... | pi |
| [`easyeda-agent`](skills/easyeda-agent/) | 通过本地 easyeda CLI、daemon 和连接器操作嘉立创EDA专业版（EasyEDA Pro）：用可迁移样例和参数化数据构建或修复原理图、布局布线 PCB，并回读连接、几何、DRC 与保存结果。适用于已有工程操作及数据驱动电路设计。 | agents |
| [`ecom-detail-factory`](skills/ecom-detail-factory/) | 生产电商商品详情页（长图 + 分屏 + 主图 + PPTX + PDF + ZIP），含 WebUI 精修台。**作用域仅限「电商详情页生产」，不是通用做图/排版工具。** 用于：做商品详情页（“做个详情页/详情页长图/宝贝详情/主图+详情图”）；改已有详情页的文案/版式/配色/顺序；出白底主图、场景图、卖点配图... | pi |
| [`flameox`](skills/flameox/) | 用 Flameox 采集有界、可复现的运行时证据——CPU/内存/GPU/推理栈的性能剖析，或把一条命令的输出抓成结构化 artifact 供后续分析比对。当用户说"profile 一下 / 性能剖析 / 火焰图 / 找性能瓶颈 / 跑个 benchmark 采数据 / 追踪 trace / 抓一次运行证据 / ... | pi |
| [`generate-social-preview`](skills/generate-social-preview/) | 生成或修改仓库的社交预览图（GitHub 社交卡片 / 包页 / 发布贴 / 链接卡片）。当用户说"做个社交预览图 / 项目的封面图 / GitHub 分享图 / 1280x640 卡片 / 参考这张图改一个"时使用。Create or revise repository-aware social preview... | pi |
| [`gitcontribute`](skills/gitcontribute/) | 用 GitContribute 做"给开源仓库贡献"的前期调研——判断某个 issue 还值不值得做、有没有人在做、适不适合外部贡献者、有没有足够证据动手，以及收集仓库贡献规范、相关 issue/PR、代码上下文和验证结果。当用户说"给这个仓库提个 PR / 这个 issue 我能做吗 / 找点能贡献的活 / 看... | pi |
| [`grsai-image-2-5`](skills/grsai-image-2-5/) | Generate or restyle images through the grsai API (gpt-image-2 / 2.5 family; text-to-image, image-to-image with base64 or URL references, transparent backgrou... | pi |
| [`grsai-nano-banana`](skills/grsai-nano-banana/) | Generate or edit images through the grsai legacy Nano Banana API (/v1/draw/nano-banana, /v1/draw/result) or the Gemini-compatible route (/v1beta/models/<mode... | pi |
| [`internalcot`](skills/internalcot/) | 开启 InternalCoT 可见思维链模式：在每次实质工具调用和回答前，必须先写 internalcot CLI 笔记，整个会话持续生效。仅当用户明确说"$internalcot / internalcot on / 开 internalcot"时才用；用户只是说"仔细想 / 深入推理 / 展示思路"不算触发。... | pi |
| [`jacobian-math`](skills/jacobian-math/) | 当精确计算或结构分析能帮助解题时，用 Jacobian（`math.find` / `math.run`）的类型化数学操作。当用户说"精确算一下 / 符号计算 / 矩阵分解 / 组合枚举 / 数论 / 验证这个数学结论 / 有什么数学操作可用"时使用。Use Jacobian’s typed operations... | pi |
| [`kicad`](skills/kicad/) | Analyze KiCad projects and PDF schematics: schematics, PCB layouts, Gerbers, footprints, symbols, netlists, and design rules. Reviews designs for bugs, trace... | pi |
| [`leantoken`](skills/leantoken/) | 用 LeanToken 做代码检索与结构理解，省 token 省上下文——找相关文件/代码、按符号大纲看结构、精确读某个函数或行段、跨 git 版本追踪符号、查询大 JSON。当任务是在大型或不熟的代码库里"找到该看的那段代码""别把整个文件读进来""追一下这个函数的历史""仓库太大上下文塞不下"时使用，优先替代... | pi |
| [`manage-pcba-program`](skills/manage-pcba-program/) | Coordinate an evidence-gated electronic product and PCBA workflow from an idea, circuit description, schematic, netlist, PCB, BOM, or fabrication package thr... | pi |
| [`morluto-reversing-index`](skills/morluto-reversing-index/) | morluto（REA 作者）整个逆向工具与知识库生态的导航索引——要装/要连什么、有哪些配套技能、以及 80+ 个逆向与安全资源清单在哪个仓库。当用户说"morluto 还有别的逆向工具吗 / REA 生态 / 装 REA / 有哪些逆向 MCP / 找个逆向知识库 / 这套逆向工具配套都有啥"时使用，或当 `... | pi |
| [`operate-jlcpcb-order`](skills/operate-jlcpcb-order/) | Operate and review a JLCPCB PCB/PCBA quote, optional physical-stencil request, or order using a frozen Gerber/drill, BOM, CPL, sourcing lock, constraints, an... | pi |
| [`pcb-layout-review`](skills/pcb-layout-review/) | Audit, finish, or port PCB placement and routing using circuit intent, mechanical constraints, sourcing evidence, native DRC/connectivity, rendered views, an... | pi |
| [`pi-web-ui-deploy`](skills/pi-web-ui-deploy/) | Deploy and stabilize pi-web-ui (pi 编码代理的 Web UI) inside an XGC / x-gpu container — global npm install, screen + /scripts/start.d autostart, dynamic Host allo... | pi |
| [`plan-electronic-product`](skills/plan-electronic-product/) | Turn an electronic product idea, behavior description, reverse-engineering note, or incomplete circuit concept into a decision-ready engineering brief and ar... | pi |
| [`qualify-pcba-sourcing`](skills/qualify-pcba-sourcing/) | Verify a PCBA BOM and proposed components before circuit or placement freeze, including exact manufacturer part numbers, pin semantics, packages, footprints,... | pi |
| [`release-pcba-fabrication`](skills/release-pcba-fabrication/) | Build and verify a vendor-neutral PCB/PCBA manufacturing release from one frozen design revision. Use when generating or auditing Gerber, drill, IPC-2581/ODB... | pi |
| [`reverse-engineer-anything`](skills/reverse-engineer-anything/) | Reverse engineer native, managed, Electron/JavaScript, packaged, firmware, and browser targets with REA. Use shipped-artifact or requested runtime evidence t... | pi |
| [`schematic-humanizer`](skills/schematic-humanizer/) | Reorganize label-heavy or netlist-like electronic schematics into human-readable functional diagrams with visible local wiring while preserving proven connec... | pi |
| [`skills-github-sync`](skills/skills-github-sync/) | 把本机 Pi skills 镜像同步到 GitHub 仓库（自动提交 + 推送），并在仓库里维护 README 清单。当用户说"同步 skills 到 GitHub / 上传 skills / 备份 skills / 新建一个 skill 顺手传上去 / skills 自动上传 / 仓库里的 skills 更新一... | pi |
| [`smokinggun`](skills/smokinggun/) | 用 SmokingGun 扫出复杂度热点候选，并整理导入的优化证据（只读静态扫描，不执行、不改码）。当用户说"找复杂度热点 / 哪里是性能瓶颈 / 这段代码是不是太重 / 优化前后对比 / 有没有证据支持这次优化"时使用；不执行 benchmark，实测走 flameox。Use SmokingGun to fi... | pi |
| [`solidcraft-checking`](skills/solidcraft-checking/) | Use alongside solidcraft-modeling and solidcraft-editing whenever you build, change or port a SolidCraft design. Checks for errors SolidCraft does not report... | pi |
| [`solidcraft-editing`](skills/solidcraft-editing/) | Use when changing, fixing or extending an existing SolidCraft design through its MCP server - a .solidcraft file or the design open in the app. Typical reque... | pi |
| [`solidcraft-mechanisms`](skills/solidcraft-mechanisms/) | Use when building, driving or animating an assembly or mechanism in SolidCraft through its MCP server - components, grounding, joints and joint origins, rigi... | pi |
| [`solidcraft-modeling`](skills/solidcraft-modeling/) | Use when building a new part, enclosure, bracket, plate, flange or any other 3D solid in SolidCraft through its MCP server (tools such as batch, execute, mea... | pi |
| [`video-studio-mcp`](skills/video-studio-mcp/) | 用脚本/AI 自动出片：剪辑引擎是开源 Concat（JSON-RPC），配音用免费 edge-tts，配乐从 AlgerMusicPlayer 本地接口下，字幕用本地 Whisper，混音走 ffmpeg（闪避/响度归一）。当用户说"剪个视频/自动剪辑/一键成片/给视频配音/加字幕/配背景音乐/把素材做成片/批... | pi |
| [`web-browse`](skills/web-browse/) | Browse and read the live web - fetch pages as clean markdown, click into tabs/buttons/accordions and read what loads, search engines, extract links and metad... | pi |
| [`wifi-wireless`](skills/wifi-wireless/) | Wi-Fi / 无线安全评估与取证（仅授权）：监听模式抓包、WPA/WPA2/WPA3 握手与 PMKID 采集、离线口令强度评估、流氓 AP / 钓鱼热点检测、企业无线隔离与 Captive Portal 绕过测试、去认证（deauth）实验室验证。当用户说 "wifi 渗透 / 无线渗透 / 抓握手 / 破解... | pi |
| [`xgc-api`](skills/xgc-api/) | Manage 仙宫云 / XGC cloud GPU instances through its Open API - check identity and balance, list instances, deploy a GPU container, get its public URL, shut down... | pi |
| [`xgc-image-run`](skills/xgc-image-run/) | 仙宫云 GPU 跑图一条龙 —— 自动开机 → 自动连进容器 → 跑 ComfyUI 出图 → 把图拉回本地 → 立刻销毁实例。当用户说"跑图/出图/生图/生成一张图/用仙宫云跑/用 ComfyUI 出图/用 Krea2 跑/拿我的 4090 跑一张/跑完就销毁/省钱的跑图方式"，或者要用**本地部署的模型**（... | pi |
| [`xhs-courseware-post`](skills/xhs-courseware-post/) | 把课件工厂产出的课件一条龙发到小红书（选图 → 补 3:4 封面 → 生成文案 → 发布 → 核实 → 回评论）。**作用域仅限「已有课件的发布与运营」，不做课件本身。** 用于：把课件发小红书/发笔记/上架；给课件写小红书文案、起标题、配话题标签；挑图、补封面、去重图；发出去以后核实、看通知、回评论。要做课件本... | pi |

## APK 备份

Pi 开发的安卓 APK + 源码备份在 [`apks/`](apks/)，共 14 个应用，由 [`apk-github-sync`](skills/apk-github-sync/) 自动同步。
