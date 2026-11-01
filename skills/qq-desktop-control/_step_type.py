# -*- coding: utf-8 -*-
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qq_ctl as Q

MSG = """pi 的 Web UI 我加了个「脑图（节点逻辑图）」功能，代码刚整理好，说下实现：

【交互】聊天输入框底部加了「脑图」按钮，点开是全屏浮层画布。节点 6 种类型：目标/条件/步骤/想法/风险/结果。拖拽摆位、从节点拉线连线、滚轮缩放、点「整理」走 BFS 自动分层布局。

【关键设计】不新增消息类型，也不动后端协议。图画完直接序列化成一棵缩进大纲，当普通文本插进输入框发出去 —— 模型看到的只是普通消息，对 pi 零侵入。

【序列化】lib/mindmap.ts 的 serializeMindMap：无入边的节点当根，● 表根、• 表子节点，两个空格一层；节点备注单独一行「备注: xxx」。成环/多父这种非树边不丢，降级写进末尾「交叉引用」段。

【代码结构】
- lib/mindmap.ts  259 行（纯数据层：模型 / 连线校验 / BFS 自动布局 / 缩进序列化）
- components/MindMapPanel.tsx  829 行（浮层编辑器：拖拽 / 连线 / 缩放 / 整理 / 预览 / 插入）
- components/ChatInput.tsx  只加「脑图」按钮 + 插入回调两处，不动输入框本身
- i18n 三份（en / zh-CN / zh-TW）+ 两个测试文件
合计 1414 行新增，零新增依赖。

代码我打个包发你。"""

q = Q.QQ()
q.focus()
ix, iy = q.pt("input")
Q.click(ix, iy)
Q.human_delay(0.2, 0.35)
Q.hotkey("ctrl", "a")
Q.hotkey("del")
Q.human_delay(0.1, 0.2)
Q.type_text(MSG)
Q.human_delay(0.4, 0.7)
p = q.shot(os.path.join(Q.HERE, "shots", "typed.png"))
print("SHOT=", p)
