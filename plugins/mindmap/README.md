# 脑图（mindmap）· pi-web-ui 界面插件

把 pi-web-custom（`agegr/pi-web` 分叉）输入框里的**脑图 / 节点逻辑图编辑器**移植到
`@youweichen/pi-web-ui`（本机 Linux 在跑的那个 Web UI）。原版是 React 组件 + `lib/mindmap.ts`；
这里把模型层原样搬过来（TS→JS），视图层用原生 DOM + SVG 重写，挂成宿主自带的**界面插件**——
不 fork 宿主、不改 npm 包、不重启服务。

v1.1.0 起多了**一句话交给 pi 的模型生成图**（`✨ AI 生成`），并补了 ComfyUI 式的**右键挑类型建节点**。

**v1.1.1 修掉「拉线弹不出/弹出来点不动」**：类型菜单的 `z-index` 原来只有 60，被浮层（9000）压在下面，
在浮层里根本看不见也点不到；同时每次开菜单都往 window 挂一个闭包，旧闭包会把新菜单一起关掉。
现在菜单 `z-index: 10001`、只有一个活动监听器，还支持 `1`–`7` 快选，端口从 14px 放大到 18px 并带内点，
新建节点会被夹进可视区（拖到浮层外松手也不会丢到视野外）。

## 装（换电脑也照这个来）

```bash
git clone https://github.com/kungful/pi-mindmap.git /tmp/pi-mindmap
bash /tmp/pi-mindmap/install.sh          # 复制到 ~/pi-mindmap-plugin 并软链进 ~/.pi-web/plugins/
```

> 同一份代码也镜像在 `me_skills_pi/plugins/mindmap/`（`bash /tmp/me_skills_pi/plugins/mindmap/install.sh` 等价）。

`install.sh` 干的事就两件：把代码拷到 `~/pi-mindmap-plugin`，再
`ln -sfn ~/pi-mindmap-plugin ~/.pi-web/plugins/mindmap`（`PI_WEB_DATA_DIR` 可覆盖数据目录）。
装完**刷新浏览器**就出现（宿主在客户端 attach 时重扫插件目录，会顺带激活服务端 `index.mjs`，不用重启服务）。

卸载：`rm ~/.pi-web/plugins/mindmap`（软链，源码还在 `~/pi-mindmap-plugin`），刷新即消失。

## 怎么用

| 入口 | 说明 |
| --- | --- |
| 输入框控制条最左的 `🧠 脑图` | 打开全屏浮层（就是 Windows 版的那个位置） |
| 顶栏 `🧠 脑图` tab | 同一份图在大面板里编辑 |
| `插入输入框` | 大纲**追加**到草稿末尾（空行分隔），**不会自动发送** |

## 交互

| 操作 | 效果 |
| --- | --- |
| 拖节点标题栏 | 移动节点 |
| 从节点右侧圆点拉线 | 拖到另一个节点=连线；**拖到空白=弹类型菜单**（点一下或按 `1`–`7`），即新建并连上 |
| 右键空白 | 同一套类型菜单，挑类型再落节点 |
| 双击空白 | 直接新建「想法」节点 |
| 滚轮 / 拖空白 | 以光标为中心缩放（0.35–2）/ 平移画布 |
| 点类型小标签 | 循环 目标/条件/步骤/想法/风险/结论/图片 |
| Delete / Backspace | 删选中节点或连线（焦点在输入框里时不触发） |
| Esc | 关类型菜单 → 取消选中 → 关浮层 |
| 拖图片文件到画布 | 新建图片节点（压到最长边 720px 的 JPEG 存 localStorage） |

工具栏：新建节点 / 自动整理（按连线 BFS 分列） / 载入图片 / 从文本导入 / **提示生成** /
复制文本 / 预览 / 插入输入框 / 清空（点两下确认）。

## 从一句话生成：本地规则 vs AI

点「提示生成」后有两个按钮：

- **本地拆句**：`promptToMindMap` 用连接词（先/同时/风险是…）分句 + 关键词判类型，
  瞬间出草稿，**不联网、不花钱**。
- **AI 生成（pi 模型）**：走宿主里 pi SDK 的 headless 一次性会话，用**你自己在 pi 里配置的模型与登录态**，
  约 10 秒返回一张图。默认留空=用 pi 当前默认模型，插件设置里可写死 `provider/model`、改超时。

AI 那一路的细节（都很实际）：

```
浏览器 ──POST /plugins-api/mindmap/generate──> index.mjs(服务端入口, host.route)
        └─ spawn: node <pi SDK>/dist/cli.js --print --mode text
                  --no-tools --no-session --no-extensions --no-skills
                  --no-context-files --no-prompt-templates --offline
                  --system-prompt <固定 JSON 规范>  -- "<你的那句话>"
```

- 不复制任何凭据逻辑：CLI 自己读 `~/.pi/agent/{settings,models,auth}.json`；
- 模型只能回文本：`--no-tools --no-session`，它碰不到磁盘、也不会污染你的会话历史；
- 一次只跑一个（并发会 429）、超时杀进程、原始输出限长；
- 一次模型调用 = 一次 token 费用，这就是为什么它是个单独的按钮而不是默认行为。

**给模型的专业格式**（`client/ai.mjs` 与 `index.mjs` 的 SYSTEM_PROMPT 成对维护）：

```json
{"nodes":[{"id":"n1","kind":"goal","title":"…","detail":"…"}],
 "edges":[{"from":"n1","to":"n2","label":"可选"}]}
```

模型的回答不老实也能吃下：先去 ``` 围栏、再抠第一个 `{` 到最后一个 `}`、容忍尾逗号/单引号/
中文 kind 别名；还失败就当成`serializeMindMap` 的缩进大纲走 `deserializeMindMap`；
再不行才报错，并把**原始返回**折在弹窗里给你看（可复制出来手动导入）。

## 交给模型的是什么

不是 JSON，是一段缩进大纲（`serializeMindMap`）：

```
【用户用脑图表达的逻辑结构】

下面是从节点图导出的思路：● 表示起点，缩进表示上一级指向下一级，「备注」是节点的补充说明。…

● [想法] 想把家里的茶叶厂从线下批发转到线上卖
  • [步骤] 做小红书每周三条内容
    备注: 先做小红书每周三条内容
  • [风险] 产能和维护跟不上

额外关联（未表现成层级）
- [步骤] 建立库存与产能预警 → [结论] 形成线上线下双渠道稳定出货
```

- 「从文本导入」用 `deserializeMindMap` 把同一段文本还原成节点图，往返一致（单测保证）。
- 环 / 回边不会死循环，降级成末尾「额外关联」列表。
- 图片节点只在大纲里带 `图片: 文件名`，base64 留在浏览器，不灌进 prompt。
- 持久化：`localStorage["pi-web-ui:mindmap:graph"]`，全浏览器一份图（原版是每草稿一份）。

## 目录

```
plugins/mindmap/
├── manifest.json          id: mindmap / icon: 🧠 / permissions: ["http"] / 两个设置项
├── index.mjs              服务端入口：host.route("POST","/generate") → 起 pi CLI 一次性会话
├── client/
│   ├── entry.mjs          视图：tab 编辑器 + 输入框按钮 + 全屏浮层（原生 DOM + SVG）
│   ├── mindmap.mjs        模型层（由 pi-web-custom/src/lib/mindmap.ts 转出，逻辑未改）
│   ├── ai.mjs             AI 输出 → 节点图（JSON 严格校验 + 大纲兜底）
│   └── i18n.mjs           中文 / 繁体 / 英文
├── tests/mindmap.test.mjs 18 个模型单测（原分叉的测试套件）
├── tests/ai.test.mjs      10 个 AI 解析单测（围栏/脏 JSON/兜底/上限）
└── install.sh             一条命令装到本机
```

## 开发

```bash
node --test tests/*.test.mjs    # 28 个用例
node --check client/entry.mjs   # 语法
```

改完 `client/*.mjs`：**刷新浏览器**即可（宿主给插件 bundle 带 `?e=<epoch>` 缓存击穿；
不生效就在 设置 › 界面插件 点「重新加载」）。改 `index.mjs`（服务端入口）：需要重新激活——
宿主在**新的客户端 attach** 时会补激活它，所以刷新页面就行；不行就把插件目录挪走再放回。

浏览器实测（无头 Chrome + CDP，脚本用完即弃）：

```bash
/opt/google/chrome/chrome --headless=new --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chrome-piweb about:blank &
# CDP 里：点 .plugin-tab → 断言 .mmp 出现 → 点 [data-act=prompt] 填词 →
# 点「AI 生成」→ 等 toast「AI 生成了 N 个节点」→ 点 插入输入框 → 断言 .inputbox-row textarea 出现大纲
```

## 与 Windows 分叉的差异

- 宿主不同（`agegr/pi-web` Next.js → `@youweichen/pi-web-ui` React+Vite+Express），
  所以走**插件**而不是给 `ChatInput.tsx` 打补丁。
- 图是**整浏览器一份**，不是每个草稿/会话一份（插件拿不到 conversationId）。
- 多了 AI 生成（原版只有本地规则）、右键类型菜单。
- 节点尺寸、颜色、序列化格式、类型循环、拉线弹菜单等行为与原版一致。
