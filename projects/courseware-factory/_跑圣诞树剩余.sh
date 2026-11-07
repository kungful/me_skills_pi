#!/bin/bash
# 圣诞树：补跑步骤2 → 重跑步骤3/4（参考链断了）→ real → photo
cd "C:/Users/hua/Documents/备份代码/小红书卖课件" || exit 1
PY="C:/Users/hua/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"
PJ="项目/圣诞树-4-6岁/project.json"

echo "=== [1/3] chain 修复 步骤2/3/4 ==="
"$PY" -X utf8 工厂/pipeline.py "$PJ" --only 范画步骤2_勾线 范画步骤3_涂色 范画步骤4_加深 --no-ui

echo "=== [2/3] real 实物 3 张 ==="
"$PY" -X utf8 工厂/pipeline.py "$PJ" --batch real --no-ui

echo "=== [3/3] photo 素材 7 张 ==="
"$PY" -X utf8 工厂/pipeline.py "$PJ" --batch photo --no-ui

echo "=== ALL DONE ==="
