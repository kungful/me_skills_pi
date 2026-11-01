# -*- coding: utf-8 -*-
"""Step 1: 在 QQ 搜索框里搜目标，截图看结果。"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qq_ctl as Q

TARGET = "四大地"

q = Q.QQ()
q.focus()
sx, sy = q.pt("search")
Q.click(sx, sy)
Q.human_delay(0.15, 0.3)
Q.hotkey("ctrl", "a")
Q.hotkey("del")
Q.human_delay(0.08, 0.15)
Q.type_text(TARGET)
time.sleep(1.0)
p = q.shot(os.path.join(Q.HERE, "shots", "search_target.png"))
print("TARGET=", TARGET)
print("SHOT=", p)
