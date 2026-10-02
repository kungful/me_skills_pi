# Pi Skills

本仓库由 [`skills-github-sync`](skills/skills-github-sync/) 自动从本机 Pi 镜像同步。
最后同步：**2026-10-03 05:21:06**

共 **10** 个 skill。

## 安装

```bash
# 全部 skills 复制到本机 Pi
git clone <repo-url> /tmp/pi-skills
cp -r /tmp/pi-skills/skills/* ~/.pi/agent/skills/
```

## 清单

| Skill | 说明 | 源 |
|---|---|---|
| [`blender-motion-state-inspection`](skills/blender-motion-state-inspection/) | Use this skill when inspecting Blender characters, rigs, poses, animation retargeting, ground contact, facing direction, or model-vs-motion alignment where s... | pi |
| [`courseware-factory`](skills/courseware-factory/) | 生产小红书售卖的少儿美术课件（PPTX + PDF 双交付），含 WebUI 审图台 + 多课件工作台。**作用域仅限「少儿美术课件生产」，不是通用找图/做图工具。** 用于：做新课件（“做课件/新课题/出一套 XX 岁课件/范画/教学课件”）；改已有课件的图片/版式/文案/品牌名；导出 PDF/PPTX/单张图... | pi |
| [`design-and-review-circuit`](skills/design-and-review-circuit/) | Design, audit, or correct an electronic circuit from a product brief, native schematic, netlist, block diagram, or circuit description. Use for architecture ... | pi |
| [`easyeda-agent`](skills/easyeda-agent/) | 通过本地 easyeda CLI、daemon 和连接器操作嘉立创EDA专业版（EasyEDA Pro）：用可迁移样例和参数化数据构建或修复原理图、布局布线 PCB，并回读连接、几何、DRC 与保存结果。适用于已有工程操作及数据驱动电路设计。 | agents |
| [`ecom-detail-factory`](skills/ecom-detail-factory/) | 生产电商商品详情页（长图 + 分屏 + 主图 + PPTX + PDF + ZIP），含 WebUI 精修台。**作用域仅限「电商详情页生产」，不是通用做图/排版工具。** 用于：做商品详情页（“做个详情页/详情页长图/宝贝详情/主图+详情图”）；改已有详情页的文案/版式/配色/顺序；出白底主图、场景图、卖点配图... | pi |
| [`grsai-image-2-5`](skills/grsai-image-2-5/) | Generate or restyle images through the grsai API (gpt-image-2 / 2.5 family; text-to-image, image-to-image with base64 or URL references, transparent backgrou... | pi |
| [`grsai-nano-banana`](skills/grsai-nano-banana/) | Generate or edit images through the grsai legacy Nano Banana API (/v1/draw/nano-banana, /v1/draw/result) or the Gemini-compatible route (/v1beta/models/<mode... | pi |
| [`kicad`](skills/kicad/) | Analyze KiCad projects and PDF schematics: schematics, PCB layouts, Gerbers, footprints, symbols, netlists, and design rules. Reviews designs for bugs, trace... | pi |
| [`skills-github-sync`](skills/skills-github-sync/) | 把本机 Pi skills 镜像同步到 GitHub 仓库（自动提交 + 推送），并在仓库里维护 README 清单。当用户说"同步 skills 到 GitHub / 上传 skills / 备份 skills / 新建一个 skill 顺手传上去 / skills 自动上传 / 仓库里的 skills 更新一... | pi |
| [`web-browse`](skills/web-browse/) | Browse and read the live web - fetch pages as clean markdown, click into tabs/buttons/accordions and read what loads, search engines, extract links and metad... | pi |
