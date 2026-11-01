#!/bin/bash
# FlashVSR+ —— stage 2/4: 下载模型权重
set -uo pipefail
export PATH=/root/miniconda3/bin:/usr/local/cuda/bin:$PATH
REPO=/root/FlashVSR_Plus
CK=$REPO/ckpts
M=https://hf-mirror.com

say() { echo; echo "########## $* ##########"; date '+%F %T'; }
dl() { # url outfile
  echo "-> $2"
  wget -c -q --show-progress --progress=dot:giga --tries=8 --timeout=60 -O "$2" "$1" \
    && echo "   ok $(du -h "$2" | cut -f1)" || echo "   FAIL $2"
}

mkdir -p "$CK/turbo" "$CK/base" "$CK/v1"

say "turbo + base + TCDecoder + VAE (ruchangyao/FlashVSR_plus)"
dl "$M/ruchangyao/FlashVSR_plus/resolve/main/turbo/dit.safetensors"          "$CK/turbo/dit.safetensors"
dl "$M/ruchangyao/FlashVSR_plus/resolve/main/turbo/lq_proj_in.safetensors"    "$CK/turbo/lq_proj_in.safetensors"
dl "$M/ruchangyao/FlashVSR_plus/resolve/main/base/dit.safetensors"           "$CK/base/dit.safetensors"
dl "$M/ruchangyao/FlashVSR_plus/resolve/main/base/lq_proj_in.safetensors"     "$CK/base/lq_proj_in.safetensors"
dl "$M/ruchangyao/FlashVSR_plus/resolve/main/TCDecoder.ckpt"                  "$CK/TCDecoder.ckpt"
dl "$M/ruchangyao/FlashVSR_plus/resolve/main/Wan2.1_VAE.pth"                  "$CK/Wan2.1_VAE.pth"

say "v1 (JunhaoZhuang/FlashVSR-v1.1)"
dl "$M/JunhaoZhuang/FlashVSR-v1.1/resolve/main/dit.safetensors"              "$CK/v1/dit.safetensors"
dl "$M/JunhaoZhuang/FlashVSR-v1.1/resolve/main/lq_proj_in.safetensors"        "$CK/v1/lq_proj_in.safetensors"

say "prompt tensor"
ls -l "$REPO/prompt_tensor/" || true

say "结果"
du -sh "$CK"/* ; echo; find "$CK" -type f -size -1k -printf '%s %p  <-- 太小，可能下成错误页\n'
du -sh "$CK"
df -h / | tail -1
say "STAGE2 DONE"
