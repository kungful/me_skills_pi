# -*- coding: utf-8 -*-
"""把已有的《大熊猫吃竹子》迁移成 项目/大熊猫吃竹子-4-6岁/project.json 标准项目"""
import os, sys, json, shutil
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD = os.path.join(ROOT, '4-6岁', '大熊猫吃竹子')
NEW = os.path.join(ROOT, '项目', '大熊猫吃竹子-4-6岁')

# ---------------- prompt 素材 ----------------
LOCK = ("LOCKED COMPOSITION - every stage must keep exactly this layout, only the level of completion changes: "
        "a chubby giant panda cub sitting and facing the viewer, body tilted slightly to the left; "
        "its head is at the upper centre with two round ears on top, big black eye patches, small smile, pink cheeks; "
        "it holds ONE bamboo stalk diagonally across its chest with both front paws, the stalk runs from the "
        "lower-left corner up to the upper-right, with three slender leaves sprouting at the top; "
        "its small round tail sticks out on the left side; the panda occupies the centre of the paper. ")

PAPER = ("A top-down flat photograph of one sheet of off-white rice paper on a light wooden desk, even soft daylight, "
         "the paper fills the whole frame, visible paper texture, mild realistic paper shadow. ")
MARKER = ("Children's art class illustration, hand-drawn MARKER and crayon style on textured off-white rice paper, "
          "sage green and olive green palette with warm beige and soft grey, bold clean black outlines, flat marker "
          "coloring, cute kindergarten art lesson example. no text, no letters, no numbers, no watermark, no signature. ")
PHOTO = ("Professional real-world photography, sharp focus, natural daylight, high detail, realistic colours, "
         "horizontal composition, no text, no watermark. ")
WATER = ("Children's art class illustration painted in CHILLED WATERCOLOUR (水粉) style on off-white rice paper: soft "
         "wobbly washes, visible brush strokes, granulating pigment, gentle colour bleeding at the edges, slightly "
         "uneven handmade watercolour texture, matte finish. no text, no letters, no watermark. ")

S_FINAL = ("THIS IS THE FINISHED MASTER ARTWORK of the lesson, drawn at its very best. Everything is complete: "
           "solid black ears, black eye patches, black front legs, black hind legs and a black shoulder band; "
           "the face, belly and back are left as clean white paper; the bamboo stalk is light yellow-green on the lit "
           "side and dark olive green on the shadow side with two visible bamboo nodes; three slender bamboo leaves; "
           "soft pink blush on the cheeks; and the background is filled with a cluster of sage-green and olive bamboo "
           "leaves at the lower left, three small smooth grey stones at the lower right, three short grass tufts, plus "
           "four small warm yellow dots as decoration. Generous clean rice-paper margin around the whole drawing. "
           "This is the finished display piece for a children's art lesson.")
S1 = ("THIS IS STEP 1 OF 5, the very first construction stage. Show ONLY the light pencil scaffolding of the locked "
      "composition: a large circle for the head in the upper centre, a big tilted oval for the body, two tiny "
      "half-circle ears, four short rounded-rectangle leg shapes, a small circle for the tail, and a long thin tilted "
      "line across the chest for the bamboo stalk. Thin pale grey PENCIL lines only. NO colouring, NO black marker "
      "areas, NO leaves, NO background, NO stones, NO yellow dots. Completely unfinished empty white rice paper all "
      "around the faint sketch. The sketch is small and centred.")
S2 = ("THIS IS STEP 2 OF 5. Continue from the reference sketch and keep the identical composition. The pencil scaffold "
      "is now traced into a clean, confident BOLD BLACK MARKER OUTLINE drawing: the full head, the two round ears, the "
      "eyes, the nose, a smiling mouth, the arms and legs, the small tail, and the bamboo stalk with its three leaves. "
      "The drawing is complete and correct as an outline. But NOTHING is filled in yet: all areas are still white "
      "paper - no black fur areas, no green, no background. Still an unfinished stage, blank white rice paper around "
      "the drawing.")
S3 = ("THIS IS STEP 3 OF 5. Continue from the reference outline and keep the identical composition. Now the BLACK fur "
      "areas are filled in with solid black marker: the two ears, the two eye patches, both front legs, both hind legs "
      "and the shoulder band across the back. Add tiny white highlight dots inside the eye patches so the eyes look "
      "shiny. Add a light cool grey shadow along the right edge of the body. The face, belly and back stay clean WHITE "
      "paper. The bamboo stalk and leaves are still UNCOLOURED. No green yet, no background, no stones, no yellow dots.")
S4 = ("THIS IS STEP 4 OF 5. Continue from the reference and keep the identical composition and the same solid black "
      "areas. Now the bamboo is coloured: the stalk is light yellow-green on the lit side and dark olive green on the "
      "shadow side, with two visible bamboo nodes drawn as short horizontal bands, and the three leaves are layered "
      "greens - bright yellow-green, grass green, deep green. Add soft PINK blush on both cheeks. The panda body stays "
      "white. The background is still EMPTY white rice paper - no leaves, no stones, no yellow dots.")
S5 = ("THIS IS STEP 5 OF 5, THE FINAL STEP. Continue from the reference and keep the identical composition, the same "
      "colours and the same black areas - this is the finished artwork, complete. Now fill the background in a simple "
      "childlike way: a cluster of sage-green and olive bamboo leaves at the LOWER LEFT, three small smooth grey stones "
      "at the LOWER RIGHT, three short grass tufts, and four small warm yellow dots as decoration. The finished picture "
      "is balanced, colourful and full, filling the paper nicely.")

CHAIN_ORDER = ['范画成品', '范画步骤1_起形', '范画步骤2_勾线', '范画步骤3_涂黑', '范画步骤4_上色', '范画步骤5_加背景']

images = []
def IM(slot, batch, prompt, style, refs=(), prev=False, lock=False, model='gpt-image-2.5'):
    images.append(dict(slot=slot, batch=batch, prompt=prompt.strip(), style=style.strip(),
                       model=model, quality='high', aspect='1536x1024',
                       refs=list(refs), ref_prev=prev, lock=lock))

IM('范画成品', 'chain', S_FINAL, PAPER + MARKER, refs=['01_封面主视觉'], lock=True)
IM('范画步骤1_起形', 'chain', S1, PAPER + MARKER, refs=['范画成品'], lock=True)
for slot, txt in [('范画步骤2_勾线', S2), ('范画步骤3_涂黑', S3), ('范画步骤4_上色', S4), ('范画步骤5_加背景', S5)]:
    IM(slot, 'chain', txt, PAPER + MARKER, prev=True, lock=True)
IM('范画成品_水粉', 'style',
   "Paint the exact same finished artwork, same locked composition, but in the chilled-watercolour technique "
   "described above: solid black ears, black eye patches, black legs and black shoulder band; face, belly and back "
   "left as clean white paper; the bamboo stalk in layered greens with two nodes and three slender leaves; pink cheeks; "
   "background with sage-green and olive bamboo leaves at the lower left, three grey stones, short grass tufts and "
   "four small warm yellow dots. Generous clean margin.",
   PAPER + WATER, refs=['01_封面主视觉'], lock=True)
IM('实物_竹子', 'real',
   "A fresh real bamboo stalk with several slender green leaves lying horizontally on a clean light wooden table, "
   "next to it a short cut piece showing two clear bamboo nodes, bright soft daylight from the left, soft shadow, "
   "top-down view, extremely clear detail of the bamboo surface.", PHOTO)
IM('实物_竹笋', 'real',
   "A freshly harvested bamboo shoot, still partly wrapped in its brown papery skin, sitting on a light wooden table "
   "next to a few loose bamboo leaves and a small knife, bright soft daylight, top-down view, crisp detail, "
   "clean simple background.", PHOTO)
IM('实物_材料工具', 'real',
   "A neat flat-lay of children's art materials on a light wooden table, arranged in a row: a stack of off-white "
   "sheets of rice paper, a black marker pen, three green marker pens in yellow-green, grass-green and dark olive, "
   "a watercolour paint set with a palette, a paintbrush in a cup, a pencil and an eraser. Top-down view, bright even "
   "daylight, everything clearly separated, product photography style.", PHOTO)
for slot, txt in [
  ('素材_坐姿', "A cute giant panda cub sitting upright on short green grass, holding a fresh bamboo stalk with both "
   "front paws and eating it, whole body fully visible, soft natural daylight, plain blurred green background."),
  ('素材_吃竹子', "A giant panda sitting among bamboo with its mouth full of fresh green bamboo leaves, chewing, the "
   "bamboo stalk crosses the frame diagonally, soft natural light, green bamboo background."),
  ('素材_面部特写', "Extreme close-up of a giant panda's face, huge round black eye patches, round black ears, black "
   "nose, white fur with fine detail, chewing a bamboo leaf, soft diffused daylight."),
  ('素材_爬树', "A giant panda cub climbing a thick tree branch high up, gripping the trunk with its claws, seen "
   "slightly from below, bamboo forest around, natural green tones, daylight."),
  ('素材_竹林', "A giant panda walking on the forest floor in a dense green bamboo forest, tall bamboo culms framing "
   "the picture on both sides, dappled sunlight through the leaves, wide horizontal composition."),
  ('素材_黑熊', "A black bear standing on four legs on a grassy clearing in a forest, glossy black fur, whole body "
   "visible in profile, natural daylight, plain green background."),
  ('素材_猫', "A black and white domestic cat sitting on a light wooden floor looking at the camera, clean simple "
   "background, whole body visible, soft daylight."),
]:
    IM(slot, 'photo', txt, PHOTO)

# ---------------- 页面 ----------------
P = []
def pg(**kw):
    P.append(kw)

pg(type='cover', title='《大熊猫吃竹子》', subtitle='《你好，动物主题》  马克笔 / 水粉 4-6岁',
   slogan=['一节课 · 一套课件 · 直接上课',
           '课件 / 教案 / 范画 / 素材 / 实物观察 全套齐备',
           '马克笔、水粉 两种画法可自由选择'],
   image='01_封面主视觉', uses=['01_封面主视觉'])

pg(type='intro', title='课 程 介 绍', chapter='课程介绍', image='范画成品',
   cards=[
     dict(head='课程目标', items=['1.观察实物与图片，了解大熊猫的外形特征，学会用圆形和椭圆概括形体。',
                                  '2.学习黑白色块的分布，感受“留白”的画面效果。',
                                  '3.认识绿色同类色，学习深浅变化的表现方法。']),
     dict(head='课程重难点', items=['1.大熊猫黑白毛色的分布位置（眼圈、耳朵、四肢、肩带）。',
                                    '2.用圆形＋椭圆组合概括形体。',
                                    '3.竹子与竹叶的绿色深浅层次。']),
     dict(head='教学安排', items=['1.课程导入    2.主题知识    3.实物观察',
                                  '4.绘画知识    5.参考素材    6.范画过程']),
   ], uses=['范画成品'])

pg(type='knowing', title='我们今天可以知道：', chapter='课程介绍',
   items=['1、大熊猫的外形特征和生活习性。', '2、大熊猫黑白毛色的分布规律。',
          '3、认识真实的竹子，观察竹节和竹叶。', '4、绿色同类色的深浅变化。',
          '5、一幅完整作品的创作步骤。'], uses=[])

pg(type='quiz', title='考 一 考', chapter='课程引导',
   question='这两只动物都是黑白配色的，大熊猫到底是“熊”还是“猫”呢？',
   images=['素材_黑熊', '素材_猫'],
   answer='揭晓：大熊猫属于熊科，它其实是“熊”！圆圆的脸像猫，所以名字里有个“猫”。',
   uses=['素材_黑熊', '素材_猫'])

for t, im, lines in [
  ('秘密一：大熊猫最爱吃竹子', '素材_吃竹子',
   ['一只成年大熊猫每天要吃掉 30～40 公斤竹子，', '差不多是小朋友体重的两倍！', '它们最喜欢吃竹笋和嫩嫩的竹叶。']),
  ('秘密二：为什么是黑白两色？', '素材_面部特写',
   ['黑色的大眼圈，就像小朋友戴上了太阳镜，', '可以帮它挡住雪地和阳光的刺眼反光，', '是一个天然的“护目镜”哦！']),
  ('秘密三：大熊猫的一天', '素材_爬树',
   ['吃竹子 12 小时，睡觉 10 小时，', '剩下的时间用来散步和玩耍。', '它们还是爬树高手，能在树上睡午觉。']),
]:
    pg(type='knowledge', title=t, chapter='课程引导', image=im, lines=lines, uses=[im])

pg(type='real_object', title='看一看：真实的竹子长什么样？', chapter='实物观察',
   image='实物_竹子', image2='实物_竹笋', img_h=3.05, img2_h=1.15,
   task_head='观察小任务',
   tasks=[dict(tag='看竹节', text='竹竿上有一圈一圈的横线，一节一节往上长。'),
          dict(tag='看竹叶', text='叶子又细又长，两头尖尖，长在一起一串一串。'),
          dict(tag='看竹笋', text='刚长出来的竹笋外面包着一层褐色的“衣服”。'),
          dict(tag='看颜色', text='竹子有多少种绿色？浅绿、中绿、深绿。'),
          dict(tag='摸一摸', text='竹竿滑滑的、硬硬的，竹叶软软的。')],
   uses=['实物_竹子', '实物_竹笋'])

pg(type='materials', title='摸一摸：我们要用到哪些材料？', chapter='实物观察',
   image='实物_材料工具',
   schemes=[dict(head='方案A 马克笔', items=['半生熟镜面宣纸', '黑色勾线笔',
                                            '绿色系马克笔（黄绿/草绿/深绿）', '铅笔、橡皮']),
            dict(head='方案B 水粉', items=['水粉纸或宣纸',
                                          '水粉颜料（黑、白、黄绿、草绿、深绿）',
                                          '水粉笔 大中小三支', '调色盘、抹布、洗笔筒'])],
   uses=['实物_材料工具'])

pg(type='observe_tags', title='小朋友们，大熊猫的外形有什么特点呢？', chapter='课程引导',
   image='素材_坐姿',
   tags=['圆圆的脸', '黑黑的眼圈', '半圆的耳朵', '胖胖的身体', '短短的四肢', '小小的尾巴'],
   uses=['素材_坐姿'])

pg(type='parts_diagram', title='大熊猫的身体是由哪些部分组成的呢？', chapter='课程引导',
   figure_note='圆形 + 椭圆 = 一只大熊猫',
   figure=dict(body=[1.65, 3.30, 3.30, 2.25], head=[3.55, 2.05, 1.90, 1.80],
               ear_left=[3.45, 1.85, 0.72, 0.72], ear_right=[4.85, 1.85, 0.72, 0.72],
               leg_front=[2.45, 4.75, 0.80, 0.62], leg_back=[3.45, 4.75, 0.80, 0.62],
               tail=[1.30, 3.85, 0.62, 0.52]),
   parts=[dict(name='头部', desc='圆圆的脸'), dict(name='耳朵', desc='两个半圆'),
          dict(name='身体', desc='一个大椭圆'), dict(name='四肢', desc='短短的'),
          dict(name='尾巴', desc='小小的圆球')], uses=[])

pg(type='poses', title='大熊猫都有哪些不同的姿势呢？', chapter='课程引导',
   items=[dict(image='素材_坐姿', label='坐着吃'), dict(image='素材_爬树', label='爬树'),
          dict(image='素材_竹林', label='散步')],
   uses=['素材_坐姿', '素材_爬树', '素材_竹林'])

pg(type='idea_list', title='大熊猫还会出现在哪里呢？', chapter='课程引导', image='素材_竹林',
   list_head='想一想，还可以怎么画？',
   items=['竹林里啃竹子', '树上睡午觉', '和小伙伴玩耍', '抱着竹笋不撒手', '在溪边喝水'],
   uses=['素材_竹林'])

pg(type='color_swatches', title='同类色小知识 —— 绿色家族', chapter='绘画知识',
   swatches=[dict(hex='CBE08A', name='黄绿', use='亮部'), dict(hex='A5C45C', name='草绿', use='中间色'),
             dict(hex='77A65A', name='橄榄绿', use='固有色'), dict(hex='4A6B2E', name='墨绿', use='暗部')],
   note_head='画竹子的时候，不要只用一种绿色：',
   note='先用草绿铺底色，再用深绿画暗部，最后用黄绿提亮 —— 竹子立刻就有了立体感。', uses=[])

pg(type='contrast_blank', title='黑白对比与画面留白', chapter='绘画知识',
   figure=dict(body=[1.35, 3.05, 4.15, 2.15], head=[2.65, 2.45, 1.55, 1.50],
               eyes=[[2.72, 2.72, 0.52, 0.52], [3.62, 2.72, 0.52, 0.52]],
               legs=[[1.22, 4.00, 0.62, 0.45], [5.00, 4.00, 0.62, 0.45]]),
   figure_note='黑色的地方要涂满、涂黑',
   tips=[dict(no='①', text='耳朵、眼圈、四肢、肩带 —— 这四处是黑色的。'),
         dict(no='②', text='脸、肚子、背部 —— 保持白色，不要涂。'),
         dict(no='③', text='留白也是画面的一部分，留得越多越透气。'),
         dict(no='④', text='黑色块面集中，画面才有力量感。')], uses=[])

for imgs in [['素材_坐姿', '素材_吃竹子'], ['素材_爬树', '素材_面部特写'], ['素材_竹林', '实物_竹子']]:
    pg(type='refs', chapter='参考素材', images=imgs, uses=imgs)

pg(type='tools_dual', title='工 具 介 绍（两种方案任选）', chapter='范画过程',
   schemes=[dict(head='方案A · 马克笔（推荐）', tools=[
             dict(no='1', name='半生熟镜面宣纸', desc='纸上有纹理，颜色更柔和'),
             dict(no='2', name='黑色勾线笔', desc='勾轮廓、涂黑色块面'),
             dict(no='3', name='绿色系马克笔', desc='黄绿、草绿、深绿各一支'),
             dict(no='4', name='铅笔和橡皮', desc='先起形，画得要轻')]),
            dict(head='方案B · 水粉', tools=[
             dict(no='1', name='水粉纸 / 宣纸', desc='比马克笔纸厚一点'),
             dict(no='2', name='水粉颜料', desc='黑、白、黄绿、草绿、深绿'),
             dict(no='3', name='水粉笔', desc='大中小三支，铺色+勾细节'),
             dict(no='4', name='调色盘和洗笔筒', desc='颜色不要调太稀')])], uses=[])

for title, im, main, tips in [
  ('步骤一：起 形', '范画步骤1_起形',
   '先用铅笔画出一个大圆（头）和一个大椭圆（身体），再画出手里的竹子，轻轻连起来。',
   ['把纸竖着放，熊猫画在正中间', '线条要轻，画错了可以擦掉', '竹子斜着穿过胸口，画面更有动感']),
  ('步骤二：勾 线', '范画步骤2_勾线',
   '用黑色勾线笔沿铅笔线描一遍，加上圆圆的耳朵、短短的四肢、笑眯眯的嘴巴。',
   ['耳朵是半圆形，长在头的两侧', '四肢画短一点，熊猫才可爱', '这时候画面还是白的，不要着急上色']),
  ('步骤三：涂 黑', '范画步骤3_涂黑',
   '把耳朵、眼圈、四肢和肩膀涂成黑色，脸和肚子保持白色 —— 这就是“留白”。',
   ['先勾边线再往里填，不容易涂出格', '眼圈里留一点小白点，眼睛更亮', '白色部分一定不要涂，留着才透气']),
  ('步骤四：上 色', '范画步骤4_上色',
   '用绿色系给竹子和竹叶上色，浅绿铺底、深绿画暗面，再给熊猫加上粉粉的腮红。',
   ['竹竿亮面用黄绿，暗面用深绿', '竹节画一道短横线', '三种绿叠在一起，竹子立刻立起来']),
  ('步骤五：加背景', '范画步骤5_加背景',
   '在周围空白的地方加上竹叶、小石头和草地，最后点上黄色小圆点，作品就完成啦！',
   ['背景要画得比主角小，不要抢主体', '左右各加一点，画面才平衡', '黄点少量点缀，画面更有神']),
]:
    pg(type='step', title=title, chapter='范画过程', image=im, text=main, tips=tips, uses=[im])

pg(type='final_dual', title='范 画 成 品', chapter='范画过程',
   hint='同构图 · 两种风格，老师可按班级情况自由选择',
   items=[dict(image='范画成品', label='马克笔版'), dict(image='范画成品_水粉', label='水粉版')],
   note='完整画面要有：明确的黑色块面 + 深浅变化的绿色 + 丰富的背景 + 适当的留白。别忘记写上作品名称、签上名字哦！',
   uses=['范画成品', '范画成品_水粉'])

pg(type='share_summary', chapter='分享表达', share_head='分 享 表 达', summary_head='课 后 总 结',
   share=['1、大熊猫身上哪些地方是黑色的？哪些地方是白色的？',
          '2、画竹子的时候，你用了哪几种绿色？'],
   summary=['1、本节课先观察真实的竹子和图片，了解大熊猫的外形特征，学习用圆形和椭圆概括动物形体，让孩子学会“先看再画”。',
            '2、通过黑白色块的分布与留白，让孩子理解“不涂满”也是一种画面语言，提高孩子的画面控制力。',
            '3、通过绿色同类色的分层上色，让孩子感受颜色的深浅变化，画面既饱满又有层次，童趣十足。'],
   uses=[])

# ---------------- 落地 ----------------
PROJ = dict(
    meta=dict(name='《大熊猫吃竹子》4-6岁课件', age='4-6岁',
              brand='【你的机构名】美育', brand_en='Art Education for Kids',
              theme=dict(primary='77A65A', dark='578B18', light='BED0B5',
                         accent='F9A605', text='354253', cream='FAF7F0', grey='595959')),
    lock=LOCK, common={}, images=images,
    chain=dict(order=CHAIN_ORDER, auto_ref_prev=True), pages=P)

os.makedirs(NEW, exist_ok=True)
for a, b in [(os.path.join(OLD, 'img'), os.path.join(NEW, 'img')),
             (os.path.join(OLD, 'img_sell'), os.path.join(NEW, 'img_sell'))]:
    if os.path.isdir(a) and not os.path.isdir(b):
        shutil.move(a, b); print('移动', b)
for f in os.listdir(OLD) if os.path.isdir(OLD) else []:
    if f.lower().endswith(('.png', '.jpg')) and '封面' in f:
        shutil.move(os.path.join(OLD, f), os.path.join(NEW, f)); print('移动', f)
os.makedirs(os.path.join(NEW, 'out'), exist_ok=True)
for f in os.listdir(OLD) if os.path.isdir(OLD) else []:
    if f.lower().endswith(('.png', '.pptx', '.pdf')):
        shutil.move(os.path.join(OLD, f), os.path.join(NEW, 'out', f))

with open(os.path.join(NEW, 'project.json'), 'w', encoding='utf-8') as f:
    json.dump(PROJ, f, ensure_ascii=False, indent=2)
print('project.json 已写入：%d 张图 / %d 页' % (len(images), len(P)))
if os.path.isdir(OLD) and not os.listdir(OLD):
    os.rmdir(OLD); print('旧目录已清空并删除')
