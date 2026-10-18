#!/usr/bin/env bash
# 一条龙：setup(如需) -> build -> flash -> verify
#   bash go.sh                  # 编译当前 sketch 并烧录
#   bash go.sh --no-build       # 只烧已有固件
#   bash go.sh --factory        # 刷回卖家英文固件
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "########## 1/4 环境 ##########"
bash "$HERE/setup.sh" | tail -12

if [ "${1:-}" = "--factory" ]; then
    echo; echo "########## 2-3/4 刷保底固件 ##########"
    bash "$HERE/flash.sh" --factory || exit 1
elif [ "${1:-}" = "--no-build" ]; then
    echo; echo "########## 2-3/4 跳过编译 ##########"
    bash "$HERE/flash.sh" || exit 1
else
    echo; echo "########## 2/4 编译 ##########"
    bash "$HERE/build.sh" || exit 1
    echo; echo "########## 3/4 烧录 ##########"
    bash "$HERE/flash.sh" || exit 1
fi

echo
echo "########## 4/4 验证 ##########"
sleep 2
. "$HERE/_env.sh"
P="$(bw16_find_port)" || exit 1
"$PY" "$HERE/verify.py" "$P" 8
