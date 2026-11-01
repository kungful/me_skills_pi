# pi-web 定制版（带「脑图」逻辑图编辑器）

[agegr/pi-web](https://github.com/agegr/pi-web) 的源码分叉，在输入框里加了一个
**脑图 / 节点逻辑图编辑器**：把想法先画成"目标 → 条件 → 步骤"的节点图，
再一键把整张图序列化成缩进大纲插进输入框，交给 AI 当结构化上下文。

- 上游基线：`v0.13.0`（commit `d128bae`）
- 本机工作副本：`C:/Users/hua/Documents/备份代码/pi-web-custom`
- 备份内容：`src/` 全量源码快照（已剔除 `node_modules/`、`.next/`）+ `patches/` 里的两个提交

## 目录

```
pi-web-custom/
  README.md                                  # 本文件
  patches/0001-mindmap-editor.patch           # 脑图编辑器（节点/连线/序列化/浮层）
  patches/0002-mindmap-text-image-linkmenu.patch  # 反向导入 + 图片节点 + 拖线弹类型
  patches/0003-mindmap-prompt-draft.patch        # 「提示生成」：一句话拆成草稿图
  src/                                        # 源码快照（可直接 npm install && npm run dev）
```

## 为什么是分叉

`npm i -g @agegr/pi-web` 装出来只有 `.next` / `bin` / `public` 预构建产物，
改不了组件，所以维护一份源码分叉。桌面快捷方式 `pi-web.lnk` 启动的启动器
（`%LOCALAPPDATA%\pi-web-launcher\pi-web-launch.ps1`）会**优先跑这个分叉的构建**，
路径记在 `fork-path.txt`，没有分叉时才回退到全局 `pi-web`。

## 加了什么

| 文件 | 说明 |
|---|---|
| `lib/mindmap.ts` | 模型层：节点/连线类型、`connectMindMapNodes`、`autoLayoutMindMap`（按连线 BFS 分列）、`serializeMindMap`（缩进大纲）、**`deserializeMindMap`（大纲→图，缩进还原层级 / `备注:` 还原 detail / 额外关联还原回边 / 跨语言 kind 别名）**、`nextNodeId` / `bumpNodeId`、**`promptToMindMap`（一句话 → 草稿图：本地规则分句 + 关键词判类型）**、`reindexMindMap`（追加时续号） |
| `components/MindMapPanel.tsx` | 全屏浮层编辑器：拖节点、**从右侧端口拖到空白处弹出类型菜单（ComfyUI 式，选中即连线）**、滚轮缩放（0.35–2 光标为中心）、平移、双击空白新建、`Delete` 删除、`Esc` 逐层关闭、类型循环、自动整理、**载入图片/拖入文件**、**从文本导入**、**提示生成**、可折叠预览、复制、插入输入框 |
| `components/ChatInput.tsx` | 底部控制条「脑图」按钮（思考等级左边）；浮层以 `role="dialog"` 渲染在 `<fieldset>` 内；插入时把大纲**追加**到草稿后面（空行分隔）并聚焦光标到末尾，**不会自动发送** |
| `lib/i18n/messages/{en,zh-CN,zh-TW}.ts` | 文案，三份 key 与占位符必须一致（`lib/i18n/registry.test.mjs` 校验） |
| `lib/mindmap.test.mjs` / `components/MindMapPanel.test.mjs` | 13 + 3 个测试（含序列化↔反序列化往返一致） |

设计要点：

- **互不干扰**：面板只是输入框的同级浮层，不点击不渲染、不抢焦点、不改草稿/附件/发送链路。
- **文本交接**：交给模型的是一段缩进大纲，不是 JSON：

  ```
  ● [目标] 茶叶厂内销转线上
    备注: 线下批发下滑 30%
    • [步骤] 先做小红书内容
  ```

  环/回边不会死循环，会降级成末尾「额外关联」列表；这段文本粘回「从文本导入」
  能原样还原成节点图（往返测试保证 `serialize(deserialize(x)) === x`）。
- **图片不进气**：图片节点把文件缩到最长边 720px 的 JPEG 存在浏览器 `localStorage`
  （每份草稿一份图），大纲里只带 `图片: 文件名`，不会把 base64 灌进 prompt。
- **提示生成是本地规则**：点「提示生成」写一句话（目标 / 先做什么 / 担心什么），
  按「，先… 同时… 风险是…」这类连接词本地分句并判类型，瞬间出一版草稿，**不调模型、不联网、不花钱**；
  选中某个节点再生成可以「接到选中节点」，草稿整体落到图右侧并连上。
- **持久化**：每个草稿/会话一份，key 为 `pi-web:mindmap:<draftKey>`，刷新不丢。

## 跑起来

```bash
npm install --registry=https://registry.npmmirror.com   # npmjs 在这台机器上会 ECONNRESET
npm run dev                                            # Turbopack，默认 30141
# 或：npm run build && npm start（别在 dev 运行时 build）
```

桌面快捷方式那条路：改完代码后跑
`%LOCALAPPDATA%\pi-web-launcher\rebuild-and-restart.ps1`（会停服 → `npm run build` → 用启动器重开）。

## 从备份恢复 / 更新上游

```bash
# 只用快照
cp -r src ~/pi-web-custom && cd ~/pi-web-custom && npm install

# 或者：全新 clone 上游后按顺序打补丁
git clone https://github.com/agegr/pi-web.git ~/pi-web-custom
cd ~/pi-web-custom && git am /path/to/pi-web-custom/patches/*.patch
```

上游升级后（`git merge origin/main`）如果解决了冲突，把本目录重新生成一遍即可（见下）。

## 刷新这份备份

```bash
python <repo>/refresh.py       # 见下，或手动：
SRC=/c/Users/hua/Documents/备份代码/pi-web-custom
DST=~/.pi/skills-repo/pi-web-custom
rm -rf "$DST/src" "$DST/patches"; mkdir -p "$DST/src" "$DST/patches"
git -C "$SRC" ls-files -co --exclude-standard -z | tar -cf - --null -T - | tar -xf - -C "$DST/src"
git -C "$SRC" format-patch --no-signature -o "$DST/patches" d128bae..HEAD
cd ~/.pi/skills-repo && git add -A pi-web-custom && git commit -m "pi-web-custom: 刷新备份" && git push
```

（`d128bae` 是上游 v0.13.0；换基线就改这个提交号。推送时如果本机代理挂着，
用 `git -c http.https://github.com.proxy= push` 直连更快。）
