#!/bin/bash
# FlashVSR+ 环境构建 —— stage 1/4: python 依赖 + 注意力算子
set -uo pipefail
export PATH=/root/miniconda3/bin:/usr/local/cuda/bin:$PATH
export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
export PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn
export HF_ENDPOINT=https://hf-mirror.com
REPO=/root/FlashVSR_Plus

say() { echo; echo "########## $* ##########"; date '+%F %T'; }

say "0. 基础信息"
python -V; which python; nvcc --version | tail -2
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

say "1. clone 代码"
if [ ! -d "$REPO/.git" ]; then
  git clone --depth 1 https://github.com/OpenImagingLab/FlashVSR_Plus.git "$REPO" || exit 11
fi
cd "$REPO" || exit 12
git log --oneline -1

say "2. torch 2.6.0 (cu124 wheel from PyPI)"
pip install -q --upgrade pip setuptools wheel || exit 21
pip install torch==2.6.0 || exit 22
python -c "import torch;print('torch',torch.__version__,'cuda',torch.version.cuda,'avail',torch.cuda.is_available(),'dev',torch.cuda.get_device_name(0))" || exit 23

say "3. flash-attn 预编译 wheel"
ABI=$(python -c "import torch;print('TRUE' if torch._C._GLIBCXX_USE_CXX11_ABI else 'FALSE')")
WHL="flash_attn-2.7.4.post1+cu12torch2.6cxx11abi${ABI}-cp310-cp310-linux_x86_64.whl"
echo "abi=$ABI  wheel=$WHL"
pip install "https://github.com/Dao-AILab/flash-attention/releases/download/v2.7.4.post1/${WHL}" || echo "!!! flash-attn 安装失败，稍后判断是否致命"
python -c "import flash_attn;print('flash_attn',flash_attn.__version__)" || echo "!!! flash_attn import 失败"

say "4. requirements"
pip install -r requirements.txt || exit 41
pip install -e . --no-deps || exit 42
python -c "import flashvsr_plus, inference; print('pkg ok')" || exit 43

say "5. FlashVSR Triton 注意力算子"
pip install -e operators/flashvsr_attn --no-build-isolation --no-deps || echo "!!! triton op 安装失败"
python -c "import flashvsr_attn; print('triton op ok')" 2>/dev/null || python -c "
import importlib,sys
for m in ('flashvsr_attn','block_sparse'):
    try: importlib.import_module(m); print(m,'ok')
    except Exception as e: print(m,'no:',e)
"

say "6. WebUI 依赖"
pip install gradio || exit 61
python -c "import gradio;print('gradio',gradio.__version__)" || exit 62

say "STAGE1 DONE"
pip list 2>/dev/null | grep -Ei "torch|flash|triton|gradio|numpy|opencv"
