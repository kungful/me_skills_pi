---
name: grsai-nano-banana
description: Generate or edit images through the grsai legacy Nano Banana API (/v1/draw/nano-banana, /v1/draw/result) or the Gemini-compatible route (/v1beta/models/<model>:generateContent). Use when the user asks to 出图/生成/绘画 with Nano Banana / gemini-2.5-flash-image / nano-banana-pro, needs 1K/2K/4K output, extreme aspect ratios (1:4, 8:1), reference-image editing, webhook or polling results, or grsai task ids from a Nano Banana job. Read the Hard Rules before any paid call.
license: MIT
compatibility: Python 3.8+; outbound HTTPS to grsai.dakka.com.cn (domestic) or grsaiapi.com (overseas); Windows/macOS/Linux.
metadata:
  origin: ECC
  api: POST /v1/draw/nano-banana + POST /v1/draw/result (+ POST /v1beta/models/<model>:generateContent)
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# grsai Nano Banana (legacy API)

Companion to the `grsai-image-2-5` skill (gpt-image-2/2.5 family). Use **that** skill for
`/v1/draw/completions` + `gpt-image-*` models; use **this** one for `nano-banana*` models,
Nano Banana routes, or the Gemini-compatible endpoint.

## When to Use

- The user names **Nano Banana** / `nano-banana-*` / `gemini-2.5-flash-image` (Nano Banana is the consumer name for the Gemini image models).
- The user needs `imageSize` 1K/2K/4K, or extreme ratios (1:4, 1:8, 4:1, 8:1) that gpt-image does not offer.
- The user supplies reference images and wants them edited/composited (Nano Banana is strong at multi-reference edits and text rendering inside images).
- The user already has a Nano Banana task id to poll or re-download.

Do NOT use for: `gpt-image-*` models (use `grsai-image-2-5`), video, or anything the Hard Rules forbid.

## Hard Rules (read before any paid call)

1. **Every submit costs credits.** Before the first submit of a session, state model + imageSize + aspectRatio + cost and get the user's OK. Prices are per call and are **refunded on failure or moderation violation**; all sizes of a model cost the same. Default to `nano-banana-fast` or `nano-banana-2-lite` (¥0.022) for tests; `nano-banana-2` (¥0.06) or `nano-banana-pro` (¥0.09) for finals; `*-4k-cl` / `nano-banana-pro-4k-vip` only when explicitly requested. 4K takes much longer — say so before submitting.
2. **No batch spam.** One task at a time; never generate more images than the user asked for; poll interval >= 5 s; retries on `failure_reason=error` capped at 2. Never loop "regenerate until it looks good" without the user driving each round.
3. **Never bypass moderation.** On `failure_reason` of `input_moderation` or `output_moderation`, stop and report. No rephrasing to sneak content through. Never request: real identifiable people or likenesses, NSFW, gore, political figures, copyrighted characters, logos or trademarks.
4. **Key hygiene.** Never print, echo, log or commit the API key; keep it in `$GRSAI_API_KEY` or a `.grsai_key` file outside version control. If exposed, tell the user to rotate it.
5. **Privacy of references.** Reference images are uploaded to grsai's servers. Get explicit consent before sending confidential or unpublished material.
6. **Download immediately.** Result URLs expire in ~2 h. Save every result to disk right away, into the user's current project directory, descriptive name, never overwriting (numeric suffix if needed).
7. **Report facts, not wishes.** After download, report the *actual* pixel size read from the file; the API may not honour the requested ratio/size exactly. Never claim the image matches real-world dimensions or code compliance; it is an AI visualization.
8. **Keep geometry locked** when re-skinning references: state explicitly which structures may not change (storeys, openings, roof, footprint) — reuse the geometry-lock paragraph from `../grsai-image-2-5/references/prompt-templates.md`.
9. **Fail loudly.** Report the raw `failure_reason` / `error` and the task id (so `poll --id` can resume). Never present a stale cached image as new.
10. **Stay in scope.** Only this skill's API and scripts; quote paths containing spaces or CJK; UTF-8 everywhere.

## Quick Start

```bash
S=~/.pi/agent/skills/grsai-nano-banana/scripts/nano_banana.py

# text to image, fast/cheap
python "$S" gen -p "a cute cat playing on grass" --model nano-banana-fast --out cat.png

# prompt file + local references (auto -> base64) + 4K pro
python "$S" gen -p prompt.txt -r ref_view.png ref_massing.png \
  --model nano-banana-pro-4k-vip --size 4K --aspect 16:9 --out house.png

# extreme ratio
python "$S" gen -p "wide cinematic banner" --aspect 21:9 --out banner.png

# remote references + extreme ratio only nano-banana-2* supports
python "$S" gen -p prompt.txt -r https://a.png --model nano-banana-2 --aspect 8:1 --out strip.png

# resume an existing task / re-download before the URL expires
python "$S" poll --id 1f0e3dad-... --out out.png

python "$S" models    # model / size / ratio matrix
```

Key resolution order: `--key` → `$GRSAI_API_KEY` → `./.grsai_key` → `~/.grsai_key`.
Hosts: `--host domestic` (default, `https://grsai.dakka.com.cn`), `--host overseas` (`https://grsaiapi.com`), or a full URL.

## API Facts

### Draw route (used by this CLI)

`POST /v1/draw/nano-banana`

```json
{
  "model": "nano-banana-fast",
  "prompt": "提示词",
  "aspectRatio": "auto",
  "imageSize": "1K",
  "urls": ["https://example.com/example.png"],
  "webHook": "-1",
  "shutProgress": false
}
```

- `model` (required), `prompt` (required), `urls` (optional reference URLs or base64), `aspectRatio` (default `auto`), `imageSize` (default `1K`), `webHook`, `shutProgress` (default `false`).
- The CLI always sends `webHook: "-1"`, which makes the API return `{"code":0,"data":{"id":"..."}}` immediately; results are then fetched with `POST /v1/draw/result` `{"id": ...}`. Set `shutProgress: true` only when you do not want intermediate progress frames.
- Streaming (omit `webHook`) and real callback URLs (`POST` JSON to your endpoint) exist; see `references/api-legacy-nano-banana.md`.

### Result / poll

`POST /v1/draw/result` with `{"id": "..."}` →
`{code: 0|-22, msg, data: {id, results:[{url, content}], progress 0-100, status, failure_reason, error}}`
(`code: -22` = task does not exist).

- `status`: `running` | `succeeded` | `failed`.
- `failure_reason`: `output_moderation` (Rule 3), `input_moderation` (Rule 3), `error` (retry; credits refunded on failure).
- `results[].url` valid ~2 h — download immediately.

### Gemini-compatible route (alternative, not used by this CLI)

Same host, official Gemini format, base URL swapped and the model renamed:
`gemini-2.5-flash-image` → `nano-banana-fast`.

```
POST https://grsai.dakka.com.cn/v1beta/models/nano-banana-fast:generateContent
```

### Models

All models are billed per call; failed and moderation-rejected calls are refunded. Price is identical at 1K / 2K / 4K within a model.

| model | imageSize | CNY/call | credits | notes |
|---|---|---|---|---|
| nano-banana-2-lite | 1K | 0.022 | 440 | gemini-3.1-flash-lite-image; cheapest, fastest tests |
| nano-banana-fast | 1K | 0.022 | 440 | promo tier, strong image editing; `nano-banana` is the same flash-lite model wrapped for the image-format API |
| nano-banana | 1K | – | – | base tier |
| nano-banana-2 | 1K/2K/4K | 0.06 | 1200 | gemini-3.1-flash-image-preview, stable; adds 1:4 / 4:1 / 1:8 / 8:1 ratios |
| nano-banana-2-cl | 1K | – | – | nano-banana-2, 1K only, extra ratios |
| nano-banana-2-2k-cl | 2K | – | – | nano-banana-2, 2K only, extra ratios |
| nano-banana-2-4k-cl | 4K | – | – | nano-banana-2, 4K only, extra ratios |
| nano-banana-pro | 1K/2K/4K | 0.09 | 1800 | gemini-3-pro-image-preview, stable; best quality |
| nano-banana-pro-vt | 1K/2K/4K | – | – | |
| nano-banana-pro-cl | 1K | – | – | nano-banana-pro, 1K only |
| nano-banana-pro-vip | 1K, 2K | – | – | nano-banana-pro, no 4K |
| nano-banana-pro-4k-vip | 4K | – | – | nano-banana-pro, 4K only |

Unknown prices are shown as `–`; never invent or estimate a price — quote only what `python "$S" models` prints.

### aspectRatio

`auto` (default), `1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `3:2`, `2:3`, `5:4`, `4:5`, `21:9`.
Extra ratios **only** on `nano-banana-2`, `nano-banana-2-cl`, `nano-banana-2-2k-cl`, `nano-banana-2-4k-cl`
(the CLI rejects other models with these ratios before spending credits):
`1:4`, `4:1`, `1:8`, `8:1`.
Returned pixels are model-dependent — always verify the file (Rule 7).

### References (`urls`)

- Local files become `data:image/<mime>;base64,...`; keep each under ~2 MB.
- Multiple references are supported and recommended: one styled view (camera/composition) plus one clean white massing view (structure lock).
- Nano Banana follows text in the prompt better than gpt-image — good for labels, signage, UI mockups.

## Prompt Playbook

Same six-block structure as `../grsai-image-2-5/references/prompt-templates.md`:
1. ROLE OF THE REFERENCES (what is locked) → 2. CAMERA → 3. MATERIALS AND TEXTURE →
4. JOINT AND DIVISION LINES → 5. GROUND / PLANTING / CONTEXT → 6. LIGHT AND RENDER.
For Nano Banana add an explicit **TEXT TO RENDER** block (exact wording, position, font feel) and keep
negative constraints (no people, no cars, no watermark, no distortion).

## Reference Files

- `scripts/nano_banana.py` — CLI: `gen` / `poll` / `models`; base64 or URL references; auto-retry; immediate download; writes `<out>.url.txt`.
- `references/api-legacy-nano-banana.md` — verbatim legacy API doc (hosts, streaming, webhook, Gemini-compatible route, result polling).
- Sibling skill `../grsai-image-2-5/` — gpt-image-2/2.5 CLI, Blender capture script, prompt templates.
