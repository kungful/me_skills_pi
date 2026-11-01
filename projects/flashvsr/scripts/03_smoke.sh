#!/bin/bash
# 冒烟测试：turbo 小尺寸快速跑通 + 一条真实 1080p，记录显存峰值与耗时
export PATH=/root/miniconda3/bin:/usr/local/cuda/bin:$PATH
REPO=/root/FlashVSR_Plus
OUT=/root/outputs
mkdir -p "$OUT"
cd "$REPO" || exit 1
say() { echo; echo "########## $* ##########"; date '+%F %T'; }

say "环境"
python -c "import torch,flash_attn,flashvsr_attn;print('torch',torch.__version__,'cuda',torch.version.cuda,'abi',torch._C._GLIBCXX_USE_CXX11_ABI);print('flash_attn',flash_attn.__version__)"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
du -sh /root/fv/ckpts /root/fv/ckpts/* 2>/dev/null

( while true; do nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits; sleep 0.5; done ) > /root/logs/vram.txt 2>&1 &
VR=$!

say "T1 turbo 768x512 x9帧"
T0=$SECONDS
python -u -m inference.run_stream \
  --input examples/case_0.mp4 --output "$OUT/smoke_turbo_768x512.mp4" \
  --mode turbo --height 512 --width 768 --max-frames 9 2>&1 | tail -12
echo "WALL $((SECONDS-T0))s"

say "T2 turbo 2048x1152 整条样片"
T0=$SECONDS
python -u -m inference.run_stream \
  --input examples/case_1.mp4 --output "$OUT/real_turbo_2048x1152.mp4" \
  --mode turbo --height 1152 --width 2048 2>&1 | tail -14
echo "WALL $((SECONDS-T0))s"

kill $VR 2>/dev/null
say "显存峰值 (MiB)"
sort -n /root/logs/vram.txt | tail -1
say "产物"
ls -lh "$OUT"
echo "### STAGE3 DONE"
