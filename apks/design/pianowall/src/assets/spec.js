/* ===========================================================
   spec.js — 钢琴墙的全部尺寸 / 排布 / 用料计算（唯一数据源）
   3D 视图、2D 图纸、规格说明都从这里取数，保证一致。
   单位：mm
   =========================================================== */
(function (global) {
  'use strict';

  /* ---------- 默认图纸尺寸（用户给定：两面 10 m × 2 m，90° 相接） ---------- */
  var DEFAULTS = {
    wallLen: 10000,   // 单面墙长
    wallH:   2000,    // 墙高
    wallT:   120,     // 墙体（面板）厚度
    whiteW:  500,     // 白键宽（= 面板分块宽）
    blackW:  295,     // 黑键宽
    blackH:  1300,    // 黑键高（自墙顶往下量，= 墙高的 65%）
    baseH:   150,     // 底部黑色踢脚带高
    gap:     8,       // 白键板之间留缝
    protrude: 25,     // 黑键 / 踢脚带凸出白键面
    mirror:  1        // 1 = 两面墙在转角处各自起一整键（左右对称）
  };

  /* 每 7 个白键为一组（do re mi fa sol la si），
     黑键落在第 1、2、4、5、6 个白键的右侧接缝上 */
  var BLACK_AFTER = [1, 2, 4, 5, 6];

  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }

  /* ---------- 核心：由参数算出完整图案排布 ---------- */
  function layout(P) {
    var whiteW = P.whiteW;
    var nWhite = Math.max(1, Math.round(P.wallLen / whiteW));      // 每面墙白键数
    var spanW = nWhite * whiteW;                                   // 图案实际总长（取整后）
    var baseH = clamp(P.baseH, 0, P.wallH - 300);
    var whiteH = P.wallH - baseH;                                  // 白键板高
    var blackH = clamp(P.blackH, 200, whiteH - 20);                // 黑键高
    var blackTop = P.wallH;                                        // 黑键顶 = 墙顶
    var blackBottom = P.wallH - blackH;

    // —— 两面墙的白键 ——
    function whites(phase) {
      var out = [];
      for (var i = 1; i <= nWhite; i++) {
        var m = ((i - 1 + phase) % 7) + 1;                          // 该键在音阶里的位置
        out.push({ idx: i, m: m, x0: (i - 1) * whiteW, x1: i * whiteW, w: whiteW });
      }
      return out;
    }
    // —— 两面墙的黑键（落在接缝上；最后一块白键右侧留空，避免被墙端切掉）——
    function blacks(phase) {
      var out = [];
      for (var i = 1; i < nWhite; i++) {
        var m = ((i - 1 + phase) % 7) + 1;
        if (BLACK_AFTER.indexOf(m) >= 0) {
          out.push({ after: i, m: m, x: i * whiteW, x0: i * whiteW - P.blackW / 2, x1: i * whiteW + P.blackW / 2 });
        }
      }
      return out;
    }

    var phaseA = 0;
    var phaseB = P.mirror ? 0 : (nWhite % 7);                       // 不镜像时图案跨过转角继续

    var walls = [
      { id: 'A', name: '外墙 A', dir: '南北向', phase: phaseA, len: spanW },
      { id: 'B', name: '外墙 B', dir: '东西向', phase: phaseB, len: spanW }
    ];

    var areas = function (o) {
      var wk = nWhite, bk = o.black.length;
      var keyArea = bk * P.blackW * blackH;                        // 黑键盖住的白键面积
      return {
        id: o.id, name: o.name, len: o.len, nWhite: wk, nBlack: bk,
        baseH: baseH, whiteH: whiteH, blackH: blackH,   /* 供 3D 建模直接取值 */
        whiteArea: Math.max(0, wk * whiteW * whiteH - keyArea),      // 白键可见面积 mm²
        blackArea: keyArea,
        baseArea: o.len * baseH,
        faceArea: o.len * P.wallH,
        blacks: o.black, whites: o.white
      };
    };

    var WA = { id: 'A', name: 'A 面', len: spanW, white: whites(phaseA), black: blacks(phaseA) };
    var WB = { id: 'B', name: 'B 面', len: spanW, white: whites(phaseB), black: blacks(phaseB) };
    var wallA = areas(WA), wallB = areas(WB);

    var mm2 = function (v) { return v / 1e6; };                     // mm² → m²
    var totWhite = mm2(wallA.whiteArea + wallB.whiteArea);
    var totBlack = mm2(wallA.blackArea + wallB.blackArea) + mm2(wallA.baseArea + wallB.baseArea);
    var totFace = mm2(wallA.faceArea + wallB.faceArea);

    return {
      P: P,
      nWhite: nWhite, spanW: spanW, spanH: P.wallH, baseH: baseH, whiteH: whiteH,
      blackH: blackH, blackTop: blackTop, blackBottom: blackBottom,
      wallA: wallA, wallB: wallB,
      totalLen: 2 * spanW,
      totalFace: totFace,
      whiteArea: totWhite,
      blackArea: totBlack,
      nWhiteTotal: wallA.nWhite + wallB.nWhite,
      nBlackTotal: wallA.nBlack + wallB.nBlack,
      /* 涂料估算：面漆 0.12 L/m²/遍 × 2 遍 × 1.1 损耗 */
      paintWhite: totWhite * 0.12 * 2 * 1.1,
      paintBlack: totBlack * 0.12 * 2 * 1.1,
      octaveW: 7 * whiteW,
      blackRatioW: P.blackW / whiteW,
      blackRatioH: blackH / P.wallH
    };
  }

  /* ---------- 数字 / 尺寸文本 ---------- */
  function fmt(v, dec) {
    dec = dec || 0;
    var s = (+v).toFixed(dec);
    var p = s.split('.');
    p[0] = p[0].replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
    return p.join('.');
  }
  function fmt2(v) { return (+v).toFixed(2); }

  global.PianoWall = {
    DEFAULTS: DEFAULTS,
    BLACK_AFTER: BLACK_AFTER,
    layout: layout,
    fmt: fmt,
    fmt2: fmt2,
    clamp: clamp
  };
})(window);
