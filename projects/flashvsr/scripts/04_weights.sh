#!/bin/bash
# 权重下载：HF 机房链路每连接几百 KB 就断，靠多连接 + 无限重试硬啃
export PATH=/root/miniconda3/bin:$PATH
B=https://huggingface.co/ruchangyao/FlashVSR_plus/resolve/main
D=/root/fv/ckpts
DL="/root/miniconda3/bin/python -u /root/build/dl.py"
mkdir -p "$D"
$DL $B/TCDecoder.ckpt "$D/TCDecoder.ckpt" 12
$DL $B/turbo/dit.safetensors "$D/turbo/dit.safetensors" 28
$DL $B/turbo/lq_proj_in.safetensors "$D/turbo/lq_proj_in.safetensors" 16
$DL $B/Wan2.1_VAE.pth "$D/Wan2.1_VAE.pth" 8
if [ "${WITH_BASE:-0}" = "1" ]; then
  $DL $B/base/dit.safetensors "$D/base/dit.safetensors" 28
  $DL $B/base/lq_proj_in.safetensors "$D/base/lq_proj_in.safetensors" 16
fi
echo "### WEIGHTS_ALL_DONE"
du -sh $D $D/* 2>/dev/null
