# 手机端发布 + 关联「个人售卖」商品（2026-11 首次打通，已验证）

什么时候走这条路，而不是 `publish_post.py`：

| 目标 | 走哪条 |
|---|---|
| 只发一条笔记（不挂商品） | `publish_post.py`（MCP/HTTP，快、有台账核实） |
| **笔记要挂「个人售卖」商品卡（¥9.9 这种）** | **手机 App**：`个人售卖 → 我发布的 → 该商品「发笔记」** |
| 商品要自动发网盘链接给买家 | 手机 App：商品「…」→ 设置自动发货 |

> MCP 发布接口**没有挂商品的字段**。笔记里的商品卡只能从 App 的「发笔记」入口产生，
> 这样发出去的笔记底部会自动出现 `个人售卖 · 商品名 · ¥9.9` 卡片，商品行也会变成 `已关联笔记`。

---

## 0. 前置：adb + 中文输入

```bash
ADB="C:/Users/hua/Documents/platform-tools/adb"
$ADB devices            # 必须能看到设备；无线调试也行
$ADB shell wm size      # 本项目实测 1260x2800
```

**`adb shell input text` 不能输中文**（`java.lang.NullPointerException: Attempt to get length of null array`）。
装 ADBKeyboard 解决（一次装好，长期可用）：

```bash
curl -sL -o ADBKeyboard.apk https://github.com/senzhk/ADBKeyBoard/raw/master/ADBKeyboard.apk
$ADB install -r ADBKeyboard.apk      # vivo 会弹「外部来源应用」→ 勾「已了解风险」→ 继续安装
$ADB shell ime enable com.android.adbkeyboard/.AdbIME
$ADB shell ime set    com.android.adbkeyboard/.AdbIME
```

输中文（base64 最稳，避免 Windows 控制台编码问题）：

```bash
B=$(python -c "import base64;print(base64.b64encode('波点爬出来了9-12课件26页'.encode()).decode())")
$ADB shell am broadcast -a ADB_INPUT_B64 --es msg "$B"
$ADB shell am broadcast -a ADB_CLEAR_TEXT          # 清空当前输入框
```

做完**必须还原输入法**，否则用户拿手机打字会一脸懵：

```bash
$ADB shell ime set com.sohu.inputmethod.sogou.vivo/.SogouIME
```

### ADBKeyboard 的一个硬坑：首次聚焦「未提交」态

小红书（以及部分自定义输入框）第一次点进去时，界面**能显示**你提交的文字，
但计数器还是 `0/20`、点确认报「内容不能为空」——文字只进了渲染层，没进 App 的文本模型。

**解法**：先发一个**按键**让输入框真正激活，再提交中文：

```bash
$ADB shell input keyevent 7        # 打一个 "0"，计数变 1/20 即代表按钮（监听器）生效
$ADB shell am broadcast -a ADB_CLEAR_TEXT
$ADB shell am broadcast -a ADB_INPUT_B64 --es msg "$B"
```

判据：右上角计数从 `0/20` 变成实际字数 → 再点确认。停在 0 就是没进去。

---

## 1. 上架「个人售卖」商品

路径：`我` → 左上「个人售卖」→「去创建」（或底部「创建商品/服务」）

| 字段 | 填什么 | 注意 |
|---|---|---|
| 商品/服务描述（名称） | `波点爬出来了9-12课件26页` | **≤20 字**，右下角实时计数；这是唯一文本位，没有长描述框 |
| 图片 | 成品 3:4 封面 | 相册「全部」→ 见下面「图怎么排到第一」 |
| 价格 | `9.9` | 数字键盘；小数点要点键，`input text "9.9"` 会丢掉点变成 99 |
| 发货方式 | **无需邮寄** | 虚拟商品；默认是「包邮」，要手动改 |
| 可售数量 | **不限数量** | 数字商品没有库存 |
| → 确认 | | 成功后出现在「我发布的」 |

### 把网盘链接挂成自动发货

`我发布的` → 该商品右侧 **「…」→ 设置自动发货** → 开关 ON → **发货说明**里贴：

```
感谢购买❤《波点爬出来了》9-12岁美术课件
网盘链接：https://pan.baidu.com/s/xxxxxxxx 提取码：xxxx
内含 PPTX + PDF + 15张高清原图，永久有效，可编辑可打印。
```

→ 确定。商品行随后显示 `已设置自动发货`（买家付款后私信自动下发这条）。
链接来源：`工厂/netdisk_publish.py` 产出的那一份，**一课题一链接**（见主 SKILL 的硬线）。

### 定价与「店铺 vs 个人售卖」

- 单套课件参考价 **¥9.9**（3 套 ¥24.9 / 全店 ¥99 / 会员 ¥199，见 `项目/糖葫芦-4-6岁/商品素材/上架文案.md`）。
- **开正式店铺**要 ≥1000 粉丝 + 营业执照 + ¥1000 保证金；粉丝不够时「个人售卖」可以先用（本次实测 52 粉就能上架、能挂到笔记底部）。
- 商品名里塞页数（`…课件26页`）比只写年龄好卖：买家第一眼判断“值不值”。

---

## 2. 发笔记并自动关联商品

`个人售卖` → `我发布的` → 目标商品那一行点 **「发笔记」**
（**不要**点底部「+」发，那样不会挂商品）。

1. 直接进相册（「全部」）→ 点缩略图**右上角的圆圈**多选（点图片本体是进预览，不是选中）
2. 底部 `下一步(n)` → 编辑页（可加音乐/滤镜，跳过）→ 右上 `下一步`
3. 正文编辑页：`添加标题` → `添加正文`
4. 填写顺序很关键，**每段都是「先 keyevent 激活 → CLEAR → 提交」**
5. 发布前逐项核对底部开关：
   - `公开可见`（要卖东西就别用「仅自己可见」）
   - **`已添加个人售卖`**（红字，说明商品挂上了）
6. `发笔记` → 等 5~10 秒 → 会自动退回「我发布的」

标题/正文/标签的内容来源：`prep_post.py` 生成的 `post.json`
（`title` ≤20 字、`content` 已去掉所有交易词、`tags` ≤10 个），**不要现场手写**。

话题当正文尾部追加即可（一次提交，不用逐个选联想词）：

```
\n\n#创意美术 #美术课件 #美术老师 #少儿美术 #小学美术 #马克笔 #9到12岁 #课件分享
```

---

## 3. 发布后的核实（两条都要看）

1. **笔记底部有商品卡**：打开笔记 → 滑到底 → 应出现 `个人售卖 · 波点爬出来了9-12课件26页 · ¥9.9`
2. **商品行有 `已关联笔记`**：`我发布的` → 该商品标签从只有 `已设置自动发货`
   变成 `已关联笔记` + `已设置自动发货`

再跑一次台账同步，把这篇登记进去（否则下次 `--next` 会再发一遍）：

```bash
python C:/Users/hua/.pi/agent/skills/xhs-courseware-post/scripts/published.py --sync
python C:/Users/hua/.pi/agent/skills/xhs-courseware-post/scripts/published.py --list   # 未发课题应为 0
```

---

## 4. 图片怎么进手机、怎么排到相册第一

```bash
# 落盘到 DCIM/Camera，并写 EXIF 时间，否则相册按拍摄时间排序会把新图甩到末尾
python -c "
from PIL import Image
now='2026:11:08 12:25:00'
im=Image.open(r'C:/.../01_cover.jpg').convert('RGB')
ex=Image.Exif(); ex[306]=now; ex[36867]=now; ex[36868]=now
im.save(r'C:/Users/hua/push_1.jpg', quality=93, exif=ex)"
MSYS_NO_PATHCONV=1 $ADB push "C:/Users/hua/push_1.jpg" /sdcard/DCIM/Camera/bdl_1.jpg
MSYS_NO_PATHCONV=1 $ADB shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE \
  -d file:///sdcard/DCIM/Camera/bdl_1.jpg
```

- 文件名用 ASCII，**别用中文**（`adb push` 经 git-bash 会被路径转换坑）
- `MSYS_NO_PATHCONV=1` 必须有，否则 `/sdcard/...` 会变成 `C:/Program Files/Git/sdcard/...`
- 没有 EXIF 时间 → 图会排在相册很后面，找起来极烦

---

## 5. 点偏位怎么办：永远用 uiautomator 拿坐标

手机截图缩略图换算坐标**必然不准**（我因此在「发笔记」按钮下方 40px 空点了 3 次，都没反应）。
正确做法——先 dump 再点：

```bash
MSYS_NO_PATHCONV=1 $ADB shell uiautomator dump /sdcard/ui.xml
MSYS_NO_PATHCONV=1 $ADB pull /sdcard/ui.xml "C:/Users/hua/ui.xml"
python - <<'EOF'
import re
s=open(r'C:\Users\hua\ui.xml',encoding='utf-8').read()
for m in re.finditer(r'<node[^>]*/?>', s):
    t=re.search(r'text="([^"]*)"',m.group(0)); b=re.search(r'bounds="(\[[^"]*\])"',m.group(0))
    if t and t.group(1).strip(): print(t.group(1),'||',b.group(1))
EOF
```

`bounds="[x1,y1][x2,y2]"` → 点击 `((x1+x2)/2, (y1+y2)/2)`。

- 小红书里 `clickable` 常为 `false`（自定义 View），**以 text 的 bounds 为准**，别因为 clickable=false 就跳过
- 相册页只有 `关闭` 一个可读节点（Flutter/Compose 渲染），坐标只能靠截图 + 精确换算：
  `屏幕坐标 = 缩略图坐标 × (1260/缩略图宽, 2800/缩略图高)`
- 小红书**创建/编辑表单里不要按 `keyevent 4`**：会直接退回列表并丢掉整张表单（实测填了 12/20 的名称+图+价格全没了）。要收键盘就点页面上的 `完成`，或点空白处。

---

## 6. 一次完整实测（可对照复现）

```
12:21  个人售卖 → 我发布的
12:27  商品「发笔记」→ 相册 → 选 2 图 → 下一步 x2
12:39  标题（keyevent 7 → CLEAR → B64）→ 20/20
12:41  正文 844 字 → 尾部追加 8 个话题
12:43  公开可见 ✓  已添加个人售卖 ✓
12:44  发笔记 → 退回「我发布的」
12:48  笔记已上线（0 浏览），底部商品卡 ¥9.9 ✓
12:49  商品行出现「已关联笔记」✓
```

耗时约 25 分钟，其中一半花在「点偏 + 表单被 back 清空」上，按本文操作可压到 8~10 分钟。
