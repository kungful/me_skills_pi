---
name: grsai-image-2-5
description: Generate or restyle images through the grsai API (gpt-image-2 / 2.5 family; text-to-image, image-to-image with base64 or URL references, transparent background, up to 3840x2160). Use when the user asks to 出图/生成/渲染/换风格 an image, turn a photo or 3D view into photoreal architecture or product art, or handle /v1/draw/completions, /v1/draw/result, or grsai task ids. Read the Hard Rules before any paid call.
license: MIT
compatibility: Python 3.8+; outbound HTTPS to grsai.dakka.com.cn (domestic) or grsaiapi.com (overseas); Windows/macOS/Linux.
metadata:
  origin: ECC
  api: POST /v1/draw/completions + POST /v1/draw/result
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# grsai Image Generation (gpt-image-2 / 2.5)

## When to Use

- The user asks to generate, render, restyle, or "跑一张/出一张/换风格" an image.
- The user gives a style reference photo and wants an existing image or 3D view restyled while keeping structure.
- The user wants a Blender/FreeCAD view turned into a photoreal architectural or product visual.
- Any task involving `/v1/draw/completions`, `/v1/draw/result`, model `gpt-image-2*`, or grsai task ids.

Do NOT use for: video generation, non-grsai image APIs, editing the skill's own scripts unless the user asks, or anything the Hard Rules forbid.

Sibling skill `grsai-nano-banana` covers the legacy Nano Banana route (`/v1/draw/nano-banana`, `nano-banana-*` models, 1K/2K/4K, extreme ratios) — use that one instead when the user asks for Nano Banana / Gemini image models.

## Hard Rules (read before any paid call)

1. **Every `gen` submit costs credits.** Before the first submit of a session, state model + quality + aspect + how many images and get the user's OK. Default to `gpt-image-2` for cheap tests; use `gpt-image-2.5 --quality high` for finals; `sunburst xhigh/max` and `3840x2160` only when explicitly requested.
2. **No batch spam.** One task at a time; never generate more images than the user asked for; poll interval >= 5 s; retries on `failure_reason=error` capped at 2 (the CLI default). Never loop "regenerate until it looks good" without the user driving each round.
3. **Never bypass moderation.** On `failure_reason` of `input_moderation` or `output_moderation`, stop and report. Do not rephrase to sneak content through (max one neutral rewording, only if the user asks). Never request: real identifiable people or their likeness, NSFW, gore, political figures, copyrighted characters, logos or trademarks.
4. **Key hygiene.** Never print, echo, screenshot, or commit the API key; keep it in `$GRSAI_API_KEY` or a `.grsai_key` file outside version control; never embed it in prompt text, generated images, or logs. If exposed, tell the user to rotate it.
5. **Privacy of references.** Reference images are uploaded to grsai's servers. Do not send confidential, unpublished, or NDR'd material without the user's explicit consent.
6. **Download immediately.** Result URLs expire in ~2 h. Save every result to disk right away; save into the user's current project directory with a descriptive name; never overwrite an existing file — add a numeric suffix; clean up temp files afterwards.
7. **Report facts, not wishes.** After download, read the PNG header and report the *actual* pixel size (requested aspect is not always honoured). Never claim the image matches real-world dimensions, materials, or code compliance; say it is an AI visualization.
8. **Keep geometry locked.** For re-skinning a model/photo, always send the geometry-lock paragraph from `references/prompt-templates.md` and both references (styled view + white massing). Never let the model add, remove, or move storeys, openings, or balconies silently.
9. **Fail loudly.** On HTTP errors, timeouts, or `failed` status, report the raw `failure_reason`/`error` and the task id (so `poll --id` can resume). Never hide a failure or present a stale cached image as new.
10. **Stay in scope.** Only this skill's API and scripts; quote paths containing spaces or CJK characters; UTF-8 everywhere; do not modify files outside the user's project without asking.

## Quick Start

```bash
S=~/.pi/agent/skills/grsai-image-2-5/scripts/grsai.py

# text to image
python "$S" gen -p "a red ceramic teapot on white, studio light" --out teapot.png

# image to image: references may be local paths (auto base64) or URLs
python "$S" gen -p prompt.txt -r ref_view.png ref_massing.png \
  --model gpt-image-2.5 --quality high --aspect 1536x1024 --out house.png

# 4K (sunburst only)
python "$S" gen -p prompt.txt -r ref.png --model gpt-image-2.5-sunburst \
  --quality max --aspect 3840x2160 --out big.png

# transparent cut-out
python "$S" gen -p "a single pear, product photo" --model gpt-image-2.5-flare \
  --quality high --background transparent --out pear.png

# resume an existing task / re-download
python "$S" poll --id 11-xxxxxxxx --out out.png

python "$S" models    # model/quality matrix
```

Key resolution order: `--key` → `$GRSAI_API_KEY` → `./.grsai_key` → `~/.grsai_key` (the key itself must never appear in command lines, files, or output).

Hosts: `--host domestic` (default, `https://grsai.dakka.com.cn`), `--host overseas` (`https://grsaiapi.com`), or a full URL.

## API Facts (verified)

- `POST /v1/draw/completions` with `{model, prompt, aspectRatio, quality, urls[], background?, mask?, webHook}`.
- The CLI always sends `webHook: "-1"` so the API returns `{"code":0,"data":{"id":"..."}}` immediately, then polls `POST /v1/draw/result` with `{"id": ...}`. Plain streaming (omit webHook) and real callback URLs also exist but are not used here.
- Poll response: `{id, progress 0-100, status: running|succeeded|failed, results:[{url}], failure_reason, error}`.
- `failure_reason`: `output_moderation`, `input_moderation`, `error` (Rule 3 applies to the first two; only `error` auto-retries, and credits are refunded on failure).

### Models

| model | documented quality | background | notes |
|---|---|---|---|
| gpt-image-2 | auto | no | cheapest |
| gpt-image-2-vip | medium | yes | |
| gpt-image-2.5 | auto | no | best default speed/quality |
| gpt-image-2.5-flare | low/medium/high | yes | good for cut-outs |
| gpt-image-2.5-sunburst | low/medium/high/xhigh/max | yes | highest detail, supports 3840x2160 |

The API **silently accepts undocumented quality values** (verified: `gpt-image-2.5` with `high` returns a high-detail image). The CLI warns and proceeds; `--strict-quality` hard-fails instead. Omit `--quality` to send the documented default.

### aspectRatio

Sets the **ratio**; returned pixels are model-dependent — always verify the actual file (Rule 7).

- Verified accepted: `1024x1024`, `1536x1024`, `1024x1536`, `3840x2160` (4K only on sunburst).
- Observed: `gpt-image-2` at `1024x1024` returned 1254x1254; `2048x1152` returned 1672x941; `gpt-image-2.5` at `1536x1024` and sunburst at `3840x2160` returned exactly the request.

### References (`urls`)

- Local files become `data:image/png;base64,...`; 1536x864 PNG (~0.8 MB base64) works reliably. Keep each under ~2 MB.
- Multiple references supported and recommended: **one styled view (camera/composition) + one clean white massing view (structure lock)**.
- `mask` uses the same format and only makes sense for edit-style prompts.

## Prompt Playbook

Labelled blocks, in this order (full templates in `references/prompt-templates.md`):

1. **ROLE OF THE REFERENCES** — which image sets the camera, which sets the locked structure; list locked items explicitly (storeys, floor heights, footprint, opening count/positions/widths/sill and head heights, balconies, roof + parapet, canopies, plinth); the rule that only materials, textures, joints, lighting and landscape may change.
2. **CAMERA** — eye height in metres, position, lens, vertical-line perspective correction, identical crop and sky proportion.
3. **MATERIALS AND TEXTURE** — real mm dimensions, finish, micro-relief, and light response for every element.
4. **JOINT AND DIVISION LINES** — 12-15 mm shadow-gap reveals, 20 mm recessed shadow lines under cornices/ledges/sills, 8 mm control joints, one module with no half-cut pieces, "no soft or smeared edges".
5. **GROUND / PLANTING / CONTEXT** — paving module and joints, planting species, defocused neighbours, sky.
6. **LIGHT AND RENDER** — sun direction and grazing angle, bounce, ambient occlusion, 50 mm f/8 ISO 100, neutral white balance, negatives (no people/cars/text/watermark/distortion).

## Blender View → Photoreal Workflow

1. `blender_get_scene_info` for objects/materials; `blender_execute_blender_code` printing the camera's location/rotation/lens, render resolution, and the building's bounding box (exclude the ground plane). Report these values to the user.
2. Run `scripts/blender_capture.py` through `blender_execute_blender_code`: it writes `ref_now.png` (EEVEE 1536x864) and `massing_now.png` (Workbench white massing) next to the .blend file.
3. Generate with both references and a playbook prompt; obey Hard Rules 1 and 8.
4. Report: camera values, reference files, output file (with actual pixel size), model/quality, and the style decisions taken from the user's reference photo.

## Reference Files

- `scripts/grsai.py` — CLI: `gen` / `poll` / `models`; base64 or URL references; auto-retry; immediate download; writes `<out>.url.txt`.
- `scripts/blender_capture.py` — paste into `blender_execute_blender_code`; emits the styled render + white massing render for the current camera.
- `references/prompt-templates.md` — geometry-lock paragraph, camera block, three architecture styles, product cut-out, joint/light blocks, material word bank.
