/* ===== 三角函数引擎：求解 + 可视化 ===== */
const T = {};

T.rad = d => d * Math.PI / 180;
T.deg = r => r * 180 / Math.PI;
T.sin = d => Math.sin(T.rad(d));
T.cos = d => Math.cos(T.rad(d));
T.tan = d => Math.tan(T.rad(d));

/* 数字格式化：去掉多余的 0 */
T.fmt = function (x, d) {
  d = d == null ? 3 : d;
  if (x == null || !isFinite(x)) return '—';
  if (Math.abs(x) < 1e-12) return '0';
  let s = x.toFixed(d);
  if (s.indexOf('.') >= 0) s = s.replace(/0+$/, '').replace(/\.$/, '');
  return s;
};
/* 长度：按大小自动选小数位，读起来舒服 */
T.len = function (x) {
  if (x == null || !isFinite(x)) return '—';
  const ax = Math.abs(x);
  if (ax >= 1000) return T.fmt(x, 1);
  if (ax >= 100) return T.fmt(x, 2);
  if (ax >= 1) return T.fmt(x, 3);
  return T.fmt(x, 4);
};

/* ---- 六个求解模式 ---- */
T.modes = [
  {
    id: 'ab', label: '对边 + 邻边', hint: '两条直角边 → 求斜边和两个锐角',
    fields: [{ k: 'a', label: '对边 a', ph: '例 3' }, { k: 'b', label: '邻边 b', ph: '例 4' }],
    solve(v) {
      const a = v.a, b = v.b, c = Math.hypot(a, b), A = T.deg(Math.atan2(a, b));
      return {
        a, b, c, A, B: 90 - A,
        steps: [
          ['勾股定理', `c = √(a² + b²) = √(${T.len(a)}² + ${T.len(b)}²) = <code>${T.len(c)}</code>`],
          ['正切 = 对边 ÷ 邻边', `tan A = a / b = ${T.len(a)} / ${T.len(b)} = <code>${T.fmt(a / b, 4)}</code>`],
          ['反查角度', `A = arctan(${T.fmt(a / b, 4)}) = <code>${T.fmt(A, 2)}°</code>`],
          ['另一个锐角', `B = 90° − A = <code>${T.fmt(90 - A, 2)}°</code>`],
          ['验算', `sin A = a / c = ${T.len(a)} / ${T.len(c)} = ${T.fmt(a / c, 4)}，与 sin ${T.fmt(A, 2)}° 一致 ✓`],
        ],
      };
    },
  },
  {
    id: 'ac', label: '对边 + 斜边', hint: '一条直角边和斜边 → 用 sin 求角',
    fields: [{ k: 'a', label: '对边 a', ph: '例 3' }, { k: 'c', label: '斜边 c', ph: '例 5' }],
    solve(v) {
      const a = v.a, c = v.c;
      if (c <= a) return { err: '斜边必须大于直角边（斜边是最长边）' };
      const b = Math.sqrt(c * c - a * a), A = T.deg(Math.asin(a / c));
      return {
        a, b, c, A, B: 90 - A,
        steps: [
          ['勾股定理反用', `b = √(c² − a²) = √(${T.len(c)}² − ${T.len(a)}²) = <code>${T.len(b)}</code>`],
          ['正弦 = 对边 ÷ 斜边', `sin A = a / c = ${T.len(a)} / ${T.len(c)} = <code>${T.fmt(a / c, 4)}</code>`],
          ['反查角度', `A = arcsin(${T.fmt(a / c, 4)}) = <code>${T.fmt(A, 2)}°</code>`],
          ['另一角', `B = 90° − A = <code>${T.fmt(90 - A, 2)}°</code>`],
           ['验算', `cos A = b / c = ${T.len(b)} / ${T.len(c)} = ${T.fmt(b / c, 4)} ✓`],
        ],
      };
    },
  },
  {
    id: 'bc', label: '邻边 + 斜边', hint: '一条直角边和斜边 → 用 cos 求角',
    fields: [{ k: 'b', label: '邻边 b', ph: '例 4' }, { k: 'c', label: '斜边 c', ph: '例 5' }],
    solve(v) {
      const b = v.b, c = v.c;
      if (c <= b) return { err: '斜边必须大于直角边（斜边是最长边）' };
      const a = Math.sqrt(c * c - b * b), A = T.deg(Math.acos(b / c));
      return {
        a, b, c, A, B: 90 - A,
        steps: [
          ['勾股定理反用', `a = √(c² − b²) = √(${T.len(c)}² − ${T.len(b)}²) = <code>${T.len(a)}</code>`],
          ['余弦 = 邻边 ÷ 斜边', `cos A = b / c = ${T.len(b)} / ${T.len(c)} = <code>${T.fmt(b / c, 4)}</code>`],
          ['反查角度', `A = arccos(${T.fmt(b / c, 4)}) = <code>${T.fmt(A, 2)}°</code>`],
          ['另一角', `B = 90° − A = <code>${T.fmt(90 - A, 2)}°</code>`],
          ['验算', `sin A = a / c = ${T.len(a)} / ${T.len(c)} = ${T.fmt(a / c, 4)} ✓`],
        ],
      };
    },
  },
  {
    id: 'Aa', label: '锐角 + 对边', hint: '一个角和它对着的边 → 用 sin / tan',
    fields: [{ k: 'A', label: '锐角 A', ph: '例 30', unit: '°' }, { k: 'a', label: '对边 a', ph: '例 1' }],
    solve(v) {
      const A = v.A, a = v.a;
      if (!(A > 0 && A < 90)) return { err: '锐角要在 0° ~ 90° 之间' };
      const c = a / T.sin(A), b = a / T.tan(A);
      return {
        a, b, c, A, B: 90 - A,
        steps: [
          ['正弦 = 对边 ÷ 斜边', `sin A = a / c → c = a / sin A = ${T.len(a)} / ${T.fmt(T.sin(A), 4)} = <code>${T.len(c)}</code>`],
          ['正切 = 对边 ÷ 邻边', `tan A = a / b → b = a / tan A = ${T.len(a)} / ${T.fmt(T.tan(A), 4)} = <code>${T.len(b)}</code>`],
          ['另一角', `B = 90° − A = <code>${T.fmt(90 - A, 2)}°</code>`],
          ['检查', `邻边 ${T.len(b)} 应该 > 对边 ${T.len(a)}？${b > a ? '是，因为 A < 45°' : '否，因为 A > 45°'} ✓`],
        ],
      };
    },
  },
  {
    id: 'Ab', label: '锐角 + 邻边', hint: '一个角和它旁边的直角边 → 用 tan / cos',
    fields: [{ k: 'A', label: '锐角 A', ph: '例 30', unit: '°' }, { k: 'b', label: '邻边 b', ph: '例 1' }],
    solve(v) {
      const A = v.A, b = v.b;
      if (!(A > 0 && A < 90)) return { err: '锐角要在 0° ~ 90° 之间' };
      const a = b * T.tan(A), c = b / T.cos(A);
      return {
        a, b, c, A, B: 90 - A,
        steps: [
          ['正切 = 对边 ÷ 邻边', `tan A = a / b → a = b · tan A = ${T.len(b)} × ${T.fmt(T.tan(A), 4)} = <code>${T.len(a)}</code>`],
          ['余弦 = 邻边 ÷ 斜边', `cos A = b / c → c = b / cos A = ${T.len(b)} / ${T.fmt(T.cos(A), 4)} = <code>${T.len(c)}</code>`],
          ['另一角', `B = 90° − A = <code>${T.fmt(90 - A, 2)}°</code>`],
          ['校验勾股', `√(a² + b²) = ${T.len(Math.hypot(a, b))}，与 c = ${T.len(c)} 一致 ✓`],
        ],
      };
    },
  },
  {
    id: 'Ac', label: '锐角 + 斜边', hint: '一个角和斜边 → 用 sin / cos 分解',
    fields: [{ k: 'A', label: '锐角 A', ph: '例 30', unit: '°' }, { k: 'c', label: '斜边 c', ph: '例 10' }],
    solve(v) {
      const A = v.A, c = v.c;
      if (!(A > 0 && A < 90)) return { err: '锐角要在 0° ~ 90° 之间' };
      const a = c * T.sin(A), b = c * T.cos(A);
      return {
        a, b, c, A, B: 90 - A,
        steps: [
          ['正弦 = 对边 ÷ 斜边', `a = c · sin A = ${T.len(c)} × ${T.fmt(T.sin(A), 4)} = <code>${T.len(a)}</code>`],
          ['余弦 = 邻边 ÷ 斜边', `b = c · cos A = ${T.len(c)} × ${T.fmt(T.cos(A), 4)} = <code>${T.len(b)}</code>`],
          ['另一角', `B = 90° − A = <code>${T.fmt(90 - A, 2)}°</code>`],
          ['口诀', `斜边乘 sin 得对边，乘 cos 得邻边 —— 这就是把斜边分解成两个直角边`],
        ],
      };
    },
  },
];

/* ---- 通用：算三个比值 ---- */
T.ratio = function (A) {
  return {
    sin: isFinite(T.sin(A)) ? T.sin(A) : NaN,
    cos: T.cos(A),
    tan: Math.abs(Math.cos(T.rad(A))) < 1e-9 ? Infinity : T.tan(A),
  };
};

/* ---- 绘图 ----
   o = { a, b, c, A, B, ref:'A'|'B', hot:['a','c'], compact:bool }
   约定：a = 相对 A 角的对边（竖直边 BC）
        b = 相对 A 角的邻边（水平边 AC）
        c = 斜边 AB
   参考角切成 B 时，对边/邻边自动互换 —— 这正是最容易混淆的点。 */
T.draw = function (o) {
  const W = 360, H = 252;
  const a = Math.max(o.a, 0), b = Math.max(o.b, 0), c = o.c || Math.hypot(a, b);
  const A = o.A, B = o.B != null ? o.B : 90 - o.A;
  const ref = o.ref || 'A';
  const hot = o.hot || [];
  const dimOthers = hot.length > 0;

  const gx = 46, top = 42, bot = 196;
  const aw = W - gx * 2, ah = bot - top;
  let s = Math.min(aw / Math.max(b, 1e-9), ah / Math.max(a, 1e-9));
  if (!isFinite(s) || s <= 0) s = 1;
  const tw = b * s, th = a * s;
  const x0 = (W - tw) / 2;
  const y1 = bot - (ah - th) / 2;
  const y0 = y1 - th;
  const PA = [x0, y1], PC = [x0 + tw, y1], PB = [x0 + tw, y0];

  /* 角色：相对参考角 */
  const role = ref === 'A'
    ? { a: 'opp', b: 'adj', c: 'hyp' }
    : { a: 'adj', b: 'opp', c: 'hyp' };
  const NAME = { opp: '对边', adj: '邻边', hyp: '斜边' };
  const COL = { opp: 'var(--opp)', adj: 'var(--adj)', hyp: 'var(--hyp)' };
  const LETTER = { a: 'a', b: 'b', c: 'c' };
  const VAL = { a: a, b: b, c: c };

  const seg = (p, q, key, w) => {
    const r = role[key], col = COL[r], isHot = hot.indexOf(key) >= 0;
    const cls = 'side' + (isHot ? ' hot' : (dimOthers ? ' dim' : ''));
    return `<line class="${cls}" x1="${p[0].toFixed(1)}" y1="${p[1].toFixed(1)}" ` +
      `x2="${q[0].toFixed(1)}" y2="${q[1].toFixed(1)}" ` +
      `stroke="${col}" stroke-width="${isHot ? 6 : (w || 3)}" style="color:${col}"/>`;
  };

  /* --- 三条边 --- */
  let g = '';
  g += seg(PA, PB, 'c');
  g += seg(PA, PC, 'b');
  g += seg(PC, PB, 'a');

  /* --- 直角标记（C 点） --- */
  const q = 13;
  g += `<polyline points="${(PC[0] - q).toFixed(1)},${PC[1].toFixed(1)} ${(PC[0] - q).toFixed(1)},${(PC[1] - q).toFixed(1)} ${PC[0].toFixed(1)},${(PC[1] - q).toFixed(1)}"
        fill="none" stroke="#6B7A8C" stroke-width="1.6"/>`;

  /* --- 角弧（用折线画，避免 arc 方向出错） --- */
  const arc = (V, P1, P2, r, on, txt, tx, ty, rot) => {
    const a1 = Math.atan2(P1[1] - V[1], P1[0] - V[0]);
    const a2 = Math.atan2(P2[1] - V[1], P2[0] - V[0]);
    let d = a2 - a1;
    while (d > Math.PI) d -= 2 * Math.PI;
    while (d < -Math.PI) d += 2 * Math.PI;
    let pts = '';
    for (let i = 0; i <= 18; i++) {
      const t = a1 + d * i / 18;
      pts += `${(V[0] + r * Math.cos(t)).toFixed(1)},${(V[1] + r * Math.sin(t)).toFixed(1)} `;
    }
    const col = on ? 'var(--opp)' : '#6B7A8C';
    const tr = rot ? ` transform="rotate(${rot.toFixed(1)} ${tx.toFixed(1)} ${ty.toFixed(1)})"` : '';
    return `<polyline points="${pts}" fill="none" stroke="${col}" stroke-width="${on ? 2.6 : 1.5}" opacity="${on ? 1 : .75}"/>` +
      `<text class="angl" x="${tx.toFixed(1)}" y="${ty.toFixed(1)}" text-anchor="middle" dominant-baseline="middle"${tr} ` +
      `fill="${on ? '#fff' : '#6B7A8C'}">${txt}</text>`;
  };

  /* 角标签摆位：
     夹角宽裕时横着写在角平分线上；
     夹角很尖时（如 80°/10° 的直角三角形），横写会撑出楔形去撞斜边，
     就把文字沿角平分线旋转，顺着狭长的楔形写 —— 跟制图规范一样。 */
  const angleLabel = (V, P1, P2, on, txt) => {
    const u1 = [P1[0] - V[0], P1[1] - V[1]];
    const u2 = [P2[0] - V[0], P2[1] - V[1]];
    const l1 = Math.hypot(u1[0], u1[1]) || 1, l2 = Math.hypot(u2[0], u2[1]) || 1;
    let ux = u1[0] / l1 + u2[0] / l2, uy = u1[1] / l1 + u2[1] / l2;
    const ul = Math.hypot(ux, uy) || 1; ux /= ul; uy /= ul;      /* 平分线单位向量 */
    const beta = Math.atan2(uy, ux);                            /* 平分线屏幕角 */
    const ang = Math.abs(Math.atan2(u1[0] * u2[1] - u1[1] * u2[0], u1[0] * u2[0] + u1[1] * u2[1]));
    const half = Math.max(ang / 2, 0.02);
    const r = on ? 27 : 23;
    const sharp = Math.max(0, Math.min(1, (32 - T.deg(ang)) / 18));   /* 越尖越像要旋转 */
    let d, rot = 0;
    if (sharp > 0.01) {
      d = Math.max(r + 22, 9 / Math.sin(half));      /* 旋转后只需半个字高的净距 */
      rot = T.deg(beta) * sharp;
    } else {
      d = Math.max(r + 17, 11 / Math.sin(half));     /* 横写要留出半行字高 */
    }
    /* 角平分线与对边交点到顶点的距离（角平分线长公式），别把字写出三角形去 */
    const Lbis = 2 * l1 * l2 * Math.cos(half) / (l1 + l2);
    d = Math.min(d, Lbis - (rot ? 24 : 10));
    d = Math.max(d, r + 14);
    const tx = V[0] + ux * d, ty = V[1] + uy * d;
    g += arc(V, P1, P2, r, on, txt, tx, ty, rot);
  };
  angleLabel(PA, PC, PB, ref === 'A', `A=${T.fmt(A, 2)}°`);
  angleLabel(PB, PC, PA, ref === 'B', `B=${T.fmt(B, 2)}°`);

  /* --- 边标签 --- */
  const lb = (x, y, rot, key) => {
    const r = role[key];
    const isHot = hot.indexOf(key) >= 0;
    const col = isHot ? COL[r] : (dimOthers ? '#7C8A9A' : COL[r]);
    const t = `transform="rotate(${rot.toFixed(1)} ${x.toFixed(1)} ${y.toFixed(1)})"`;
    return `<text class="lbl" x="${x.toFixed(1)}" y="${y.toFixed(1)}" text-anchor="middle" ` +
      `dominant-baseline="middle" ${t} fill="${col}">${NAME[r]} ${LETTER[key]}=${T.len(VAL[key])}</text>`;
  };
  /* b 边：底边下方 */
  g += lb((PA[0] + PC[0]) / 2, y1 + 26, 0, 'b');
  /* a 边：竖直边右侧，竖排（rotation -90） */
  g += lb(PC[0] + 17, (y0 + y1) / 2, -90, 'a');
  /* c 边：斜边外侧（从直角点指向斜边中点再往外推 18，避免压在 B 角标签上） */
  {
    const mid = [(PA[0] + PB[0]) / 2, (PA[1] + PB[1]) / 2];
    let vx = mid[0] - PC[0], vy = mid[1] - PC[1];
    const vl = Math.hypot(vx, vy) || 1; vx /= vl; vy /= vl;
    const off = (b * s < 90 || a * s < 90) ? 24 : 18;   /* 瘦三角形多推一点 */
    const lx = mid[0] + vx * off, ly = mid[1] + vy * off;
    const ang = Math.atan2(PB[1] - PA[1], PB[0] - PA[0]) * 180 / Math.PI;
    g += lb(lx, ly, ang, 'c');
  }

  /* --- 顶点字母 --- */
  const dot = (p, col) => `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="3.1" fill="${col}"/>`;
  g += dot(PA, '#E8EDF3') + dot(PB, '#E8EDF3') + dot(PC, '#6B7A8C');
  const vl = (p, t, col, dx, dy) =>
    `<text class="lbl sm" x="${(p[0] + dx).toFixed(1)}" y="${(p[1] + dy).toFixed(1)}" ` +
    `text-anchor="middle" dominant-baseline="middle" fill="${col}">${t}</text>`;
  g += vl(PA, 'A', ref === 'A' ? '#FFB43A' : '#8A97A8', -15, 15);
  g += vl(PB, 'B', ref === 'B' ? '#FFB43A' : '#8A97A8', 14, -9);
  g += vl(PC, 'C', '#8A97A8', 15, 15);

  return `<svg class="tri" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">${g}</svg>`;
};

/* 数据是否可用 */
T.valid = r => r && !r.err && isFinite(r.a) && isFinite(r.b) && isFinite(r.c) && r.a >= 0 && r.b >= 0;
