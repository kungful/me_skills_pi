/* ===== 建筑力学计算 ===== */
const M = {};
M.fmt = T.fmt;
M.len = T.len;

/* 公共存储：截面结果可以带到应力校核里去 */
M.store = {};

/* 把界面里存的值洗干净再交给 calc。
   坑：自选型（sel）字段是字符串，绝不能 parseFloat —— 否则变成 0，
   所有 if/else 分支都会掉进最后一个，结果静默算错。 */
M.coerce = function (c, raw) {
  const o = {};
  c.inputs.forEach(f => {
    if (f.sel) { o[f.k] = raw[f.k]; return; }
    o[f.k] = (typeof raw[f.k] === 'number') ? raw[f.k] : (parseFloat(raw[f.k]) || 0);
  });
  return o;
};

/* 每个计算器：{ id, title, hint, inputs:[{k,label,unit,def,show,opts,sel}], calc(v) }
   calc 返回 { head:[[标题,值,副标]], rows:[[名,值]], steps:[[名,文本]], verdict:{cls,html} } */

M.calcs = [

  /* ---------------- 坡度 ---------------- */
  {
    id: 'slope', title: '坡度 · 角度 · 斜长',
    hint: '坡度就是「每前进 1 米升高多少」。它其实就是 tanθ —— 对边（竖直高）比邻边（水平距离）。',
    inputs: [
      { k: 'mode', label: '已知条件', sel: true, def: 'LH',
        opts: [{ v: 'LH', t: '水平 + 竖直' }, { v: 'AL', t: '角度 + 水平' }, { v: 'AS', t: '角度 + 斜长' }] },
      { k: 'L', label: '水平距离 L', unit: 'm', def: 4, show: ['LH', 'AL'] },
      { k: 'H', label: '竖直高 H', unit: 'm', def: 0.2, show: ['LH'] },
      { k: 'A', label: '坡角 θ', unit: '°', def: 30, show: ['AL', 'AS'] },
      { k: 'S', label: '斜长 S', unit: 'm', def: 5, show: ['AS'] },
    ],
    calc(v) {
      let L, H, S;
      if (v.mode === 'LH') { L = v.L; H = v.H; }
      else if (v.mode === 'AL') { L = v.L; H = L * T.tan(v.A); }
      else { L = v.S * T.cos(v.A); H = v.S * T.sin(v.A); }
      if (!(L > 0)) return { err: '水平距离要大于 0' };
      S = Math.hypot(L, H);
      const th = T.deg(Math.atan2(H, L));
      const i = H / L;
      const pct = i * 100;
      const steps = [];
      if (v.mode !== 'AL') steps.push(['反算坡角', `θ = arctan(H / L) = arctan(${M.len(H)} / ${M.len(L)}) = <code>${M.fmt(th, 3)}°</code>`]);
      else steps.push(['求竖直高', `H = L · tanθ = ${M.len(L)} × ${M.fmt(T.tan(v.A), 4)} = <code>${M.len(H)}</code> m`]);
      steps.push(['坡度比', `i = H / L = ${M.len(H)} / ${M.len(L)} = <code>${M.fmt(i, 4)}</code>`]);
      steps.push(['化成 1:x', `1 : ${M.fmt(1 / i, 2)} —— 每走 ${M.fmt(1 / i, 2)} m 水平，升高 1 m`]);
      steps.push(['百分比', `坡度 = i × 100% = <code>${M.fmt(pct, 3)}%</code>`]);
      steps.push(['斜长', `S = √(L² + H²) = √(${M.len(L)}² + ${M.len(H)}²) = <code>${M.len(S)}</code> m`]);
      steps.push(['下料用', `斜杆长度 = 水平距离 ÷ cosθ = ${M.len(L)} ÷ ${M.fmt(T.cos(th), 4)} = ${M.len(S)} m`]);

      let vd = null;
      if (pct >= 1 && pct <= 1.5) vd = { cls: 'ok', html: '≈ 卫生间 / 阳台地面找坡常用 <b>1% ~ 1.5%</b>' };
      else if (pct >= 2 && pct <= 3) vd = { cls: 'ok', html: '≈ 平屋面排水坡度 <b>2% ~ 3%</b>' };
      else if (pct > 3 && pct <= 5) vd = { cls: 'ok', html: '≈ 散水坡度 <b>3% ~ 5%</b>' };
      else if (pct > 5 && pct <= 8.33) vd = { cls: 'warn', html: '无障碍坡道上限是 <b>1:12 = 8.33%</b>，超过就不符合规范' };
      else if (pct > 8.33 && pct <= 15) vd = { cls: 'warn', html: '已超过无障碍坡道上限（8.33%），自行车坡道限 15%' };
      else if (pct > 15) vd = { cls: 'warn', html: '这已经是<b>楼梯或屋面</b>级别的坡度了（' + M.fmt(th, 1) + '°）' };

      return {
        head: [['坡角 θ', M.fmt(th, 3) + '°'], ['坡度', M.fmt(pct, 3) + '%'], ['斜长 S', M.len(S) + ' m']],
        rows: [['坡度比 i', M.fmt(i, 4)], ['化成', '1 : ' + M.fmt(1 / i, 2)],
               ['每米水平升高', M.fmt(H / L * 1000, 2) + ' mm'],
               ['sinθ（竖直占比）', M.fmt(T.sin(th), 4)], ['cosθ（水平占比）', M.fmt(T.cos(th), 4)]],
        steps, verdict: vd,
      };
    },
  },

  /* ---------------- 荷载 ---------------- */
  {
    id: 'load', title: '板 / 梁 荷载换算',
    hint: '面荷载 (kN/m²) × 受荷宽度 = 线荷载 (kN/m)，线荷载才是梁上真正受的力。',
    inputs: [
      { k: 'g', label: '材料容重 γ', unit: 'kN/m³', def: 25 },
      { k: 't', label: '板厚 t', unit: 'mm', def: 100 },
      { k: 'add', label: '附加恒载（面层等）', unit: 'kN/m²', def: 1.0 },
      { k: 'live', label: '活荷载', unit: 'kN/m²', def: 2.0 },
      { k: 'B', label: '受荷宽度 B', unit: 'm', def: 3.0 },
    ],
    calc(v) {
      const self = v.g * v.t / 1000;               // kN/m²
      const gk = self + v.add;                      // 恒载标准值 kN/m²
      const qkArea = gk + v.live;                   // 总标准值 kN/m²
      const qk = qkArea * v.B;                      // 线荷载标准值 kN/m
      const qd = (1.3 * gk + 1.5 * v.live) * v.B;   // 设计值 kN/m
      return {
        head: [['板自重', M.fmt(self, 3) + ' kN/m²'], ['线荷载标准', M.fmt(qk, 2) + ' kN/m'], ['设计线荷载', M.fmt(qd, 2) + ' kN/m']],
        rows: [['恒载标准值 gk', M.fmt(gk, 3) + ' kN/m²'],
               ['活载标准值', M.fmt(v.live, 2) + ' kN/m²'],
               ['受荷宽度 B', M.len(v.B) + ' m'],
               ['线荷载标准值 qk', M.fmt(qk, 2) + ' kN/m'],
               ['设计线荷载 qd', M.fmt(qd, 2) + ' kN/m'],
               ['折算 kgf/m（参考）', M.fmt(qd * 102, 0) + ' kgf/m']],
        steps: [
          ['板自重', `g = γ × t / 1000 = ${M.len(v.g)} × ${M.len(v.t)} / 1000 = <code>${M.fmt(self, 3)}</code> kN/m²`],
          ['恒载标准值', `gk = 自重 + 附加 = ${M.fmt(self, 3)} + ${M.len(v.add)} = <code>${M.fmt(gk, 3)}</code> kN/m²`],
          ['线荷载标准值', `qk = (gk + 活载) × B = (${M.fmt(gk, 3)} + ${M.len(v.live)}) × ${M.len(v.B)} = <code>${M.fmt(qk, 2)}</code> kN/m`],
          ['设计值（1.3 恒 + 1.5 活）', `qd = (1.3 × ${M.fmt(gk, 3)} + 1.5 × ${M.len(v.live)}) × ${M.len(v.B)} = <code>${M.fmt(qd, 2)}</code> kN/m`],
          ['用法', `把 qd 填进「梁的内力与挠度」的均布荷载，就能算弯矩和挠度`],
        ],
        verdict: { cls: 'warn', html: '常用活荷载参考：住宅楼面 2.0、办公室 2.0、走廊楼梯 2.5~3.5、阳台 2.5、上人屋面 2.0、不上人屋面 0.5（kN/m²）' },
      };
    },
  },

  /* ---------------- 梁 ---------------- */
  {
    id: 'beam', title: '梁的内力与挠度',
    hint: '均布荷载和跨中集中荷载可以叠加，两个都填就是同时作用。',
    inputs: [
      { k: 'type', label: '支承形式', sel: true, def: 'ss',
        opts: [{ v: 'ss', t: '简支梁（两端支承）' }, { v: 'cant', t: '悬臂梁（一端固定）' }] },
      { k: 'L', label: '计算跨度 L', unit: 'm', def: 6 },
      { k: 'q', label: '均布荷载 q', unit: 'kN/m', def: 10 },
      { k: 'P', label: '集中荷载 P', unit: 'kN', def: 0 },
      { k: 'E', label: '弹性模量 E', unit: 'GPa', def: 206 },
      { k: 'I', label: '惯性矩 I', unit: 'cm⁴', def: 2000 },
      { k: 'lim', label: '挠度限值 1/', unit: '', def: 250 },
    ],
    calc(v) {
      const L = v.L, q = v.q, P = v.P;
      if (!(L > 0)) return { err: '跨度要大于 0' };
      const qn = q;                        // kN/m 数值上等于 N/mm
      const LN = L * 1000, EN = v.E * 1000, IN = v.I * 1e4;
      let Mmax, Vmax, f1 = 0, f2 = 0, name;
      if (v.type === 'ss') {
        Mmax = q * L * L / 8 + P * L / 4;
        Vmax = q * L / 2 + P / 2;
        f1 = 5 * qn * Math.pow(LN, 4) / (384 * EN * IN);
        f2 = (P * 1000) * Math.pow(LN, 3) / (48 * EN * IN);
        name = '简支梁';
      } else {
        Mmax = q * L * L / 2 + P * L;
        Vmax = q * L + P;
        f1 = qn * Math.pow(LN, 4) / (8 * EN * IN);
        f2 = (P * 1000) * Math.pow(LN, 3) / (3 * EN * IN);
        name = '悬臂梁';
      }
      const f = f1 + f2;
      const fmax = LN / Math.max(v.lim, 1);
      const ratio = f / fmax;
      let vd;
      if (ratio <= 1) vd = { cls: 'ok', html: `挠度 <b>${M.fmt(f, 2)} mm</b> ≤ 限值 ${M.fmt(fmax, 2)} mm（L/${M.fmt(v.lim, 0)}）→ <b>满足</b>` };
      else if (ratio <= 1.1) vd = { cls: 'warn', html: `挠度 ${M.fmt(f, 2)} mm 略超限值 ${M.fmt(fmax, 2)} mm（${M.fmt(ratio * 100, 0)}%）→ 接近临界` };
      else vd = { cls: 'bad', html: `挠度 <b>${M.fmt(f, 2)} mm</b> > 限值 ${M.fmt(fmax, 2)} mm（${M.fmt(ratio * 100, 0)}%）→ <b>挠度超限</b>，需加大截面或减小跨度` };

      const st = [];
      if (v.type === 'ss') {
        st.push(['支座反力', `R = qL/2 + P/2 = ${M.len(q)}×${M.len(L)}/2 + ${M.len(P)}/2 = <code>${M.fmt(Vmax, 2)}</code> kN（每端）`]);
        st.push(['最大弯矩', `M = qL²/8 + PL/4 = ${M.len(q)}×${M.len(L)}²/8 + ${M.len(P)}×${M.len(L)}/4 = <code>${M.fmt(Mmax, 2)}</code> kN·m`]);
        st.push(['位置', `跨中（L/2 = ${M.fmt(L / 2, 2)} m 处）`]);
        st.push(['挠度（均布）', `f₁ = 5qL⁴/(384EI) = 5×${M.len(q)}×${M.len(L)}⁴/(384×${M.len(v.E)}×${M.len(v.I)}) = <code>${M.fmt(f1, 2)}</code> mm`]);
        if (P > 0) st.push(['挠度（集中）', `f₂ = PL³/(48EI) = <code>${M.fmt(f2, 2)}</code> mm`]);
      } else {
        st.push(['支座反力', `R = qL + P = ${M.len(q)}×${M.len(L)} + ${M.len(P)} = <code>${M.fmt(Vmax, 2)}</code> kN（固定端）`]);
        st.push(['最大弯矩', `M = qL²/2 + PL = <code>${M.fmt(Mmax, 2)}</code> kN·m`]);
        st.push(['位置', `固定端根部（最危险）`]);
        st.push(['挠度（均布）', `f₁ = qL⁴/(8EI) = <code>${M.fmt(f1, 2)}</code> mm`]);
        if (P > 0) st.push(['挠度（集中）', `f₂ = PL³/(3EI) = <code>${M.fmt(f2, 2)}</code> mm`]);
      }
      st.push(['合计挠度', `f = f₁ + f₂ = <code>${M.fmt(f, 2)}</code> mm，限值 L/${M.fmt(v.lim, 0)} = ${M.fmt(fmax, 2)} mm`]);
      st.push(['拿去配筋/选型', `把 M = ${M.fmt(Mmax, 2)} kN·m 填进「弯曲应力校核」，配上截面 W 就能算出应力`]);

      M.store.beam = { M: Mmax, V: Vmax };
      return {
        head: [['最大弯矩 M', M.fmt(Mmax, 2) + '', 'kN·m'], ['最大剪力 V', M.fmt(Vmax, 2) + '', 'kN'], ['最大挠度 f', M.fmt(f, 2) + '', 'mm']],
        rows: [['支承形式', name],
               ['翼缘/腹板惯性矩 I', M.len(v.I) + ' cm⁴'],
               ['弹性模量 E', M.len(v.E) + ' GPa'],
               ['挠度限值', 'L/' + M.fmt(v.lim, 0) + ' = ' + M.fmt(fmax, 2) + ' mm'],
               ['挠度利用率', M.fmt(ratio * 100, 1) + ' %']],
        steps: st, verdict: vd,
      };
    },
  },

  /* ---------------- 截面特性 ---------------- */
  {
    id: 'section', title: '截面特性 A / I / W',
    hint: 'I 是惯性矩（抗弯刚度），W 是抵抗矩（抗弯能力）。算出 W 才能算应力。',
    inputs: [
      { k: 'type', label: '截面形状', sel: true, def: 'rect',
        opts: [{ v: 'rect', t: '矩形 b×h' }, { v: 'square', t: '正方形 a' }, { v: 'circle', t: '圆 d' },
               { v: 'pipe', t: '圆管 D,t' }, { v: 'tube', t: '方管 b×h,t' }, { v: 'ibeam', t: 'H 型钢' }] },
      { k: 'b', label: '宽 b', unit: 'mm', def: 200, show: ['rect', 'tube', 'ibeam'] },
      { k: 'h', label: '高 h', unit: 'mm', def: 500, show: ['rect', 'tube', 'ibeam'] },
      { k: 'a', label: '边长 a', unit: 'mm', def: 200, show: ['square'] },
      { k: 'd', label: '直径 d', unit: 'mm', def: 200, show: ['circle'] },
      { k: 'D', label: '外径 D', unit: 'mm', def: 200, show: ['pipe'] },
      { k: 't', label: '壁厚 t', unit: 'mm', def: 8, show: ['pipe', 'tube'] },
      { k: 'tw', label: '腹板厚 tw', unit: 'mm', def: 8, show: ['ibeam'] },
      { k: 'tf', label: '翼缘厚 tf', unit: 'mm', def: 12, show: ['ibeam'] },
    ],
    calc(v) {
      let A = 0, I = 0, H = 0, nm = '', hk = 'h', hlab = '截面高度 h';
      if (v.type === 'rect') { const b = v.b, h = v.h; A = b * h; I = b * h * h * h / 12; H = h; nm = `矩形 ${b}×${h}`; }
      else if (v.type === 'square') { const a = v.a; A = a * a; I = a * a * a * a / 12; H = a; hk = 'a'; hlab = '截面边长 a'; nm = `正方形 ${a}`; }
      else if (v.type === 'circle') { const d = v.d; A = Math.PI * d * d / 4; I = Math.PI * Math.pow(d, 4) / 64; H = d; hk = 'd'; hlab = '截面直径 d'; nm = `圆 d=${d}`; }
      else if (v.type === 'pipe') { const D = v.D, t = v.t, d = D - 2 * t; A = Math.PI * (D * D - d * d) / 4; I = Math.PI * (Math.pow(D, 4) - Math.pow(d, 4)) / 64; H = D; hk = 'D'; hlab = '截面外径 D'; nm = `圆管 D=${D} t=${t}`; }
      else if (v.type === 'tube') { const b = v.b, h = v.h, t = v.t, bi = b - 2 * t, hi = h - 2 * t; A = b * h - bi * hi; I = (b * Math.pow(h, 3) - bi * Math.pow(hi, 3)) / 12; H = h; nm = `方管 ${b}×${h}×${t}`; }
      else { const b = v.b, h = v.h, tw = v.tw, tf = v.tf; A = 2 * b * tf + (h - 2 * tf) * tw; I = (b * Math.pow(h, 3) - (b - tw) * Math.pow(h - 2 * tf, 3)) / 12; H = h; nm = `H 型钢 ${b}×${h}×${tw}×${tf}`; }
      if (!(A > 0) || !(I > 0)) return { err: '尺寸不合法' };

      const A_cm2 = A / 100, I_cm4 = I / 1e4, W_cm3 = (I / (H / 2)) / 1000, i_cm = Math.sqrt(I / A) / 10;
      M.store.section = { W: W_cm3, I: I_cm4, A: A_cm2, name: nm };
      let Wf = '', If = '';
      if (v.type === 'rect') { Wf = 'b·h²/6'; If = 'b·h³/12'; }
      else if (v.type === 'square') { Wf = 'a³/6'; If = 'a⁴/12'; }
      else if (v.type === 'circle') { Wf = 'π·d³/32'; If = 'π·d⁴/64'; }
      else if (v.type === 'pipe') { Wf = 'I/(D/2)'; If = 'π(D⁴−d⁴)/64'; }
      else if (v.type === 'tube') { Wf = 'I/(h/2)'; If = '[b·h³−(b−2t)(h−2t)³]/12'; }
      else { Wf = 'I/(h/2)'; If = '[b·h³−(b−tw)(h−2tf)³]/12'; }

      return {
        head: [['截面面积 A', M.fmt(A_cm2, 2) + '', 'cm²'], ['惯性矩 I', M.fmt(I_cm4, 1) + '', 'cm⁴'], ['抵抗矩 W', M.fmt(W_cm3, 1) + '', 'cm³']],
        rows: [['截面', nm],
               [hlab, M.len(H) + ' mm'],
               ['回转半径 i', M.fmt(i_cm, 3) + ' cm'],
               ['I 公式', If], ['W 公式', Wf]],
        steps: [
          ['面积', `A = ${M.fmt(A, 0)} mm² = <code>${M.fmt(A_cm2, 2)}</code> cm²`],
          ['惯性矩', `I = ${If} = <code>${M.fmt(I_cm4, 1)}</code> cm⁴`],
          ['抵抗矩', `W = I / (${hk}/2) = <code>${M.fmt(W_cm3, 1)}</code> cm³`],
          ['怎么用', `应力 σ = M / W。比如 M = 100 kN·m 时，σ = 100×10⁶ / (${M.fmt(W_cm3, 1)}×10³) = <code>${M.fmt(1e8 / W_cm3, 1)}</code> MPa`],
          ['提示', `同样的截面积，把材料放得离中性轴越远（h 越大），I 和 W 越大 —— 这就是工字钢做成「工」字的原因`],
        ],
        verdict: { cls: 'warn', html: `结果已存下，去「弯曲应力校核」点<b>带入截面</b>即可直接引用 W = ${M.fmt(W_cm3, 1)} cm³` },
      };
    },
  },

  /* ---------------- 应力校核 ---------------- */
  {
    id: 'stress', title: '弯曲应力校核 σ = M / W',
    hint: '算出应力，跟材料允许应力比一比，就知道能不能用。',
    inputs: [
      { k: 'Mn', label: '弯矩 M', unit: 'kN·m', def: 100 },
      { k: 'W', label: '抵抗矩 W', unit: 'cm³', def: 500 },
      { k: 'f', label: '材料允许应力 f', unit: 'MPa', def: 215 },
      { k: 'V', label: '剪力 V（可选）', unit: 'kN', def: 0 },
      { k: 'A', label: '截面面积 A（可选）', unit: 'cm²', def: 0 },
    ],
    calc(v) {
      if (!(v.W > 0)) return { err: '抵抗矩 W 要大于 0' };
      const sig = v.Mn * 1e6 / (v.W * 1e3);      // MPa
      const util = sig / v.f;
      let vd;
      if (util <= 0.9) vd = { cls: 'ok', html: `σ = <b>${M.fmt(sig, 1)} MPa</b> ≤ f = ${M.fmt(v.f, 0)} MPa（利用率 ${M.fmt(util * 100, 1)}%）→ <b>满足</b>，还有富余` };
      else if (util <= 1.0) vd = { cls: 'warn', html: `σ = ${M.fmt(sig, 1)} MPa，利用率 ${M.fmt(util * 100, 1)}% → <b>刚好满足</b>，几乎没有富余，建议留 10% 余量` };
      else vd = { cls: 'bad', html: `σ = <b>${M.fmt(sig, 1)} MPa</b> > f = ${M.fmt(v.f, 0)} MPa（${M.fmt(util * 100, 1)}%）→ <b>不满足</b>，需加大截面（W 至少 ${M.fmt(v.Mn * 1e6 / (v.f * 1e3), 1)} cm³）` };

      const st = [
        ['单位换算', `M = ${M.len(v.Mn)} kN·m = ${M.len(v.Mn)} × 10⁶ N·mm；W = ${M.len(v.W)} cm³ = ${M.len(v.W)} × 10³ mm³`],
        ['弯曲应力', `σ = M / W = ${M.len(v.Mn)}×10⁶ / (${M.len(v.W)}×10³) = <code>${M.fmt(sig, 2)}</code> MPa`],
        ['利用率', `${M.fmt(sig, 2)} / ${M.fmt(v.f, 0)} = <code>${M.fmt(util * 100, 1)}%</code>`],
      ];
      const rows = [['弯曲应力 σ', M.fmt(sig, 2) + ' MPa'], ['允许应力 f', M.fmt(v.f, 0) + ' MPa'],
                    ['利用率', M.fmt(util * 100, 1) + ' %'], ['最小需要 W', M.fmt(v.Mn * 1e6 / (v.f * 1e3), 1) + ' cm³']];
      if (v.V > 0 && v.A > 0) {
        const tau = 1.5 * v.V * 1000 / (v.A * 100);   // MPa，矩形截面最大剪应力
        rows.push(['最大剪应力 τ', M.fmt(tau, 2) + ' MPa']);
        rows.push(['剪切利用率', M.fmt(tau / (0.58 * v.f) * 100, 1) + ' % vs 0.58f=' + M.fmt(0.58 * v.f, 0)]);
        st.push(['剪应力', `τ = 1.5V/A = 1.5×${M.len(v.V)}×10³ / (${M.len(v.A)}×10²) = <code>${M.fmt(tau, 2)}</code> MPa（矩形截面近似）`]);
        st.push(['剪切判定', `允许剪应力约 0.58f = ${M.fmt(0.58 * v.f, 0)} MPa，${tau <= 0.58 * v.f ? '满足' : '不满足'}`]);
      }
      return {
        head: [['弯曲应力 σ', M.fmt(sig, 1) + '', 'MPa'], ['利用率', M.fmt(util * 100, 1) + '', '%'], ['允许应力 f', M.fmt(v.f, 0) + '', 'MPa']],
        rows, steps: st, verdict: vd,
      };
    },
    actions: [
      {
        label: '带入截面 W', done: '已带入截面 W',
        run(v) {
          if (!M.store.section) return '请先到「截面特性」算一次';
          v.W = Math.round(M.store.section.W * 10) / 10;
          v.A = Math.round(M.store.section.A * 10) / 10;
          if (M.store.beam) v.Mn = Math.round(M.store.beam.M * 100) / 100;
          return null;
        },
      },
      {
        label: '带入梁的 M', done: '已带入梁的弯矩',
        run(v) {
          if (!M.store.beam) return '请先到「梁的内力与挠度」算一次';
          v.Mn = Math.round(M.store.beam.M * 100) / 100;
          v.V = Math.round(M.store.beam.V * 100) / 100;
          return null;
        },
      },
      { label: 'Q235 钢 215', run(v) { v.f = 215; return null; }, done: '已切到 Q235' },
      { label: 'C30 混凝土 14.3', run(v) { v.f = 14.3; return null; }, done: '已切到 C30' },
    ],
  },

  /* ---------------- 斜杆内力 ---------------- */
  {
    id: 'strut', title: '斜杆 / 支撑 内力',
    hint: '竖向力靠斜杆扛的时候：θ 越小，斜杆越吃力。这就是斜撑要「立起来」的原因。',
    inputs: [
      { k: 'type', label: '形式', sel: true, def: 'single',
        opts: [{ v: 'single', t: '单根斜撑' }, { v: 'pair', t: '人字形（两根）' }] },
      { k: 'V', label: '竖向力 V', unit: 'kN', def: 20 },
      { k: 'A', label: '与水平夹角 θ', unit: '°', def: 45 },
    ],
    calc(v) {
      const th = v.A;
      if (!(th > 0 && th < 90)) return { err: '夹角要在 0° ~ 90° 之间（不含端点）' };
      const V = v.V;
      const n = v.type === 'pair' ? 2 : 1;
      const per = V / n;
      const N = per / T.sin(th);
      const Hh = per / T.tan(th);
      const lenPer = 1 / T.sin(th);   // 每 1 m 高对应的斜杆长度
      const rows = [
        ['每根承担竖向力', M.fmt(per, 2) + ' kN'],
        ['斜杆轴力 N', M.fmt(N, 2) + ' kN'],
        ['水平分力 H', M.fmt(Hh, 2) + ' kN'],
        ['每 1 m 高的斜杆长', M.fmt(lenPer, 3) + ' m'],
        ['斜杆用钢量指数', M.fmt(lenPer * N, 2)],
      ];
      let vd;
      if (th < 30) vd = { cls: 'bad', html: `夹角只有 ${M.fmt(th, 1)}°，斜杆轴力放大到竖向力的 <b>${M.fmt(N / per, 2)} 倍</b>，非常不经济，一般不宜小于 30°` };
      else if (th >= 30 && th < 45) vd = { cls: 'warn', html: `夹角 ${M.fmt(th, 1)}°，轴力是竖向力的 ${M.fmt(N / per, 2)} 倍。可以用，但 45° 左右更省料` };
      else if (th <= 60) vd = { cls: 'ok', html: `夹角 ${M.fmt(th, 1)}°，放大倍数 ${M.fmt(N / per, 2)}，受力与用钢量都比较均衡 —— <b>45° 附近最经济</b>` };
      else vd = { cls: 'ok', html: `夹角 ${M.fmt(th, 1)}°，轴力放大倍数 ${M.fmt(N / per, 2)} 很小，但斜杆变长、水平分力也小，注意支承处的水平推力要有人接住` };

      return {
        head: [['斜杆轴力 N', M.fmt(N, 2) + '', 'kN'], ['水平分力 H', M.fmt(Hh, 2) + '', 'kN'], ['放大倍数', M.fmt(N / per, 2) + '', '倍']],
        rows,
        steps: [
          ['力的三角形', `竖向力 V 是「对边」，斜杆轴力 N 是「斜边」→ N = V / sinθ`],
          ['代入', `N = ${M.len(per)} / sin ${M.fmt(th, 1)}° = ${M.len(per)} / ${M.fmt(T.sin(th), 4)} = <code>${M.fmt(N, 2)}</code> kN`],
          ['水平分力', `H = V / tanθ = ${M.len(per)} / ${M.fmt(T.tan(th), 4)} = <code>${M.fmt(Hh, 2)}</code> kN`],
          ['下料长度', `每 1 m 高需要 ${M.fmt(lenPer, 3)} m 斜杆（= 1/sinθ）；如果高度是 ${M.fmt(3, 1)} m，就用 ${M.fmt(3 * lenPer, 3)} m`],
          ['选型建议', `按 N = ${M.fmt(N, 2)} kN 查型钢/钢管承载力，再考虑压杆稳定（长细比）折减`],
        ],
        verdict: vd,
      };
    },
  },

  /* ---------------- 斜面受力 ---------------- */
  {
    id: 'incline', title: '斜面受力分解（滑不滑）',
    hint: '物体放在斜面上：重力自动分成「往下滑」和「压住斜面」两个力 —— 用的是 sin 和 cos。',
    inputs: [
      { k: 'W', label: '物重 W', unit: 'kN', def: 10 },
      { k: 'A', label: '斜面倾角 θ', unit: '°', def: 25 },
      { k: 'mu', label: '摩擦系数 μ', unit: '', def: 0.3 },
    ],
    calc(v) {
      const th = v.A;
      if (!(th >= 0 && th < 90)) return { err: '倾角要在 0° ~ 90° 之间' };
      const dn = v.W * T.sin(th), nn = v.W * T.cos(th), fr = v.mu * nn;
      const net = dn - fr;
      const slip = net > 1e-9;
      const locked = T.tan(th) <= v.mu;
      const vd = locked
        ? { cls: 'ok', html: `tanθ = ${M.fmt(T.tan(th), 3)} ≤ μ = ${M.len(v.mu)} → <b>自锁</b>，物体不会自己滑下去（静摩擦足够）` }
        : { cls: 'bad', html: `tanθ = ${M.fmt(T.tan(th), 3)} > μ = ${M.len(v.mu)} → <b>会下滑</b>，净下滑力 ${M.fmt(net, 2)} kN。要么加大摩擦（μ 需 ≥ ${M.fmt(T.tan(th), 3)}），要么加挡/加锚` };
      return {
        head: [['下滑分力', M.fmt(dn, 2) + '', 'kN'], ['正压力', M.fmt(nn, 2) + '', 'kN'], ['摩擦力', M.fmt(fr, 2) + '', 'kN']],
        rows: [['临界摩擦系数 μ_min', M.fmt(T.tan(th), 4)],
               ['净下滑力', M.fmt(net, 2) + ' kN'],
               ['下滑占比 sinθ', M.fmt(T.sin(th), 4)],
               ['压面占比 cosθ', M.fmt(T.cos(th), 4)]],
        steps: [
          ['下滑分力（沿斜面）', `W∥ = W · sinθ = ${M.len(v.W)} × ${M.fmt(T.sin(th), 4)} = <code>${M.fmt(dn, 2)}</code> kN`],
          ['正压力（垂直斜面）', `W⊥ = W · cosθ = ${M.len(v.W)} × ${M.fmt(T.cos(th), 4)} = <code>${M.fmt(nn, 2)}</code> kN`],
          ['摩擦力', `f = μ · W⊥ = ${M.len(v.mu)} × ${M.fmt(nn, 2)} = <code>${M.fmt(fr, 2)}</code> kN`],
          ['净下滑力', `W∥ − f = ${M.fmt(dn, 2)} − ${M.fmt(fr, 2)} = <code>${M.fmt(net, 2)}</code> kN（${slip ? '会滑' : '不会滑'}）`],
          ['自锁条件', `tanθ ≤ μ。现在 tan ${M.fmt(th, 1)}° = ${M.fmt(T.tan(th), 4)}，μ = ${M.len(v.mu)} → ${locked ? '自锁成立' : '不成立'}`],
        ],
        verdict: vd,
      };
    },
  },
];
