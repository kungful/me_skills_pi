# -*- coding: utf-8 -*-
"""一次性脚手架：以《小兔子吃萝卜》为结构母版，生成《小象洗澡》4-6岁 课件 project.json"""
import os, sys, json
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, '项目', '小兔子吃萝卜-4-6岁', 'project.json')
DST_DIR = os.path.join(ROOT, '项目', '小象洗澡-4-6岁')

STYLE_DRAW = ("A top-down flat photograph of one sheet of off-white rice paper on a light wooden desk, "
              "even soft daylight, the paper fills the whole frame, visible paper texture, mild realistic "
              "paper shadow. Children's art class illustration, hand-drawn, flat colours, thick clean outlines, "
              "no text, no signature, no watermark.")
STYLE_PHOTO = ("Professional real-world photography, sharp focus, natural daylight, high detail, "
               "realistic colours, horizontal composition, no text, no watermark.")

LOCK = (
    "LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
    "one chubby little grey baby elephant sitting in the shallow water of a pond, facing the viewer, body "
    "tilted slightly to the left; its big round head is at the upper centre with TWO huge round floppy ears "
    "spreading out to both sides, small friendly dark eyes, a short stubby trunk curling down and slightly to "
    "the right with two tiny nostrils at the tip, small pink cheek patches, four thick stumpy legs partly in "
    "the water, and a short thin tail with a little tuft at the end. Its trunk holds ONE bright green lotus "
    "pod (a round flat-topped seed pod with 5-6 small round holes on top) together with a broad round "
    "green lotus leaf. The lotus leaf floats at the lower-left of the picture and the lotus pod is held up "
    "just right of the head at the upper centre-right. Behind them: pale blue-green water with 3-4 simple "
    "wavy water lines, a big round lotus leaf pad floating at the right, two small white lotus flowers at the "
    "upper left, and a soft pale-blue sky band with one small white cloud along the very top edge. Canvas "
    "aspect 3:2 landscape, paper centred, nothing cropped by the frame edge.")

IMAGES = [
    dict(slot="范画成品", batch="chain", prompt=
        "THIS IS THE FINISHED MASTER ARTWORK of the lesson, drawn at its very best. Everything is complete: "
        "clean marker outlines, the elephant's soft blue-grey body with a paler grey shading on its underside "
        "and inside the ears, darker grey shading along the folds of the trunk, the bright green lotus pod "
        "fully coloured with a darker green rim and dark round holes on top, the big lotus leaf coloured in "
        "two tones of green with its radiating veins drawn in a deeper green, small white lotus flowers with "
        "yellow centres, pale blue-green water with simple wavy lines, a soft pale-blue sky band and one "
        "small white cloud. The whole picture is finished, balanced and cheerful.",
        style=STYLE_DRAW, refs=[], ref_prev=False, lock=True),

    dict(slot="范画步骤1_起形", batch="chain", prompt=
        "THIS IS STEP 1 OF 5, the very first construction sketch, and it is DRAWN ONLY IN LIGHT GREY PENCIL "
        "- no marker, no ink, no colour whatsoever anywhere on the paper. Faint thin pencil construction "
        "lines only: one big circle for the head, two large flattened ovals spreading to the left and to the "
        "right for the ears, one large rounded oval for the body below, a long curved tube shape for the "
        "trunk curling down to the right, four small ovals for the stumpy legs, one thin short line for the "
        "tail, a small circle for the lotus pod held to the right of the head, and one large circle with a "
        "few radiating lines for the lotus leaf at the lower-left. Construction lines only, all strokes "
        "light, thin and faint, with no details, no eyes and no shading at all.",
        style=STYLE_DRAW, refs=[], ref_prev=False, lock=True),

    dict(slot="范画步骤2_勾线", batch="chain", prompt=
        "THIS IS STEP 2 OF 5. Continue from the reference sketch and keep the identical composition. The "
        "pencil scaffold is now traced into a clean, confident BLACK MARKER OUTLINE drawing: the round head, "
        "the two huge floppy ears, the large body, the four thick stumpy legs, the trunk curling down and to "
        "the right with its two nostrils, the short tail with the tuft, the round lotus pod held beside the "
        "head with its little holes on top, and the big round lotus leaf with radiating veins at the "
        "lower-left. Add only the outline face details in black - two small round friendly eyes and two "
        "round cheek patches. NO colour is filled in yet: the drawing is pure black outline on white paper, "
        "and the pencil construction lines are gone.",
        style=STYLE_DRAW, refs=[], ref_prev=True, lock=True),

    dict(slot="范画步骤3_涂色", batch="chain", prompt=
        "THIS IS STEP 3 OF 5. Continue from the reference outline drawing and keep the identical composition. "
        "The black outline is unchanged and the main flat colours are now blocked in, still with an EMPTY "
        "white background: the lotus pod body is filled with one flat bright green, its holes with dark "
        "green, the big lotus leaf with one flat medium green, the two inner ears with one flat pale pink, "
        "and the cheek patches with a light pink dab. The elephant's body stays plain white and unshaded. "
        "Every colour is flat, even and entirely inside its outline.",
        style=STYLE_DRAW, refs=[], ref_prev=True, lock=True),

    dict(slot="范画步骤4_加深", batch="chain", prompt=
        "THIS IS STEP 4 OF 5. Continue from the reference flat-colour stage and keep the identical "
        "composition. Now the picture gains depth while the background is STILL EMPTY white: the elephant's "
        "body is filled with a soft blue-grey and a paler grey shading is added along its underside, inside "
        "the ears and along the folds of the trunk; the lotus leaf gets a darker green on its far side with "
        "its veins drawn in an even deeper green; the lotus pod gets a darker green rim; the eyes are filled "
        "solid black with a small white highlight dot; the two white lotus flowers are coloured with pale "
        "pink edges and yellow centres. All colours remain flat marker colour inside their outlines.",
        style=STYLE_DRAW, refs=[], ref_prev=True, lock=True),

    dict(slot="范画步骤5_加背景", batch="chain", alias="范画成品"),

    dict(slot="实物_莲蓬", batch="real", prompt=
        "A few fresh real lotus pods picked from a pond, lying on a clean light wooden table, one pod cut in "
        "half to show the round seeds inside, the stems still attached, bright soft daylight from the left, "
        "soft shadow, top-down view, natural olive-green and brown colours.", style=STYLE_PHOTO),

    dict(slot="实物_荷叶", batch="real", prompt=
        "A close-up of a real fresh green lotus leaf pad lying on dark pond water, showing the round shape "
        "with a notch, the radiating veins and the water droplets on its waxy surface, natural daylight, "
        "soft blurred water background, sharp focus, natural deep green colours, horizontal composition.",
        style=STYLE_PHOTO),

    dict(slot="实物_材料工具", batch="real", prompt=
        "A neat flat-lay of children's art materials on a clean white table: a sheet of off-white rice paper, "
        "a black fine-liner pen, a handful of grey, green and blue marker pens, a pencil and an eraser, "
        "arranged tidily with even soft daylight, top-down view, no text, no watermark, no brand logos.",
        style=STYLE_PHOTO),

    dict(slot="素材_坐姿", batch="photo", prompt=
        "A cute real baby elephant sitting upright in shallow pond water, facing the camera, huge floppy "
        "ears, trunk curled, natural daylight, sharp focus, natural colours.", style=STYLE_PHOTO),
    dict(slot="素材_洗澡", batch="photo", prompt=
        "A real baby elephant in shallow water spraying water over its own back with its trunk, water "
        "droplets frozen in the air, natural daylight, sharp focus, natural colours.", style=STYLE_PHOTO),
    dict(slot="素材_面部特写", batch="photo", prompt=
        "An extreme close-up of a real baby elephant's face, showing the huge floppy ears with pale pink "
        "inner skin, the small round dark eyes, the stubby trunk with its two nostrils and the pink cheek "
        "patches, soft natural daylight, shallow depth of field.", style=STYLE_PHOTO),
    dict(slot="素材_用鼻子", batch="photo", prompt=
        "A real baby elephant holding a lotus pod up to its mouth with the tip of its trunk, standing in "
        "shallow water, natural daylight, sharp focus, natural colours.", style=STYLE_PHOTO),
    dict(slot="素材_趴着", batch="photo", prompt=
        "A real baby elephant LYING FLAT DOWN asleep on a sandy river bank, its whole body "
        "horizontal and low on the ground, all four legs folded and tucked under its belly, its "
        "head resting on the ground, eyes closed, huge floppy ears spread flat on the sand, seen "
        "from a low side angle so the lying-down posture is unmistakable and clearly different from "
        "a sitting pose, natural daylight, sharp focus, natural grey colours, no text, no watermark.",
        style=STYLE_PHOTO),
    dict(slot="素材_池塘", batch="photo", prompt=
        "A real baby elephant in a wide lotus pond with big round lotus leaves and white lotus flowers, the "
        "elephant small in the frame showing its environment, bright natural daylight, natural colours.",
        style=STYLE_PHOTO),
    dict(slot="素材_河马", batch="photo", prompt=
        "A close-up of a real baby hippo standing in the water, showing its SHORT small round ears on top of "
        "its head, its broad round muzzle and its big round body half in the water, natural daylight, sharp "
        "focus, natural grey colours.", style=STYLE_PHOTO),
]

PAGES_TEXT = {
    "intro": {"cards": [
        {"head": "课程目标", "items": [
            "1.观察实物与图片，了解小象的外形特征，学会用圆形和椭圆概括形体。",
            "2.认识莲蓬和荷叶的形状与颜色，学习用绿色表现层次。",
            "3.感受蓝灰与绿色的对比，学习画面留白与背景添画。"]},
        {"head": "课程重难点", "items": [
            "1.小象的大耳朵、长鼻子和四条粗腿的位置与比例。",
            "2.用圆形＋椭圆组合概括形体。",
            "3.莲蓬与荷叶的绿色深浅变化与画面留白。"]},
        {"head": "教学安排", "items": [
            "1.课程导入    2.主题知识    3.实物观察",
            "4.绘画知识    5.参考素材    6.范画过程"]}]},
    "knowing": {"items": [
        "1、小象的外形特征和生活习性。",
        "2、小象的长鼻子和大耳朵各有什么用。",
        "3、认识真实的莲蓬和荷叶，观察它们的形状和叶脉。",
        "4、蓝灰与绿色的对比，以及绿色的深浅变化。",
        "5、一幅完整作品的创作步骤。"]},
    "quiz": {"question": "小象和小河马都是胖胖的、住在水里，它们最大的不同在哪里呢？",
             "images": ["素材_河马", "素材_坐姿"],
             "answer": "揭晓：小象的耳朵又大又扁、鼻子长长的能卷东西；小河马的耳朵又小又圆、鼻子短短的。一起记住口诀：「象耳大扇子，鼻子长钩子」。"},
    "k1": {"title": "秘密一：小象最爱吃什么？",
           "image": "素材_用鼻子",
           "lines": ["小象是吃素的大动物，最喜欢水里的莲蓬、",
                     "嫩荷叶和嫩枝条。",
                     "它用长鼻子把食物卷起来送进嘴里，还会把水也吸进去喷着玩。"]},
    "k2": {"title": "秘密二：长长的鼻子有什么用？",
           "image": "素材_面部特写",
           "lines": ["大象的鼻子又长又灵活，像一只小手臂，",
                     "能卷起莲蓬、当水管喝水、",
                     "还能把水喷出来冲掉身上的泥巴和虫子。"]},
    "k3": {"title": "秘密三：小象的一天",
           "image": "素材_池塘",
           "lines": ["小象整天都待在水边，天热就泡在水里，",
                     "用鼻子吸水喷在身上当淋浴。",
                     "它走路慢慢的，但很爱和小河马一起玩水。"]},
    "real": {"title": "看一看：真实的莲蓬和荷叶长什么样？",
             "image": "实物_莲蓬", "image2": "实物_荷叶",
             "tasks": [
                 {"tag": "看形状", "text": "莲蓬是一个圆圆的小碗，上面有几个圆圆的小洞。"},
                 {"tag": "看叶子", "text": "荷叶是圆圆的大盘子，中间凹下去，边上有一个小缺口。"},
                 {"tag": "看颜色", "text": "莲蓬是黄绿色的，荷叶是深绿色的，叶脉更浅。"},
                 {"tag": "摸一摸", "text": "荷叶滑滑的、有一层油，莲蓬的杆子硬硬的、里面是海绵一样的。"}]},
    "knowing_tags": {"title": "小朋友们，小象的外形有什么特点呢？"},
    "parts": {"title": "小象的身体是由哪些部分组成的呢？"},
    "poses": {"title": "小象都有哪些不同的姿势呢？",
              "images": ["素材_坐姿", "素材_洗澡", "素材_用鼻子", "素材_趴着"]},
    "idea": {"title": "小象还会出现在哪里呢？", "image": "素材_池塘"},
    "swatches": {"title": "同类色小知识 —— 绿色家族"},
    "contrast": {"title": "蓝灰与绿色的对比 · 画面留白"},
}

def main():
    with open(SRC, encoding='utf-8') as f:
        d = json.load(f)

    d['meta']['name'] = "《小象洗澡》4-6岁课件"
    d['meta']['photo_note'] = "全部图片由 AI 生成，保证对题 + 可商用 + 风格统一"
    d['meta']['theme'] = {"primary": "3E9BB0", "dark": "1F6B7C", "light": "BFDDE3",
                          "accent": "F2A93B", "text": "2F4550", "cream": "FAF7F0", "grey": "595959"}
    d['lock'] = LOCK
    # ★ common.stroke 是全链条共用的线条语言，母版里写着兔子/胡萝卜 —— 换课题时必须
    #   一起改掉颜色描述，否则范画链会收到自相矛盾的指令（"白色兔子的身体" 出现在小象课里）。
    st = d['common']['stroke']
    OLD_STROKE = ("The carrot orange, the leaf green, the pink ears and the white rabbit body keep exactly "
                  "the same colours and the same line weight in the finished artwork and in the corresponding step.")
    NEW_STROKE = ("The lotus-pod green, the lotus-leaf green, the little blue-grey elephant body and its pale "
                  "pink inner ears keep exactly the same colours and the same line weight in the finished "
                  "artwork and in the corresponding step.")
    if OLD_STROKE in st:
        d['common']['stroke'] = st.replace(OLD_STROKE, NEW_STROKE)

    old = {i['slot']: i for i in d['images']}
    # 旧槽位 → 新槽位（保留母版的 style/refs 等结构性字段）
    rename = {
        "范画成品": "范画成品", "范画步骤1_起形": "范画步骤1_起形",
        "范画步骤2_勾线": "范画步骤2_勾线", "范画步骤3_涂色": "范画步骤3_涂色",
        "范画步骤4_加深": "范画步骤4_加深", "范画步骤5_加背景": "范画步骤5_加背景",
        "实物_胡萝卜": "实物_莲蓬", "实物_胡萝卜叶": "实物_荷叶", "实物_材料工具": "实物_材料工具",
        "素材_坐姿": "素材_坐姿", "素材_吃胡萝卜": "素材_洗澡", "素材_面部特写": "素材_面部特写",
        "素材_跳跃": "素材_用鼻子", "素材_趴着": "素材_趴着", "素材_草地": "素材_池塘",
        "素材_老鼠": "素材_河马",
    }
    images = []
    for spec in IMAGES:
        src_key = None
        for k, v in rename.items():
            if v == spec['slot']:
                src_key = k; break
        base = dict(old[src_key])
        base.pop('source', None); base.pop('query', None)
        base['slot'] = spec['slot']
        for k in ('prompt', 'style', 'refs', 'ref_prev', 'lock', 'alias'):
            if k in spec:
                base[k] = spec[k]
        base['model'] = 'gpt-image-2.5'
        base['quality'] = 'high'
        base['aspect'] = '1536x1024'
        if spec.get('batch') != 'chain':
            base['stroke'] = ''      # 实物/素材照片页不注入「线条语言」
        images.append(base)
    d['images'] = images

    # ---- 页面文案替换 ----
    seq = iter(['k1', 'k2', 'k3'])
    d['pages'][0]['title'] = "《小象洗澡》"
    d['pages'][0]['image'] = '范画成品'
    d['pages'][0]['uses'] = ['范画成品']
    for p in d['pages']:
        t = p['type']
        if t == 'intro':
            p['cards'] = PAGES_TEXT['intro']['cards']
        elif t == 'knowing':
            p['items'] = PAGES_TEXT['knowing']['items']
        elif t == 'quiz':
            p.update(question=PAGES_TEXT['quiz']['question'],
                     images=PAGES_TEXT['quiz']['images'],
                     answer=PAGES_TEXT['quiz']['answer'])
            p['uses'] = PAGES_TEXT['quiz']['images']
        elif t == 'knowledge':
            key = next(seq)
            p['title'] = PAGES_TEXT[key]['title']
            p['image'] = PAGES_TEXT[key]['image']
            p['lines'] = PAGES_TEXT[key]['lines']
            p['uses'] = [p['image']]
        elif t == 'real_object':
            p['title'] = PAGES_TEXT['real']['title']
            p['image'] = PAGES_TEXT['real']['image']
            p['image2'] = PAGES_TEXT['real']['image2']
            p['tasks'] = PAGES_TEXT['real']['tasks']
            p['uses'] = ['实物_莲蓬', '实物_荷叶']
        elif t == 'observe_tags':
            p['title'] = PAGES_TEXT['knowing_tags']['title']
        elif t == 'parts_diagram':
            p['title'] = PAGES_TEXT['parts']['title']
        elif t == 'poses':
            p['title'] = PAGES_TEXT['poses']['title']
            p['images'] = PAGES_TEXT['poses']['images']
            p['uses'] = PAGES_TEXT['poses']['images']
        elif t == 'idea_list':
            p['title'] = PAGES_TEXT['idea']['title']
            p['image'] = PAGES_TEXT['idea']['image']
            p['uses'] = ['素材_池塘']
        elif t == 'color_swatches':
            p['title'] = PAGES_TEXT['swatches']['title']
            p['swatches'] = ['#2E7D32', '#4CAF50', '#7CC47F', '#AED581', '#1B5E20', '#8D6E63']
        elif t == 'contrast_blank':
            p['title'] = PAGES_TEXT['contrast']['title']

    d['chain'] = {
        "order": ["范画成品", "范画步骤1_起形", "范画步骤2_勾线",
                  "范画步骤3_涂色", "范画步骤4_加深", "范画步骤5_加背景"],
        "auto_ref_prev": True, "anchor": "范画成品",
        "note": "链条正向：成品(设计基准) → 步骤1 → 步骤2 → 步骤3 → 步骤4 → 步骤5。每步参考图 = [成品锚点, 上一步]；步骤5 直接是成品的别名。",
    }

    # ★★ 页面内容整页改写 ★★
    # 说明：上面那个按 type 的循环只换了标题/图片，页面里的“实质文案”
    # （外形标签、形体拆解、姿态、联想、色卡、留白、参考素材、工具、步骤正文）
    # 还是母版《小兔子吃萝卜》的内容，而且 poses 写成了 images、
    # color_swatches 写成了 hex 字符串 —— 这两个结构错误会让装配直接崩。
    # 所以这里按页号做一次完整覆盖，保证换课题时不留旧内容。
    PAGES_FIX = {
        9: dict(schemes=[{"head": "方案A 马克笔", "items": [
            "半生熟镜面宣纸", "黑色勾线笔",
            "蓝灰色系马克笔（浅蓝灰/中蓝灰）",
            "绿色马克笔（草绿/深绿）",
            "粉色马克笔（耳朵里面/脸颊）", "铅笔、橡皮"]}]),
        10: dict(tags=["圆圆的大脑袋", "两只大扇子耳朵", "圆圆的小眼睛",
                       "长长的鼻子", "圆滚滚的身体", "细细的小尾巴"]),
        11: dict(figure_note="圆形 + 大椭圆 = 一只小象",
                 figure={"body": [2.15, 3.55, 3.10, 2.05],
                         "head": [2.85, 2.25, 1.70, 1.60],
                         "ear_left": [1.90, 2.10, 1.10, 1.50],
                         "ear_right": [4.50, 2.10, 1.10, 1.50],
                         "trunk": [3.55, 3.50, 0.55, 1.35],
                         "leg_front": [2.50, 5.25, 0.80, 0.60],
                         "leg_back": [3.90, 5.25, 0.80, 0.60],
                         "tail": [1.75, 4.15, 0.55, 0.50]},
                 parts=[{"name": "头部", "desc": "圆圆的大脑袋"},
                        {"name": "耳朵", "desc": "两只大椭圆"},
                        {"name": "身体", "desc": "一个大椭圆"},
                        {"name": "鼻子", "desc": "长长的弯管"},
                        {"name": "四肢", "desc": "粗粗的四条"},
                        {"name": "尾巴", "desc": "细细的小尾巴"}]),
        12: dict(items=[{"image": "素材_坐姿", "label": "坐着"},
                       {"image": "素材_洗澡", "label": "喷水洗澡"},
                       {"image": "素材_用鼻子", "label": "卷东西"},
                       {"image": "素材_趴着", "label": "趴着休息"}]),
        13: dict(list_head="想一想，还可以怎么画？",
                 items=["在池塘里给自己喷水洗澡", "用长鼻子卷起莲蓬",
                        "和好朋友小河马一起玩水", "躲在荷叶下面乘凉",
                        "在草地上慢慢散步"]),
        14: dict(swatches=[{"hex": "CBE08A", "name": "黄绿", "use": "亮部"},
                          {"hex": "A5C45C", "name": "草绿", "use": "中间色"},
                          {"hex": "77A65A", "name": "橄榄绿", "use": "固有色"},
                          {"hex": "4A6B2E", "name": "墨绿", "use": "暗部"}],
                 note_head="画荷叶和莲蓬的时候，不要只用一种绿色：",
                 note="先用草绿铺满荷叶，再用墨绿画背光的暗部，最后用黄绿在亮的地方提一笔 —— 叶子立刻就有了立体感。"),
        15: dict(figure_note="小象的身体要留白，不要涂满",
                 tips=[{"no": "①", "text": "蓝灰和绿色放在一起很清爽，一个安静、一个活泼，互相衬托。"},
                       {"no": "②", "text": "小象的身体用浅浅的蓝灰来画，肚皮和耳朵里可以再浅一点。"},
                       {"no": "③", "text": "荷叶和莲蓬用深浅不同的绿色，画在周围衬托小象。"},
                       {"no": "④", "text": "留白多一分，画面就透气一分，看起来更干净。"}]),
        16: dict(head="素 材 参 考",
                 hint="观察真实照片里小象的姿势，还有它大耳朵和长鼻子的角度。",
                 images=["素材_坐姿", "素材_趴着"],
                 uses=["素材_坐姿", "素材_趴着"]),
        17: dict(head="细 节 参 考",
                 hint="看看小象的脸：大大的耳朵、圆圆的眼睛、卷起来的长鼻子和细细的小尾巴。",
                 images=["素材_面部特写", "素材_用鼻子"],
                 uses=["素材_面部特写", "素材_用鼻子"]),
        18: dict(head="场 景 参 考",
                 hint="小象在哪里？池塘里、荷叶丛中、草地边，背景可以怎么画？",
                 images=["素材_池塘", "实物_荷叶"],
                 uses=["素材_池塘", "实物_荷叶"]),
        19: dict(schemes=[{"head": "方案A · 马克笔（推荐）", "tools": [
            {"no": "1", "name": "半生熟镜面宣纸", "desc": "纸上有纹理，颜色更柔和"},
            {"no": "2", "name": "黑色勾线笔", "desc": "勾轮廓、画五官和鼻子"},
            {"no": "3", "name": "蓝灰色系马克笔", "desc": "浅蓝灰、中蓝灰各一支"},
            {"no": "4", "name": "绿色马克笔", "desc": "草绿、深绿，画荷叶和莲蓬"},
            {"no": "5", "name": "粉色马克笔", "desc": "涂耳朵里面和脸颊"},
            {"no": "6", "name": "铅笔和橡皮", "desc": "先起形，画得要轻"}]}]),
        20: dict(text="先用铅笔画出一个大圆（头）和两个大椭圆（耳朵），再画一个大椭圆（身体），"
                      "加上弯弯的长鼻子和四条粗腿，最后画出手里卷着的莲蓬和荷叶。",
                 tips=["把纸横着放，小象画在正中间", "耳朵要画得又大又圆，向两边展开",
                       "线条要轻，画错了可以擦掉"]),
        21: dict(text="用黑色勾线笔把铅笔线描成干净流畅的实线，再添上圆圆的小眼睛、微笑的嘴巴、"
                      "两个小鼻孔和莲蓬上圆圆的小洞。",
                 tips=["线要一笔画到底，不要来回描", "记住：一步一条线，线条要干净",
                       "先画外轮廓，再画里面的五官"]),
        22: dict(text="给莲蓬涂上亮绿色、荷叶涂上中等绿色，耳朵里面和脸颊涂上浅粉色 —— "
                      "只平涂一遍，先不管深浅。",
                 tips=["莲蓬用亮绿，荷叶用草绿，不要涂到线上", "耳朵里面的粉色要涂得淡淡的",
                       "小象的身体先不要涂，留着留白"]),
        23: dict(text="给小象的身体涂上浅浅的蓝灰色，肚皮和耳朵里面更浅一点；荷叶用深绿画暗部，"
                      "眼睛涂黑并留一个小白点。",
                 tips=["暗部只画在一边，画面才有立体感",
                       "眼睛涂黑，记得留一个小白点当高光",
                       "蓝灰要涂得均匀，不要涂出轮廓"]),
        24: dict(text="在周围画上淡淡的水波纹、几片小荷叶、两朵白荷花和一小条蓝天，"
                      "最后写上作品名称、签上自己的名字。",
                 tips=["背景从下往上画，先水面再天空", "水波用蓝色轻轻画几条，不要涂满",
                       "签名写在右下角小小的位置"]),
        25: dict(note="完整画面要有：蓝灰的小象 + 深浅变化的绿色荷叶与莲蓬 + 浅浅的水波背景 + "
                      "适当的留白。别忘记写上作品名称、签上名字哦！"),
        26: dict(share=["1、小象的耳朵是什么形状的？它的长鼻子能做什么？",
                        "2、画荷叶和莲蓬的时候，你用了哪几种绿色？"],
                 summary=["1、本节课先观察真实的莲蓬、荷叶和小象照片，了解小象的外形特征，"
                          "学习用圆形和大椭圆概括动物形体，让孩子学会“先看再画”。",
                          "2、通过蓝灰与绿色的对比以及画面留白，让孩子理解“不涂满”也是"
                          "一种画面语言，提高孩子的画面控制力。",
                          "3、通过绿色同类色的分层上色，让孩子感受颜色的深浅变化，"
                          "画面既清爽又有层次，童趣十足。"]),
    }
    for _n, _kw in PAGES_FIX.items():
        d['pages'][_n - 1].update(_kw)
    # poses 结构错写在 images，清掉免得渲染器认错
    d['pages'][11].pop('images', None)

    os.makedirs(DST_DIR, exist_ok=True)
    for sub in ('img', 'img_sell', 'out'):
        os.makedirs(os.path.join(DST_DIR, sub), exist_ok=True)
    with open(os.path.join(DST_DIR, 'project.json'), 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    print('已生成：%s' % DST_DIR)
    print('  %d 页 / %d 个槽位' % (len(d['pages']), len(d['images'])))


if __name__ == '__main__':
    main()