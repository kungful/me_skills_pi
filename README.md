# Pi Skills

本仓库由 [`skills-github-sync`](skills/skills-github-sync/) 自动从本机 Pi 镜像同步。
最后同步：**2026-10-02 17:48:57**

共 **8** 个 skill。

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
| [`courseware-factory`](skills/courseware-factory/) | 生产小红书售卖的少儿美术课件（PPTX + PDF 双交付），含 WebUI 审图台。用当用户要做新课件（"做课件/新课题/出一套 XX 岁课件/范画/教学课件"），或要改已有课件的图片、版式、文案、品牌名，或要导出 PDF/PPTX/单张图片时。仅需生成普通图片、不动课件结构时用 grsai-image-2-5。 | pi |
| [`design-and-review-circuit`](skills/design-and-review-circuit/) | Design, audit, or correct an electronic circuit from a product brief, native schematic, netlist, block diagram, or circuit description. Use for architecture ... | pi |
| [`easyeda-agent`](skills/easyeda-agent/) | 通过本地 easyeda CLI、daemon 和连接器操作嘉立创EDA专业版（EasyEDA Pro）：用可迁移样例和参数化数据构建或修复原理图、布局布线 PCB，并回读连接、几何、DRC 与保存结果。适用于已有工程操作及数据驱动电路设计。 | agents |
| [`grsai-image-2-5`](skills/grsai-image-2-5/) | Generate or restyle images through the grsai API (gpt-image-2 / 2.5 family; text-to-image, image-to-image with base64 or URL references, transparent backgrou... | pi |
| [`grsai-nano-banana`](skills/grsai-nano-banana/) | Generate or edit images through the grsai legacy Nano Banana API (/v1/draw/nano-banana, /v1/draw/result) or the Gemini-compatible route (/v1beta/models/<mode... | pi |
| [`kicad`](skills/kicad/) | Analyze KiCad projects and PDF schematics: schematics, PCB layouts, Gerbers, footprints, symbols, netlists, and design rules. Reviews designs for bugs, trace... | pi |
| [`skills-github-sync`](skills/skills-github-sync/) | 把本机 Pi skills 镜像同步到 GitHub 仓库（自动提交 + 推送），并在仓库里维护 README 清单。当用户说"同步 skills 到 GitHub / 上传 skills / 备份 skills / 新建一个 skill 顺手传上去 / skills 自动上传 / 仓库里的 skills 更新一... | pi |
