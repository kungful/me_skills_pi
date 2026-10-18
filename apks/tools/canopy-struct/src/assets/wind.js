/* =====================================================================
   wind.js —— 风荷载（GB 50009-2012 体系的简化实现）
   w_k = βgz · μs · μz · w0        [kN/m²]
   另外给：风速 ↔ 风压、蒲福风级、地区基本风压、反算最大风速
   ===================================================================== */
const WIND = (function () {

  /* 基本风压 w0 (kN/m²)，GB50009 附录 E 常见城市 50 年重现期（近似值） */
  const REGIONS = {
    '三亚': 0.90, '海口': 0.85, '厦门': 0.80, '深圳': 0.75, '福州': 0.70,
    '大连': 0.65, '青岛': 0.60, '广州': 0.60, '乌鲁木齐': 0.60,
    '上海': 0.55, '杭州': 0.50, '天津': 0.50, '宁波': 0.50, '温州': 0.60,
    '北京': 0.45, '济南': 0.45, '郑州': 0.45, '沈阳': 0.55, '哈尔滨': 0.55,
    '南京': 0.40, '南昌': 0.40, '石家庄': 0.35, '合肥': 0.35,
    '武汉': 0.35, '长沙': 0.35, '西安': 0.35, '南宁': 0.35, '太原': 0.30,
    '成都': 0.30, '重庆': 0.30, '昆明': 0.30, '贵阳': 0.30, '兰州': 0.30,
    '拉萨': 0.30, '银川': 0.35, '呼和浩特': 0.45,
    '自定义': 0.60,
  };

  /* 地面粗糙度 A/B/C/D */
  const ROUGH = {
    A: { t: 'A 类 海岸·海岛·湖岸·荒漠', muz: [1.09, 1.28, 1.42, 1.52, 1.67, 1.79, 1.89, 1.97],
         bz: [1.69, 1.65, 1.60, 1.57, 1.53, 1.50, 1.47, 1.45] },
    B: { t: 'B 类 田野·乡村·丛林·房屋稀疏乡镇', muz: [1.00, 1.00, 1.13, 1.23, 1.39, 1.52, 1.62, 1.71],
         bz: [1.76, 1.70, 1.66, 1.63, 1.59, 1.56, 1.54, 1.52] },
    C: { t: 'C 类 有密集建筑群的城市市区', muz: [0.65, 0.65, 0.65, 0.74, 0.88, 1.00, 1.10, 1.20],
         bz: [1.95, 1.85, 1.79, 1.77, 1.71, 1.68, 1.65, 1.63] },
    D: { t: 'D 类 密集建筑群且房屋较高的市区', muz: [0.51, 0.51, 0.51, 0.51, 0.51, 0.60, 0.69, 0.77],
         bz: [2.20, 2.05, 1.99, 1.94, 1.86, 1.82, 1.79, 1.76] },
  };
  const ZS = [5, 10, 15, 20, 30, 40, 50, 60];

  function interp(tab, z) {
    if (z <= ZS[0]) return tab[0];
    if (z >= ZS[ZS.length - 1]) return tab[tab.length - 1];
    for (let i = 0; i < ZS.length - 1; i++) {
      if (z >= ZS[i] && z <= ZS[i + 1]) {
        const f = Math.log(z / ZS[i]) / Math.log(ZS[i + 1] / ZS[i]);
        return tab[i] + f * (tab[i + 1] - tab[i]);
      }
    }
    return tab[0];
  }

  /* 风速 m/s → 风压 kN/m²（w = v²/1600） */
  const v2w = v => v * v / 1600;
  const w2v = w => Math.sqrt(1600 * Math.max(w, 0));

  /* 蒲福风级（10 分钟平均） */
  const BF = [
    [0.3, '0 级 无风'], [1.6, '1 级 软风'], [3.4, '2 级 轻风'], [5.5, '3 级 微风'],
    [8.0, '4 级 和风'], [10.8, '5 级 清风'], [13.9, '6 级 强风'], [17.2, '7 级 疾风'],
    [20.8, '8 级 大风'], [24.5, '9 级 烈风'], [28.5, '10 级 狂风'], [32.7, '11 级 暴风'],
    [37.0, '12 级 飓风'], [41.5, '13 级'], [46.2, '14 级'], [51.0, '15 级'],
    [56.1, '16 级'], [61.3, '17 级 台风'], [1e9, '17 级以上'],
  ];
  function beaufort(v) { for (const b of BF) if (v < b[0]) return b[1]; return '17 级以上'; }

  /* 网布的体型/阻力系数：孔隙率越高越"透风" */
  function coeff(kind, porosity) {
    const p = Math.max(0, Math.min(0.95, porosity));
    if (kind === 'up')   return 1.25 * (1 - p) + 0.10;   // 风吸（垂直网面向上）
    if (kind === 'down') return 0.55 * (1 - p) + 0.03;   // 风压（垂直网面向下）
    if (kind === 'drag') return 1.30 * (1 - p) + 0.15;   // 水平风力（迎风投影）
    if (kind === 'wall') return 1.30;                    // 砖墙迎风
    return 1;
  }

  /* 主计算：给参数 → 各种风压 */
  function calc(P) {
    const w0 = P.w0 * (P.w0Factor || 1), rough = ROUGH[P.rough] || ROUGH.C;
    const z = Math.max(5, P.z);
    const muz = interp(rough.muz, z);
    const bgz = interp(rough.bz, z);
    const wk = bgz * muz * w0;                            // kN/m²（未乘体型系数）
    const v = w2v(w0);
    return {
      w0, w0base: P.w0, w0Factor: P.w0Factor || 1, z, muz, bgz, wk, v, rough: P.rough, roughText: rough.t,
      beaufort: beaufort(v),
      cUp: P.cManual ? P.Cup : coeff('up', P.porosity),
      cDown: P.cManual ? P.Cdown : coeff('down', P.porosity),
      cDrag: P.cManual ? P.Cdrag : coeff('drag', P.porosity),
      qUp: wk * (P.cManual ? P.Cup : coeff('up', P.porosity)),       // kN/m²
      qDown: wk * (P.cManual ? P.Cdown : coeff('down', P.porosity)),
      qDrag: wk * (P.cManual ? P.Cdrag : coeff('drag', P.porosity)),
    };
  }

  return { REGIONS, ROUGH, ZS, interp, v2w, w2v, beaufort, coeff, calc, BF };
})();
if (typeof module !== 'undefined') module.exports = WIND;
