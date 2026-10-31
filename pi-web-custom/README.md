# pi-web 定制版（带「脑图」逻辑图编辑器）

[agegr/pi-web](https://github.com/agegr/pi-web) 的源码分叉，在输入框里加了一个
**脑图 / 节点逻辑图编辑器**：把想法先画成"目标 → 条件 → 步骤"的节点图，
再一键把整张图序列化成缩进大纲插进输入框，交给 AI 当结构化上下文。

- 上游基线：`v0.13.0`（commit `d128bae`）
- 本机工作副本：`C:/Users/hua/Documents/备份代码/pi-web-custom`
- 备份内容：`src/` 全量源码快照（已剔除 `node_modules/`、`.next/`）+ `patches/` 里的提交补丁

## 目录

```
pi-web-custom/
  README.md                  # 本文件
  patches/0001-mindmap.patch  # 相对上游 v0.13.0 的完整改动（含新增文件）
  src/                        # 源码快照（可直接 npm install && npm run dev）
```

## 为什么是分叉

`npm i -g @agegr/pi-web` 装出来只有 `.next` / `bin` / `public` 预构建产物，
改不了组件，所以维护一份源码分叉。

## 加了什么

| 文件 | 说明 |
|---|---|
| `lib/mindmap.ts` | 纯模型层：节点/连线类型、`connectMindMapNodes` 连线校验、`autoLayoutMindMap` 按连线 BFS 分列排版、`serializeMindMap` 缩进大纲序列化、`nextNodeId` / `bumpNodeId` |
| `components/MindMapPanel.tsx` | 全屏浮层编辑器：拖动节点、从右侧圆点拖到另一节点连线、滚轮缩放（0.35–2，以光标为中心）、拖空白平移、双击空白新建、`Delete` 删除、`Esc` 关闭、类型标签循环切换 6 种类型、自动整理、可折叠预览、复制文本、插入输入框 |
| `components/ChatInput.tsx` | 底部控制条新增「脑图」按钮（思考等级左边）；面板以 `role="dialog"` 浮层渲染在 `<fieldset>` 内；插入时把大纲**追加**到已有草稿后面（空行分隔）并聚焦光标到末尾，**不会自动发送** |
| `lib/i18n/messages/{en,zh-CN,zh-TW}.ts` | 新增文案，三份 key 完全一致（`lib/i18n/registry.test.mjs` 会校验） |
| `lib/mindmap.test.mjs` / `components/MindMapPanel.test.mjs` | 8 + 2 个测试 |

设计要点：

- **互不干扰**：面板只是输入框的同级浮层，不点击不渲染、不抢焦点、不改草稿/附件/发送链路。
- **文本交接**：交给模型的是一段缩进大纲，不是 JSON：

  ```
  ● [目标] 茶叶厂内销转线上
    备注: 线下批发下滑 30%
    • [步骤] 先做小红书内容
  ```

  环/回边不会死循环，会降级成末尾「额外关联」列表。
- **持久化**：每个草稿/会话一份，存 `localStorage`（`pi-web:mindmap:<draftKey>`），刷新不丢。

## 跑起来

```bash
npm install --registry=https://registry.npmmirror.com   # npmjs 在这台机器上会 ECONNRESET
npm run dev                                            # Turbopack，默认 30141
# 或：npm run build && npm start（别在 dev 运行时 build）
```

> 全局还装着 npm 版 pi-web 时，30141 会被它占着 —— 先停掉全局实例，或给 dev 换个端口。

## 从备份恢复 / 更新上游

```bash
# 只用快照
cp -r src ~/pi-web-custom && cd ~/pi-web-custom && npm install

# 或者：全新 clone 上游后打补丁
git clone https://github.com/agegr/pi-web.git ~/pi-web-custom
cd ~/pi-web-custom && git am /path/to/pi-web-custom/patches/0001-mindmap.patch
```

上游升级后（`git fetch origin && git merge origin/main`）如果补齐了新版本，
把本目录重新生成一遍即可（见下）。

## 刷新这份备份

```bash
SRC=/c/Users/hua/Documents/备份代码/pi-web-custom
DST=~/.pi/skills-repo/pi-web-custom
rm -rf "$DST/src"; mkdir -p "$DST/src" "$DST/patches"
git -C "$SRC" ls-files -co --exclude-standard -z | tar -cf - --null -T - | tar -xf - -C "$DST/src"
git -C "$SRC" format-patch --no-signature -o "$DST/patches" d128bae..HEAD
cd ~/.pi/skills-repo && git add -A pi-web-custom && git commit -m "pi-web-custom: 刷新备份" && git push
```

（`d128bae` 是上游 v0.13.0；换基线就改这个提交号。）
