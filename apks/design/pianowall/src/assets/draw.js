/* ===========================================================
   draw.js — 2D 施工图纸（平面 / 展开立面 / 单元详图 / 剖面节点）
   全部按 mm 建模，用 Canvas 2D 出图；字号、线宽用 CSS 像素，保证手机上清晰。
   =========================================================== */
(function (global) {
  'use strict';
  var PW = global.PianoWall;
  var fmt = PW.fmt;

  var INK = '#101418', DIM = '#0a58c8', DIM2 = '#c1121f', MUTE = '#7a8794', GREEN = '#0a7a5a';
  var PAD = 8;

  /* ---------------- 画布 / 坐标 ---------------- */
  function Sheet(canvas, box, opts) {
    opts = opts || {};
    this.canvas = canvas;
    this.box = box;
    this.W = box.x1 - box.x0;
    this.H = box.y1 - box.y0;
    var host = (canvas.parentElement && canvas.parentElement.clientWidth) || 360;
    var s = Math.max((host - 2 * PAD) / this.W, opts.minS || 0);
    var dpr = Math.min(global.devicePixelRatio || 1, 3) * (opts.hiRes || 1);
    var cssW = this.W * s + 2 * PAD, cssH = this.H * s + 2 * PAD;
    canvas.style.width = cssW + 'px';
    canvas.style.height = cssH + 'px';
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(cssH * dpr);
    var ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.ctx = ctx; this.s = s; this.cssW = cssW; this.cssH = cssH;
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, cssW, cssH);
    ctx.lineJoin = 'miter';
  }
  Sheet.prototype.X = function (x) { return PAD + (x - this.box.x0) * this.s; };
  Sheet.prototype.Y = function (y) { return PAD + (y - this.box.y0) * this.s; };
  Sheet.prototype.L = function (mm) { return mm * this.s; };

  /* 建立图纸：自动在底部预留标题栏 + 说明用的空白带（按像素留，和屏幕无关地留够） */
  function mkSheet(canvas, x0, x1, top, bottom, opts) {
    var host = (canvas.parentElement && canvas.parentElement.clientWidth) || 360;
    var s = Math.max((host - 2 * PAD) / (x1 - x0), (opts && opts.minS) || 0);
    var band = Math.max(1300, 74 / s);
    return new Sheet(canvas, { x0: x0, x1: x1, y0: top, y1: bottom + band }, opts);
  }

  /* ---------------- 基础图元（坐标为 mm） ---------------- */
  function line(ctx, x1, y1, x2, y2, color, lw, dash) {
    ctx.save();
    ctx.strokeStyle = color || INK; ctx.lineWidth = lw || 1;
    if (dash) ctx.setLineDash(dash);
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
    ctx.restore();
  }
  function rect(ctx, x, y, w, h, fill, stroke, lw) {
    ctx.save();
    if (fill) { ctx.fillStyle = fill; ctx.fillRect(x, y, w, h); }
    if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = lw || 1; ctx.strokeRect(x + .5, y + .5, w - 1, h - 1); }
    ctx.restore();
  }
  function text(ctx, x, y, str, o) {
    o = o || {};
    var size = o.size || 11, weight = o.weight || 700;
    ctx.save();
    ctx.font = weight + ' ' + size + 'px "PingFang SC","Microsoft YaHei",system-ui,sans-serif';
    ctx.textAlign = o.align || 'center';
    ctx.textBaseline = o.base || 'middle';
    if (o.halo !== false) {
      ctx.lineWidth = size * 0.34; ctx.strokeStyle = o.haloColor || 'rgba(255,255,255,.95)';
      ctx.strokeText(str, x, y);
    }
    ctx.fillStyle = o.color || INK;
    ctx.fillText(str, x, y);
    ctx.restore();
  }
  function arrow(ctx, x, y, dx, dy, size, color) {
    var a = Math.atan2(dy, dx), w = size * 0.32;
    ctx.save(); ctx.fillStyle = color || INK;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(x - size * Math.cos(a) + w * Math.sin(a), y - size * Math.sin(a) - w * Math.cos(a));
    ctx.lineTo(x - size * Math.cos(a) - w * Math.sin(a), y - size * Math.sin(a) + w * Math.cos(a));
    ctx.closePath(); ctx.fill(); ctx.restore();
  }
  function hDim(ctx, x1, x2, y, yRef, label, o) {
    o = o || {};
    var L = (o.lw || 1), c = o.color || DIM;
    if (yRef != null && o.ext !== false) {
      line(ctx, x1, yRef, x1, y + (o.over || 5), c, L);
      line(ctx, x2, yRef, x2, y + (o.over || 5), c, L);
    }
    line(ctx, x1, y, x2, y, c, L);
    var s = o.arrow || 7;
    arrow(ctx, x1, y, -1, 0, s, c); arrow(ctx, x2, y, 1, 0, s, c);
    line(ctx, x1, y - 4, x1, y + 4, c, L); line(ctx, x2, y - 4, x2, y + 4, c, L);
    if (label) text(ctx, (x1 + x2) / 2, y - (o.tOff || 9), label,
      { size: o.size || 11, color: c, weight: 700 });
  }
  function vDim(ctx, y1, y2, x, xRef, label, o) {
    o = o || {};
    var L = (o.lw || 1), c = o.color || DIM;
    if (xRef != null && o.ext !== false) {
      line(ctx, xRef, y1, x + (o.over || 5) * (xRef > x ? -1 : 1), y1, c, L);
      line(ctx, xRef, y2, x + (o.over || 5) * (xRef > x ? -1 : 1), y2, c, L);
    }
    line(ctx, x, y1, x, y2, c, L);
    var s = o.arrow || 7;
    arrow(ctx, x, y1, 0, -1, s, c); arrow(ctx, x, y2, 0, 1, s, c);
    line(ctx, x - 4, y1, x + 4, y1, c, L); line(ctx, x - 4, y2, x + 4, y2, c, L);
    if (label) {
      ctx.save(); ctx.translate(x - (o.tOff || 9), (y1 + y2) / 2); ctx.rotate(-Math.PI / 2);
      text(ctx, 0, 0, label, { size: o.size || 11, color: c, weight: 700 });
      ctx.restore();
    }
  }
  /* 引线标注：箭头指在 (x,y)，文字在 (tx,ty) */
  function leader(ctx, x, y, tx, ty, label, o) {
    o = o || {};
    var c = o.color || INK;
    line(ctx, x, y, tx, ty, c, o.lw || 1);
    var dx = tx - x, dy = ty - y, len = Math.hypot(dx, dy) || 1;
    arrow(ctx, x, y, -dx / len, -dy / len, 7, c);
    if (o.tick !== false) {
      if (Math.abs(dy) > Math.abs(dx)) line(ctx, tx - 14, ty, tx + 14, ty, c, o.lw || 1);
      else line(ctx, tx, ty - 14, tx, ty + 14, c, o.lw || 1);
    }
    text(ctx, tx, ty + (o.dy == null ? -12 : o.dy), label,
      { size: o.size || 11, color: c, weight: 700, align: o.align || 'center' });
  }
  /* 标题栏 + 图名说明（都画在底部预留带里） */
  function titleBlock(sh, name, sub, anchor, notes) {
    var ctx = sh.ctx, w = Math.min(236, sh.cssW - 20), h = 42;
    var x = anchor === 'br' ? sh.cssW - 10 - w : 10;
    var y = sh.cssH - 10 - h;
    ctx.save();
    ctx.fillStyle = 'rgba(255,255,255,.96)'; ctx.fillRect(x, y, w, h);
    ctx.strokeStyle = INK; ctx.lineWidth = 1.2; ctx.strokeRect(x + .5, y + .5, w, h);
    line(ctx, x, y + 23, x + w, y + 23, INK, 1);
    text(ctx, x + 8, y + 11.5, name, { size: 12, align: 'left', halo: false });
    text(ctx, x + w - 8, y + 11.5, sub || '单位：mm', { size: 9.5, align: 'right', halo: false, color: MUTE });
    var bx = x + 8, by = y + 33, seg = Math.min(20, (w - 70) / 5);
    for (var i = 0; i < 5; i++) {
      ctx.fillStyle = i % 2 ? '#fff' : INK;
      ctx.fillRect(bx + i * seg, by - 4, seg, 8);
      text(ctx, bx + i * seg, by + 11, String(i), { size: 8, halo: false, color: MUTE });
    }
    text(ctx, bx + 5 * seg, by + 11, '5 m', { size: 8, align: 'left', halo: false, color: MUTE });
    ctx.restore();
    if (notes && notes.length) {
      var nx = anchor === 'br' ? 12 : x + w + 14;
      var ny = sh.cssH - 16 - (notes.length - 1) * 14;
      ctx.save();
      notes.forEach(function (t, i) {
        text(ctx, nx, ny + i * 14, '· ' + t, { size: 10, align: 'left', halo: false, color: '#4a5560', weight: 600 });
      });
      ctx.restore();
    }
  }

  /* ---------------- 钢琴键立面（共用） ---------------- */
  function elevation(ctx, sh, L, o) {
    var P = o.P, x0 = o.x0, y0 = o.y0;
    var blackH = sh.L(o.blackH), base = sh.L(P.baseH);
    var yTop = sh.Y(y0), yBot = sh.Y(y0 + P.wallH);
    rect(ctx, sh.X(x0), yTop, sh.L(L), sh.L(P.wallH), '#ffffff', null);
    for (var i = 0; i <= o.nWhite; i++) {
      line(ctx, sh.X(x0 + i * P.whiteW), yTop, sh.X(x0 + i * P.whiteW), yBot, '#aab4c0', 1);
    }
    for (var k = 0; k < o.blacks.length; k++) {
      rect(ctx, sh.X(x0 + o.blacks[k].x - P.blackW / 2), yTop, Math.max(1, sh.L(P.blackW)), blackH, '#141414', null);
    }
    rect(ctx, sh.X(x0), yBot - base, sh.L(L), base, '#141414', null);
    rect(ctx, sh.X(x0), yTop, sh.L(L), sh.L(P.wallH), null, INK, 1.4);
  }

  /* ================= 图纸 1：平面图 ================= */
  function drawPlan(canvas, data, hiRes) {
    var P = data.P, L = data.spanW, T = P.wallT, oct = data.octaveW;
    var sh = mkSheet(canvas, -2000, L + 1000, -1500, L + 1200, { minS: 0.02, hiRes: hiRes });
    var c = sh.ctx;

    rect(c, sh.X(0), sh.Y(0), sh.L(L), sh.L(T), '#e7ebf0', INK, 1.4);
    rect(c, sh.X(0), sh.Y(0), sh.L(T), sh.L(L), '#e7ebf0', INK, 1.4);
    line(c, sh.X(0), sh.Y(T), sh.X(L), sh.Y(T), '#141414', 3);
    line(c, sh.X(T), sh.Y(0), sh.X(T), sh.Y(L), '#141414', 3);
    for (var x = 0; x <= L; x += P.whiteW) line(c, sh.X(x), sh.Y(T), sh.X(x), sh.Y(T + 300), '#4c7dff', 1.2);
    for (var y = 0; y <= L; y += P.whiteW) line(c, sh.X(T), sh.Y(y), sh.X(T + 300), sh.Y(y), '#4c7dff', 1.2);
    for (var o = 0; o <= L; o += oct) {
      line(c, sh.X(o), sh.Y(T), sh.X(o), sh.Y(T + 560), DIM2, 2);
      line(c, sh.X(T), sh.Y(o), sh.X(T + 560), sh.Y(o), DIM2, 2);
    }
    hDim(c, sh.X(0), sh.X(L), sh.Y(-800), sh.Y(0), fmt(L), { size: 12 });
    vDim(c, sh.Y(0), sh.Y(L), sh.X(-800), sh.X(0), fmt(L), { size: 12 });
    /* 白键宽（靠转角，但90°标记已挪到更外圈） */
    hDim(c, sh.X(6 * P.whiteW), sh.X(7 * P.whiteW), sh.Y(T + 1100), sh.Y(T), '白键 ' + fmt(P.whiteW), { color: GREEN, size: 10.5 });
    vDim(c, sh.Y(L - oct), sh.Y(L), sh.X(T + 1500), sh.X(T), '八度 ' + fmt(oct), { color: DIM2, size: 10.5 });
    /* 90° 转角 */
    var r = 2600, cx = sh.X(0), cy = sh.Y(0);
    c.save(); c.strokeStyle = DIM2; c.lineWidth = 1.4;
    c.beginPath(); c.arc(cx, cy, sh.L(r), Math.PI / 2, 0); c.stroke();
    c.beginPath(); c.moveTo(cx, cy); c.lineTo(cx + sh.L(r * 1.12), cy); c.lineTo(cx, cy + sh.L(r * 1.12)); c.closePath(); c.stroke();
    c.restore();
    text(c, cx + sh.L(2300), cy + sh.L(2300), '90°', { size: 12, color: DIM2 });
    text(c, sh.X(L * 0.55), sh.Y(L * 0.58), '内院（键面朝向）', { size: 12, color: GREEN });
    arrow(c, sh.X(L * 0.55), sh.Y(L * 0.58) - 13, -0.45, -0.89, 9, GREEN);
    text(c, sh.X(-1400), sh.Y(-1150), '外侧（墙背）', { size: 10.5, color: MUTE, align: 'left' });
    leader(c, sh.X(L * 0.72), sh.Y(T / 2), sh.X(L * 0.72 + 1700), sh.Y(-420), '墙厚 ' + fmt(T), { color: MUTE, size: 10.5 });
    text(c, sh.X(T + 750), sh.Y(L + 80), 'B 面墙（长 ' + fmt(L) + '）', { size: 10.5, align: 'left' });
    text(c, sh.X(0), sh.Y(L + 520), 'A 面墙（长 ' + fmt(L) + '）', { size: 10.5, align: 'left' });
    titleBlock(sh, '平面图 · L 型转角', '比例见图上标尺', 'br',
      ['键位刻度朝向内院键面', '转角两面墙各自从整键起排']);
    return sh;
  }

  /* ================= 图纸 2：展开立面 ================= */
  function drawElev(canvas, data, hiRes) {
    var P = data.P, L = data.spanW, gapX = 700, oct = data.octaveW, H = P.wallH;
    var yBot = H + 150;
    var sh = mkSheet(canvas, -1600, 2 * L + gapX + 1400, -2100, yBot + 900, { minS: 0.045, hiRes: hiRes });
    var c = sh.ctx;

    hDim(c, sh.X(0), sh.X(2 * L + gapX), sh.Y(-1700), null, fmt(data.totalLen), { color: DIM2, ext: false, size: 13 });
    elevation(c, sh, L, { P: P, x0: 0, y0: 0, blackH: data.blackH, whiteH: data.whiteH, nWhite: data.nWhite, blacks: data.wallA.blacks });
    elevation(c, sh, L, { P: P, x0: L + gapX, y0: 0, blackH: data.blackH, whiteH: data.whiteH, nWhite: data.nWhite, blacks: data.wallB.blacks });

    /* 每面墙长 + 八度刻度（墙下方） */
    hDim(c, sh.X(0), sh.X(L), sh.Y(yBot + 620), sh.Y(yBot), fmt(L), { size: 11.5 });
    hDim(c, sh.X(L + gapX), sh.X(2 * L + gapX), sh.Y(yBot + 620), sh.Y(yBot), fmt(L), { size: 11.5 });
    for (var o = 0; o <= L; o += oct) {
      line(c, sh.X(o), sh.Y(yBot), sh.X(o), sh.Y(yBot + 240), DIM2, 1.6);
      line(c, sh.X(L + gapX + o), sh.Y(yBot), sh.X(L + gapX + o), sh.Y(yBot + 240), DIM2, 1.6);
    }
    text(c, sh.X(0), sh.Y(yBot + 330), '每 ' + fmt(oct) + ' 一组（7 白键）', { size: 10.5, color: DIM2, align: 'left' });
    text(c, sh.X(L + gapX), sh.Y(yBot + 330), '每 ' + fmt(oct) + ' 一组（7 白键）', { size: 10.5, color: DIM2, align: 'left' });
    /* 高度尺寸 */
    vDim(c, sh.Y(0), sh.Y(H), sh.X(-800), sh.X(0), fmt(H), { size: 12 });
    vDim(c, sh.Y(H - data.blackH), sh.Y(H), sh.X(2 * L + gapX + 600), sh.X(2 * L + gapX), fmt(data.blackH), { color: '#141414', size: 11 });
    vDim(c, sh.Y(H - data.baseH), sh.Y(H), sh.X(2 * L + gapX + 1500), sh.X(2 * L + gapX), fmt(data.baseH), { color: MUTE, size: 10 });
    /* 引注 */
    var bk = data.wallA.blacks[2] || data.wallA.blacks[0];
    leader(c, sh.X(bk ? bk.x : 900), sh.Y(H - data.blackH * 0.45), sh.X(bk ? bk.x : 900), sh.Y(-1250),
      '黑键 ' + fmt(P.blackW) + ' × ' + fmt(data.blackH), { color: INK });
    leader(c, sh.X(3.5 * P.whiteW), sh.Y(H - data.baseH - 80), sh.X(3.5 * P.whiteW), sh.Y(-800),
      '白键缝 ' + fmt(P.whiteW), { color: GREEN });
    leader(c, sh.X(L + gapX + 2.5 * P.whiteW), sh.Y(H - data.baseH * 0.5), sh.X(L + gapX + 2.5 * P.whiteW), sh.Y(-350),
      '黑踢脚 ' + fmt(data.baseH), { color: INK });
    line(c, sh.X(L + gapX / 2), sh.Y(-250), sh.X(L + gapX / 2), sh.Y(yBot + 780), '#9aa6b3', 1, [6, 5]);
    text(c, sh.X(L + gapX / 2), sh.Y(yBot + 760), '90° 转角', { size: 11, color: DIM2 });
    titleBlock(sh, '立面展开图（两面墙连续展开）', '单位：mm', 'bl',
      ['黑键自墙顶下挂 ' + fmt(data.blackH), '键缝内必须做深色背板，否则透亮']);
    return sh;
  }

  /* ================= 图纸 3：单元详图 ================= */
  function drawUnit(canvas, data, hiRes) {
    var P = data.P, oct = data.octaveW, L = oct + P.whiteW, H = P.wallH;
    var sh = mkSheet(canvas, -900, L + 1600, -1700, H + 1500, { minS: 0.08, hiRes: hiRes });
    var c = sh.ctx;
    var blacks = [];
    for (var i = 1; i < 9; i++) {
      var m = ((i - 1) % 7) + 1;
      if (PW.BLACK_AFTER.indexOf(m) >= 0 && i * P.whiteW < L) blacks.push({ x: i * P.whiteW });
    }
    elevation(c, sh, L, { P: P, x0: 0, y0: 0, blackH: data.blackH, whiteH: data.whiteH, nWhite: 8, blacks: blacks });
    var name = ['do', 're', 'mi', 'fa', 'sol', 'la', 'si'];
    for (var k = 0; k < 8; k++) {
      text(c, sh.X((k + 0.5) * P.whiteW), sh.Y(H - 350), name[k % 7], { size: 10, color: '#42546a' });
    }
    text(c, sh.X(L / 2), sh.Y(H - 520), '每 7 个白键一组', { size: 10.5, color: '#42546a' });
    /* 尺寸 */
    hDim(c, sh.X(0), sh.X(P.whiteW), sh.Y(H + 520), sh.Y(H), fmt(P.whiteW), { size: 10.5 });
    hDim(c, sh.X(P.whiteW), sh.X(2 * P.whiteW), sh.Y(H + 520), sh.Y(H), fmt(P.whiteW), { size: 10.5 });
    hDim(c, sh.X(0), sh.X(oct), sh.Y(H + 1000), sh.Y(H), '八度 ' + fmt(oct), { color: DIM2, size: 11.5 });
    hDim(c, sh.X(0), sh.X(L), sh.Y(-500), sh.Y(0), fmt(L), { color: DIM2, size: 11.5 });
    vDim(c, sh.Y(0), sh.Y(H), sh.X(-620), sh.X(0), fmt(H), { size: 11.5 });
    vDim(c, sh.Y(H - data.baseH), sh.Y(H), sh.X(L + 700), null, fmt(data.baseH), { size: 9.5, color: MUTE, over: 0, tOff: 7 });
    vDim(c, sh.Y(H - data.blackH), sh.Y(H), sh.X(L + 1300), null, fmt(data.blackH), { size: 10.5, color: '#141414', over: 0 });
    var b1 = blacks[0];
    if (b1) hDim(c, sh.X(b1.x - P.blackW / 2), sh.X(b1.x + P.blackW / 2), sh.Y(-1100), sh.Y(H - data.blackH), fmt(P.blackW), { size: 10, color: '#141414' });
    /* 2+3 分组 */
    var gy = sh.Y(H + 1380);
    line(c, sh.X(P.whiteW), gy, sh.X(3 * P.whiteW), gy, DIM2, 1.2);
    text(c, sh.X(2 * P.whiteW), gy - 12, '2 白键组', { size: 10, color: DIM2 });
    line(c, sh.X(3 * P.whiteW), gy, sh.X(7 * P.whiteW), gy, GREEN, 1.2);
    text(c, sh.X(5 * P.whiteW), gy - 12, '3 白键组', { size: 10, color: GREEN });
    titleBlock(sh, '单元详图（黑键定位 · 一组）', '单位：mm', 'bl',
      ['黑键居中于两白键拼缝', '一组 = 7 白键 = ' + fmt(oct) + ' mm', '键缝 ' + fmt(P.gap) + ' mm，缝后深色背板',
       '黑键凸出 ' + fmt(P.protrude) + ' mm', '黑键下沿到踢脚上沿 = ' + fmt(data.blackH - data.baseH) + ' mm']);
    return sh;
  }

  /* ================= 图纸 4：剖面节点 ================= */
  function drawSect(canvas, data, hiRes) {
    var P = data.P, T = P.wallT, pr = P.protrude, H = P.wallH;
    /* ① 水平剖面：板顶在 y=-900 */
    var hTop = -900;
    var gy = 500 + 900 + H;                    /* ② 地面线 */
    var sh = mkSheet(canvas, -2400, 4400, -2000, gy + 500, { minS: 0.075, hiRes: hiRes });
    var c = sh.ctx;

    /* 标题 ① */
    text(c, sh.X(-1200), sh.Y(-1850), '① 水平剖面（切一刀看板厚与黑键凸出）', { size: 12, align: 'left' });
    var secL = data.octaveW;                       /* 水平剖面取一个八度 */
    rect(c, sh.X(0), sh.Y(hTop), sh.L(secL), sh.L(T), '#dfe4ea', INK, 1.3);
    rect(c, sh.X(0), sh.Y(hTop + T), sh.L(secL), Math.max(2, sh.L(18)), '#4a5560', null);
    [1, 2, 4, 5, 6].forEach(function (n) {
      var xx = n * P.whiteW;
      rect(c, sh.X(xx - P.blackW / 2), sh.Y(hTop - pr), sh.L(P.blackW), Math.max(2, sh.L(pr)), '#141414', null);
    });
    line(c, sh.X(0), sh.Y(hTop), sh.X(secL), sh.Y(hTop), '#141414', 3);
    hDim(c, sh.X(0), sh.X(secL), sh.Y(500), sh.Y(hTop + T), fmt(secL) + '（一个八度）');
    vDim(c, sh.Y(hTop), sh.Y(hTop + T), sh.X(-900), null, '板厚 ' + fmt(T), { size: 10.5, over: 0 });
    leader(c, sh.X(P.whiteW), sh.Y(hTop - pr), sh.X(P.whiteW + 1200), sh.Y(-1450), '黑键：凸出 ' + fmt(pr) + ' / 宽 ' + fmt(P.blackW), { size: 10 });
    leader(c, sh.X(secL - 250), sh.Y(hTop + T * 0.5), sh.X(3100), sh.Y(-1150), '白键板 ' + fmt(T) + '（白色）', { color: MUTE, size: 10 });
    leader(c, sh.X(200), sh.Y(hTop + T + 18), sh.X(600), sh.Y(-350), '深色背板 18（封缝）', { color: MUTE, size: 10, align: 'left' });

    /* 标题 ② */
    text(c, sh.X(-1200), sh.Y(gy - H - 950), '② 竖向剖面（墙脚节点）', { size: 12, align: 'left' });
    var top = gy - H;
    rect(c, sh.X(0), sh.Y(top), sh.L(T), sh.L(H), '#dfe4ea', INK, 1.3);
    rect(c, sh.X(-pr), sh.Y(top), Math.max(2, sh.L(pr)), sh.L(data.blackH), '#141414', null);
    rect(c, sh.X(-pr), sh.Y(gy - data.baseH), sh.L(T + pr), sh.L(data.baseH), '#141414', INK, 1);
    rect(c, sh.X(T), sh.Y(top), Math.max(2, sh.L(18)), sh.L(H), '#4a5560', null);
    line(c, sh.X(-1100), sh.Y(gy), sh.X(1000), sh.Y(gy), INK, 1.6);
    for (var i = -1000; i < 900; i += 150) line(c, sh.X(i), sh.Y(gy), sh.X(i - 110), sh.Y(gy + 110), MUTE, .8);
    vDim(c, sh.Y(top), sh.Y(gy), sh.X(-2100), sh.X(-pr), fmt(H), { size: 11.5 });
    vDim(c, sh.Y(top), sh.Y(gy - data.blackH), sh.X(700), sh.X(T), fmt(data.blackH), { size: 10.5, color: '#141414' });
    vDim(c, sh.Y(gy - data.baseH), sh.Y(gy), sh.X(1500), sh.X(T), '踢脚 ' + fmt(data.baseH), { size: 10, color: MUTE });
    leader(c, sh.X(-pr * 0.5), sh.Y(gy - data.baseH - 900), sh.X(-1300), sh.Y(gy - H * 0.55), '黑键 ' + fmt(P.blackW) + ' / 厚 ' + fmt(pr), { color: '#141414', size: 10 });
    leader(c, sh.X(T + 9), sh.Y(top + 700), sh.X(2400), sh.Y(top + 400), '深色背板 18', { color: MUTE, size: 10 });
    leader(c, sh.X(T * 0.5), sh.Y(top + 200), sh.X(2400), sh.Y(top - 150), '白键板 ' + fmt(T), { color: MUTE, size: 10 });
    titleBlock(sh, '剖面节点图（① 水平 / ② 竖向）', '单位：mm', 'bl',
      ['黑键、踢脚凸出 ' + fmt(pr) + ' mm 形成投影线', '背板 18 mm 用来封住键缝']);
    return sh;
  }

  /* ---------------- 尺寸表 ---------------- */
  function dimTable(data) {
    var P = data.P;
    var rows = [
      ['单面墙长', fmt(data.spanW) + ' mm'],
      ['两面墙总展开长', fmt(data.totalLen) + ' mm（' + (data.totalLen / 1000).toFixed(1) + ' m）'],
      ['墙高', fmt(P.wallH) + ' mm'],
      ['墙体（面板）厚度', fmt(P.wallT) + ' mm'],
      ['白键宽 / 分块宽', fmt(P.whiteW) + ' mm'],
      ['黑键宽', fmt(P.blackW) + ' mm（白键的 ' + (data.blackRatioW * 100).toFixed(1) + '%）'],
      ['黑键高（自墙顶下量）', fmt(data.blackH) + ' mm（墙高的 ' + (data.blackRatioH * 100).toFixed(1) + '%）'],
      ['黑键下沿离地', fmt(data.blackBottom) + ' mm'],
      ['底部黑踢脚带高', fmt(data.baseH) + ' mm'],
      ['白键板净高', fmt(data.whiteH) + ' mm'],
      ['键板拼缝', fmt(P.gap) + ' mm'],
      ['黑键 / 踢脚凸出', fmt(P.protrude) + ' mm'],
      ['一个八度（7 白键）', fmt(data.octaveW) + ' mm'],
      ['转角', '90°'],
      ['白键总数（两面墙）', data.nWhiteTotal + ' 块'],
      ['黑键总数（两面墙）', data.nBlackTotal + ' 块']
    ];
    var h = '<h3>尺寸表 / DIMENSION TABLE</h3><table><tr><th>项目</th><th>尺寸</th></tr>';
    rows.forEach(function (r) { h += '<tr><td>' + r[0] + '</td><td class="n">' + r[1] + '</td></tr>'; });
    h += '</table>';
    return h;
  }

  global.Draw2D = {
    drawAll: function (data, hiRes) {
      hiRes = hiRes || 1;
      return {
        plan: drawPlan(document.getElementById('cv-plan'), data, hiRes),
        elev: drawElev(document.getElementById('cv-elev'), data, hiRes),
        unit: drawUnit(document.getElementById('cv-unit'), data, hiRes),
        sect: drawSect(document.getElementById('cv-sect'), data, hiRes)
      };
    },
    /* 单独重绘并导出 PNG（2 倍分辨率） */
    exportPng: function (kind, data) {
      var cv = document.createElement('canvas');
      var fig = document.createElement('figure');
      fig.style.cssText = 'position:fixed;left:-99999px;top:0;width:440px';
      fig.appendChild(cv); document.body.appendChild(fig);
      var fn = { plan: drawPlan, elev: drawElev, unit: drawUnit, sect: drawSect }[kind];
      fn(cv, data, 2);
      var url = cv.toDataURL('image/png');
      document.body.removeChild(fig);
      return url;
    },
    dimTable: dimTable
  };
})(window);
