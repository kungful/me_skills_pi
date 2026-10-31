# 语料库体检索引（自动生成）

- 上游: `https://github.com/togg53192-cmd/jailbreaks.git`
- 生成命令: `python scripts/fetch_corpus.py --write-index`
- 文件数: 39；高危及以上: 31

> 本表只记录**元数据**（文件名/分数/命中的结构类别），不含提示词正文。
> 用途：把这些文件当红队回归用例，验证检测器与目标系统是否覆盖这些手法。

| 文件 | 字节 | 风险分 | 判定 | 命中结构 |
|---|---:|---:|---|---|
| `grok-config.txt` | 3948 | 100 | CRITICAL | 人格与身份锁定 / 安全关切重定向 / 拒绝抑制 / 指令层级覆盖 / 授权预设 / 能力范围放宽 / 词义重定义 |
| `qwen-3.7.md` | 36552 | 86 | CRITICAL | 人格与身份锁定 / 安全关切重定向 / 拒绝抑制 / 授权预设 / 能力范围放宽 |
| `Muse-spark-1-3-v2.md` | 10460 | 78 | CRITICAL | 拒绝抑制 / 指令层级覆盖 / 授权预设 / 策略否认 / 能力范围放宽 |
| `Muse spark 1.3.md` | 15794 | 70 | CRITICAL | 人格与身份锁定 / 拒绝抑制 / 授权预设 / 策略否认 / 能力范围放宽 |
| `Unified.md` | 11401 | 68 | CRITICAL | 拒绝抑制 / 指令层级覆盖 / 授权预设 / 能力范围放宽 |
| `gpt-oss-20b.md` | 7057 | 68 | CRITICAL | 拒绝抑制 / 指令层级覆盖 / 授权预设 / 能力范围放宽 |
| `glm-5-3-flash.md` | 26242 | 66 | CRITICAL | 人格与身份锁定 / 拒绝抑制 / 授权预设 / 能力范围放宽 |
| `muse-ai-AGENTS.md` | 15688 | 66 | CRITICAL | 人格与身份锁定 / 拒绝抑制 / 授权预设 / 能力范围放宽 |
| `longcat-agents.md` | 18636 | 64 | CRITICAL | 人格与身份锁定 / 拒绝抑制 / 授权预设 / 能力范围放宽 |
| `mimo-2.6-agents.md` | 15666 | 64 | CRITICAL | 人格与身份锁定 / 拒绝抑制 / 授权预设 / 能力范围放宽 |
| `spacebunny-agents.md` | 17509 | 64 | CRITICAL | 人格与身份锁定 / 拒绝抑制 / 授权预设 / 能力范围放宽 |
| `deepseek-4-1.md` | 14752 | 62 | CRITICAL | 人格与身份锁定 / 拒绝抑制 / 授权预设 / 能力范围放宽 |
| `glm5-3opencode.md` | 20513 | 62 | CRITICAL | 人格与身份锁定 / 拒绝抑制 / 授权预设 / 能力范围放宽 |
| `qwen-3.8.md` | 14752 | 62 | CRITICAL | 人格与身份锁定 / 拒绝抑制 / 授权预设 / 能力范围放宽 |
| `nemotron-3-ultra.md` | 17543 | 60 | CRITICAL | 人格与身份锁定 / 拒绝抑制 / 授权预设 / 能力范围放宽 |
| `opus v1.md` | 19538 | 60 | CRITICAL | 人格与身份锁定 / 安全关切重定向 / 拒绝抑制 / 能力范围放宽 |
| `Grok build.md` | 7994 | 58 | HIGH | 拒绝抑制 / 授权预设 / 策略否认 / 能力范围放宽 |
| `opus v2.md` | 26422 | 58 | HIGH | 人格与身份锁定 / 安全关切重定向 / 指令层级覆盖 / 策略否认 |
| `Gemini-4-Argon.md` | 13936 | 56 | HIGH | 拒绝抑制 / 授权预设 / 策略否认 / 能力范围放宽 |
| `Mistral-Large-4.md` | 20767 | 56 | HIGH | 人格与身份锁定 / 指令层级覆盖 / 授权预设 / 能力范围放宽 |
| `grok-4.7.md` | 5190 | 54 | HIGH | 指令层级覆盖 / 授权预设 / 能力范围放宽 |
| `kimik3.1.md` | 10684 | 54 | HIGH | 拒绝抑制 / 授权预设 / 能力范围放宽 |
| `BigPickle-opencode.md` | 25462 | 52 | HIGH | 人格与身份锁定 / 指令层级覆盖 / 能力范围放宽 |
| `Step-5-preview.md` | 22927 | 48 | HIGH | 授权预设 / 策略否认 / 能力范围放宽 |
| `kimi-k3-agents.md` | 14664 | 46 | HIGH | 授权预设 / 策略否认 / 能力范围放宽 |
| `deepseek v4.md` | 13026 | 40 | HIGH | 拒绝抑制 / 能力范围放宽 |
| `gemma4.md` | 12977 | 40 | HIGH | 拒绝抑制 / 能力范围放宽 |
| `glm-5.2.md` | 13657 | 40 | HIGH | 拒绝抑制 / 能力范围放宽 |
| `glm-zcode-5.2.md` | 12934 | 40 | HIGH | 拒绝抑制 / 能力范围放宽 |
| `kimi-k2.md` | 12939 | 40 | HIGH | 拒绝抑制 / 能力范围放宽 |
| `deepseek v3.md` | 12591 | 38 | HIGH | 拒绝抑制 / 能力范围放宽 |
| `glm-zcode-5.3-AGENTS.md` | 3214 | 26 | MEDIUM | 授权预设 / 能力范围放宽 |
| `README.md` | 8632 | 24 | MEDIUM | 人格与身份锁定 / 指令层级覆盖 |
| `Muse-wonder.md` | 13483 | 18 | MEDIUM | 能力范围放宽 |
| `Sonnet v2.md` | 7998 | 16 | LOW | 安全关切重定向 |
| `sonnet v1.md` | 4893 | 14 | LOW | 安全关切重定向 |
| `glm-zcode-5.3.md` | 3562 | 12 | LOW | 授权预设 |
| `Beam.md` | 10645 | 10 | LOW | 指令层级覆盖 |
| `qwen-preferences.md` | 1 | 0 | INFO | — |
