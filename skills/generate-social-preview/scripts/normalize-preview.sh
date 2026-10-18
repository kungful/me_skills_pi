#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: normalize-preview.sh <input-image> <output.png>" >&2
  exit 64
fi

input_path=$1
output_path=$2

if [[ ! -f "$input_path" ]]; then
  echo "Input image does not exist: $input_path" >&2
  exit 66
fi

if [[ -e "$output_path" ]]; then
  echo "Refusing to overwrite existing output: $output_path" >&2
  exit 73
fi

if command -v sips >/dev/null 2>&1; then
  width=$(sips -g pixelWidth "$input_path" | awk '/pixelWidth:/ { print $2 }')
  height=$(sips -g pixelHeight "$input_path" | awk '/pixelHeight:/ { print $2 }')
elif command -v magick >/dev/null 2>&1; then
  read -r width height < <(magick identify -format '%w %h' "$input_path")
else
  echo "Normalization requires macOS sips or ImageMagick (magick)." >&2
  exit 69
fi

if [[ -z "${width:-}" || -z "${height:-}" || "$height" -eq 0 ]]; then
  echo "Could not determine input dimensions." >&2
  exit 65
fi

if ! awk -v width="$width" -v height="$height" 'BEGIN {
  ratio = width / height
  delta = ratio - 2
  if (delta < 0) delta = -delta
  exit(delta > 0.02)
}'; then
  echo "Input must be approximately 2:1; got ${width}x${height}." >&2
  exit 65
fi

output_dir=$(dirname "$output_path")
mkdir -p "$output_dir"
temporary_dir=$(mktemp -d "${TMPDIR:-/tmp}/social-preview.XXXXXX")
temporary_output="$temporary_dir/preview.png"

cleanup() {
  rm -f "$temporary_output"
  rmdir "$temporary_dir" 2>/dev/null || true
}
trap cleanup EXIT

if command -v sips >/dev/null 2>&1; then
  cp "$input_path" "$temporary_output"
  sips -s format png -z 640 1280 "$temporary_output" >/dev/null
else
  magick "$input_path" -resize '1280x640!' "$temporary_output"
fi

mv "$temporary_output" "$output_path"
echo "Wrote 1280x640 social preview: $output_path"
