#!/usr/bin/env bash
cd "C:/Users/hua/Documents/备份代码/小红书卖课件" || exit 1
export PYTHONIOENCODING=utf-8
PY="C:/Users/hua/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"
Q='这是给4-6岁少儿美术课件做的小红书封面。只做事实核对，不评价好不好看：1)有几只手？手指数量对不对，有没有粘连畸形或多出手臂？2)有没有文字乱码（注意：图里不该有文字）？3)主体有没有崩坏断裂融合？4)其他AI瑕疵？尽量短。最后一句必须是 [可用] 或 [不可用]。'
for t in 手指印仙人掌 保鲜袋拓印花海 线描青花瓷瓶 撕纸小怪兽 松果猫头鹰; do
  for c in A_四宫格 B_实物对照 C_桌面实拍; do
    f="项目/${t}-4-6岁/封面候选/${c}.png"
    [ -f "$f" ] || continue
    echo "===== $t / $c ====="
    "$PY" _审图.py "$f" --q "$Q" 2>&1 | sed -n '/核对/,$p' | grep -v '^$' | tail -8
  done
done
echo "===== 审图结束 $(date +%H:%M) ====="
