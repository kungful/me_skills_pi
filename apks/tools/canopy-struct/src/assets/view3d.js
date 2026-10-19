/* =====================================================================
   view3d.js —— three.js 三维受力模型
   世界坐标：x=沿长边墙，y=向上，z=从墙向院内
   ===================================================================== */
const V3 = (function () {

  let ok = false, why = '', renderer, scene, camera, canvas, host;
  let groups = {}, labels = [], R = null, opt = null;
  let cam = { az: 0.62, pol: 1.02, dist: 14, tx: 4, ty: 1.35, tz: 1.9 };
  let dragging = false, lastX = 0, lastY = 0, pinch = 0, lastTap = 0;

  const UTIL = u => u > 1 ? 0xFF5A5A : u > 0.85 ? 0xFFB84D : 0x44C7A9;

  /* ---------------- 贴图：网布 / 砖 ---------------- */
  function netTexture() {
    const c = document.createElement('canvas'); c.width = c.height = 128;
    const g = c.getContext('2d');
    g.clearRect(0, 0, 128, 128);
    g.strokeStyle = 'rgba(140,240,215,.85)'; g.lineWidth = 2.2;
    for (let i = 0; i <= 16; i++) {
      const p = i * 8;
      g.beginPath(); g.moveTo(p, 0); g.lineTo(p, 128); g.stroke();
      g.beginPath(); g.moveTo(0, p); g.lineTo(128, p); g.stroke();
    }
    const t = new THREE.CanvasTexture(c);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    return t;
  }
  function brickTexture() {
    const c = document.createElement('canvas'); c.width = c.height = 64;
    const g = c.getContext('2d');
    g.fillStyle = '#6b4a3c'; g.fillRect(0, 0, 64, 64);
    g.strokeStyle = 'rgba(230,220,210,.45)'; g.lineWidth = 1.6;
    for (let r = 0; r < 8; r++) {
      const y = r * 8;
      g.beginPath(); g.moveTo(0, y); g.lineTo(64, y); g.stroke();
      const off = (r % 2) * 16;
      for (let k = 0; k < 2; k++) {
        const x = (off + k * 32) % 64;
        g.beginPath(); g.moveTo(x, y); g.lineTo(x, y + 8); g.stroke();
      }
    }
    const t = new THREE.CanvasTexture(c);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    return t;
  }
  function labelSprite(text, col) {
    const c = document.createElement('canvas');
    const g0 = c.getContext('2d');
    g0.font = '600 44px -apple-system,"Microsoft YaHei",sans-serif';
    const wpx = Math.max(96, Math.ceil(g0.measureText(text).width) + 34);
    c.width = wpx; c.height = 64;
    const g = c.getContext('2d');
    g.fillStyle = 'rgba(10,16,20,.78)';
    g.strokeStyle = col || '#44C7A9'; g.lineWidth = 2;
    g.beginPath(); g.roundRect ? g.roundRect(2, 2, wpx - 4, 60, 12) : g.rect(2, 2, wpx - 4, 60);
    g.fill(); g.stroke();
    g.font = '600 40px -apple-system,"Microsoft YaHei",sans-serif';
    g.fillStyle = col || '#44C7A9'; g.textAlign = 'center'; g.textBaseline = 'middle';
    g.fillText(text, wpx / 2, 33);
    const t = new THREE.CanvasTexture(c);
    const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: t, transparent: true, depthTest: false }));
    sp.scale.set(wpx / 64 * 0.40, 0.40, 1);
    return sp;
  }

  /* ---------------- 初始化 ---------------- */
  function init(el) {
    host = el;
    try {
      if (!window.THREE || !window.WebGLRenderingContext) throw new Error('no webgl');
      canvas = document.createElement('canvas');
      canvas.id = 'cv3';
      host.innerHTML = '';
      host.appendChild(canvas);
      renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, preserveDrawingBuffer: true });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      try {
        if (THREE.SRGBColorSpace && 'outputColorSpace' in renderer) renderer.outputColorSpace = THREE.SRGBColorSpace;
        else if (THREE.sRGBEncoding && 'outputEncoding' in renderer) renderer.outputEncoding = THREE.sRGBEncoding;
      } catch (e) { }
      scene = new THREE.Scene();
      scene.background = new THREE.Color(0x0A0F13);
      scene.fog = new THREE.Fog(0x0A0F13, 30, 90);
      camera = new THREE.PerspectiveCamera(42, 1, 0.1, 400);
      const amb = new THREE.AmbientLight(0xffffff, 0.72); scene.add(amb);
      const d1 = new THREE.DirectionalLight(0xffffff, 0.85); d1.position.set(12, 20, 14); scene.add(d1);
      const d2 = new THREE.DirectionalLight(0x88ccff, 0.35); d2.position.set(-14, 8, -10); scene.add(d2);
      const grid = new THREE.GridHelper(40, 40, 0x1c2a34, 0x141f27);
      grid.position.set(4, 0, 2); grid.material.opacity = .85; grid.material.transparent = true;
      scene.add(grid);
      ok = true;
      bind();
      resize();
    } catch (e) {
      ok = false; why = String(e && e.message || e);
      host.innerHTML = '<div style="padding:24px;color:#8FA3B0;font-size:13px;line-height:1.8">'
        + '这台设备/WebView 打不开 WebGL，三维视图不可用。<br>切到「平面/内力」页照常看受力图和计算结果。</div>';
    }
    return ok;
  }

  function resize() {
    if (!ok) return;
    const W = host.clientWidth || 320, H = host.clientHeight || 300;
    // 竖屏时不要把画布拉成一根长条：限高 ≈ 1.02×宽，竖直居中
    const h = Math.max(200, Math.min(H, W * 1.02));
    canvas.style.width = W + 'px';
    canvas.style.height = h + 'px';
    canvas.style.top = Math.max(0, (H - h) / 2) + 'px';
    renderer.setSize(W, h, false);
    camera.aspect = W / h; camera.updateProjectionMatrix();
    draw();
  }

  /* ---------------- 交互 ---------------- */
  function bind() {
    canvas.addEventListener('touchstart', e => {
      if (e.touches.length === 1) { dragging = true; lastX = e.touches[0].clientX; lastY = e.touches[0].clientY; }
      else if (e.touches.length === 2) {
        pinch = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
      }
    }, { passive: true });
    canvas.addEventListener('touchmove', e => {
      e.preventDefault();
      if (e.touches.length === 1 && dragging) {
        const dx = e.touches[0].clientX - lastX, dy = e.touches[0].clientY - lastY;
        lastX = e.touches[0].clientX; lastY = e.touches[0].clientY;
        cam.az -= dx * 0.0075; cam.pol = Math.max(0.18, Math.min(1.52, cam.pol - dy * 0.006));
        draw();
      } else if (e.touches.length === 2) {
        const d = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY);
        if (pinch) cam.dist = Math.max(4, Math.min(70, cam.dist * pinch / d));
        pinch = d; draw();
      }
    }, { passive: false });
    canvas.addEventListener('touchend', () => { dragging = false; pinch = 0; });
    // 桌面调试（鼠标）
    canvas.addEventListener('mousedown', e => { dragging = true; lastX = e.clientX; lastY = e.clientY; });
    window.addEventListener('mousemove', e => {
      if (!dragging) return;
      cam.az -= (e.clientX - lastX) * 0.0075; cam.pol = Math.max(0.18, Math.min(1.52, cam.pol - (e.clientY - lastY) * 0.006));
      lastX = e.clientX; lastY = e.clientY; draw();
    });
    window.addEventListener('mouseup', () => dragging = false);
    canvas.addEventListener('wheel', e => { e.preventDefault(); cam.dist = Math.max(4, Math.min(70, cam.dist * (1 + e.deltaY * 0.0012))); draw(); }, { passive: false });
  }

  function resetView() { cam = { az: 0.62, pol: 1.02, dist: 14, tx: 4, ty: 1.35, tz: 1.9 }; draw(); }
  function topView() { cam = { az: 0.0001, pol: 0.20, dist: 13, tx: 4, ty: 0.5, tz: 2.0 }; draw(); }
  function frontView() { cam = { az: 0.0001, pol: 1.30, dist: 11.5, tx: 4, ty: 1.4, tz: 2.0 }; draw(); }
  function endView() { cam = { az: 1.5708, pol: 1.35, dist: 11, tx: 1.2, ty: 1.4, tz: 2.0 }; draw(); }

  function fitDist() {
    // 用当前模型的实际包围球算"刚好装得下"的距离
    let R = 6;
    try {
      const box = new THREE.Box3().setFromObject(scene);
      const sph = box.getBoundingSphere(new THREE.Sphere());
      R = Math.max(2.5, sph.radius);
    } catch (e) { }
    const halfY = camera.fov * Math.PI / 360;
    const halfX = Math.atan(Math.tan(halfY) * Math.max(camera.aspect, 0.2));
    const half = Math.min(halfY, halfX);
    return R / Math.sin(half) * 0.92;
  }
  function draw() {
    if (!ok) return;
    const t = new THREE.Vector3(cam.tx, cam.ty, cam.tz);
    camera.position.set(
      t.x + cam.dist * Math.sin(cam.pol) * Math.sin(cam.az),
      t.y + cam.dist * Math.cos(cam.pol),
      t.z + cam.dist * Math.sin(cam.pol) * Math.cos(cam.az));
    // 远程只有"不超过装得下的距离"时才拉远，绝不缩小到看不见
    const fd = fitDist();
    const d = Math.min(cam.dist, fd);
    camera.position.sub(t).multiplyScalar(d / Math.max(cam.dist, 0.001)).add(t);
    camera.lookAt(t);
    renderer.render(scene, camera);
  }

  /* ---------------- 几何工具 ---------------- */
  function tube(a, b, r, col, parent) {
    const dx = b.x - a.x, dy = b.y - a.y, dz = b.z - a.z;
    const L = Math.hypot(dx, dy, dz);
    if (L < 1e-6) return null;
    const g = new THREE.CylinderGeometry(r, r, L, 10, 1);
    const m = new THREE.MeshStandardMaterial({ color: col, roughness: .55, metalness: .45 });
    const mesh = new THREE.Mesh(g, m);
    mesh.position.set((a.x + b.x) / 2, (a.y + b.y) / 2, (a.z + b.z) / 2);
    mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0),
      new THREE.Vector3(dx / L, dy / L, dz / L));
    parent.add(mesh);
    return mesh;
  }
  function box(cx, cy, cz, sx, sy, sz, col, parent, opacity) {
    const m = new THREE.MeshStandardMaterial({ color: col, roughness: .85, metalness: .05,
      transparent: opacity !== undefined, opacity: opacity === undefined ? 1 : opacity });
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(sx, sy, sz), m);
    mesh.position.set(cx, cy, cz);
    parent.add(mesh);
    return mesh;
  }
  function arrow3(a, b, col, parent, rad) {
    const dir = new THREE.Vector3(b.x - a.x, b.y - a.y, b.z - a.z);
    const L = dir.length(); if (L < 1e-6) return;
    const mat = new THREE.MeshStandardMaterial({ color: col, roughness: .5, emissive: col, emissiveIntensity: .28 });
    const shaft = new THREE.Mesh(new THREE.CylinderGeometry(rad || .045, rad || .045, L * 0.72, 8), mat);
    shaft.position.copy(new THREE.Vector3(a.x, a.y, a.z).add(dir.clone().multiplyScalar(0.36)));
    shaft.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.clone().normalize());
    parent.add(shaft);
    const head = new THREE.Mesh(new THREE.ConeGeometry((rad || .045) * 2.6, L * 0.28, 10), mat);
    head.position.copy(new THREE.Vector3(a.x, a.y, a.z).add(dir.clone().multiplyScalar(L * 0.86)));
    head.quaternion.copy(shaft.quaternion);
    parent.add(head);
  }

  /* ---------------- 建模 ---------------- */
  function build(RR, o) {
    if (!ok) return;
    R = RR; opt = o || {};
    const P = R.P, geo = R.geo;

    Object.values(groups).forEach(gp => scene.remove(gp));
    labels.forEach(s => scene.remove(s));
    groups = {}; labels = [];

    const G = {
      wall: new THREE.Group(), net: new THREE.Group(), frame: new THREE.Group(),
      found: new THREE.Group(), load: new THREE.Group(), reac: new THREE.Group(), label: new THREE.Group(),
    };
    Object.values(G).forEach(gp => scene.add(gp));
    groups = G;

    /* 墙 */
    const bt = brickTexture(); bt.repeat.set(Math.max(1, P.Wx / 1.2), Math.max(1, P.Hw / 0.6));
    const bw = new THREE.Mesh(new THREE.BoxGeometry(P.Wx, P.Hw, 0.24),
      new THREE.MeshStandardMaterial({ map: bt, roughness: .95 }));
    bw.position.set(P.Wx / 2, P.Hw / 2, -0.12);
    G.wall.add(bw);
    const bt2 = brickTexture(); bt2.repeat.set(Math.max(1, P.Wy / 1.2), Math.max(1, P.Hw / 0.6));
    const bw2 = new THREE.Mesh(new THREE.BoxGeometry(0.24, P.Hw, P.Wy),
      new THREE.MeshStandardMaterial({ map: bt2, roughness: .95 }));
    bw2.position.set(-0.12, P.Hw / 2, P.Wy / 2);
    G.wall.add(bw2);
    if (o.showNet !== false) {
      const l1 = labelSprite(`长边墙 ${P.Wx.toFixed(1)}m`, '#a8846c');
      l1.scale.multiplyScalar(0.8);
      l1.position.set(P.Wx * 0.88, P.Hw + 0.25, 0.35); G.label.add(l1);
      const l2 = labelSprite(`短边墙 ${P.Wy.toFixed(1)}m`, '#a8846c');
      l2.scale.multiplyScalar(0.8);
      l2.position.set(0.35, P.Hw + 0.25, P.Wy * 0.9); G.label.add(l2);
    }

    /* 网面 */
    const nt = netTexture();
    const nx = Math.round(geo.netL * 4), nz = Math.round(geo.netW * 4);
    nt.repeat.set(nx, nz);
    const slope = P.slopeDeg * Math.PI / 180;
    const geoPlane = new THREE.PlaneGeometry(geo.netL, geo.netW / Math.cos(slope));
    const netMat = new THREE.MeshStandardMaterial({
      map: nt, transparent: true, opacity: 0.78, side: THREE.DoubleSide,
      color: 0xffffff, roughness: .9, metalness: 0, alphaTest: 0.05, depthWrite: false,
    });
    const net = new THREE.Mesh(geoPlane, netMat);
    net.rotation.x = -Math.PI / 2 + slope;
    net.position.set(geo.netL / 2, P.h - geo.rise / 2, geo.netW / 2);
    G.net.add(net);
    // 网的四条边
    const rc = 0.022;
    tube({ x: 0, y: P.h, z: 0 }, { x: geo.netL, y: P.h, z: 0 }, rc, 0x2fbf9b, G.net);
    tube({ x: 0, y: P.h - geo.rise, z: geo.netW }, { x: geo.netL, y: P.h - geo.rise, z: geo.netW }, rc, 0x2fbf9b, G.net);

    /* 每根柱一套 */
    const maxDefl = Math.max(...R.perCol.flatMap(p => ['up', 'down', 'wind'].map(k => Math.abs(p.cases[k].defl))), 1e-4);
    const dscale = (opt.deflScale || 0) > 0 ? (0.55 / maxDefl) * opt.deflScale / 10 : 0;
    const caseKey = o.caseKey || 'up';

    geo.cols.forEach((c, ci) => {
      const row = R.perCol[ci].cases[caseKey];
      const fr = row.frame;
      const uMain = row.frame;                     // 用当前工况的节点位移放大变形
      const dz = node => (uMain.res.U[node * 3] || 0) * dscale;      // 局部 x（悬臂方向）
      const dy = node => (uMain.res.U[node * 3 + 1] || 0) * dscale;  // 竖直
      // 局部 (lx=沿悬臂, ly=标高) + 节点位移 → 世界
      const Wv = (lx, ly, node) => ({
        x: c.base.x,
        y: ly + (node === undefined ? 0 : dy(node)),
        z: c.base.y + lx + (node === undefined ? 0 : dz(node)),
      });
      const nTipY = P.h - (c.L / geo.netW) * geo.rise;
      const vBase = Wv(0, 0, 0), vJ = Wv(0, P.h, 1), vTip = Wv(c.L, nTipY, 2);
      const yA0 = P.diagType === 'below' ? P.h - P.r : P.h + P.r;
      const vA = Wv(0, yA0, 3);
      const vOnCol = P.diagType === 'below' ? Wv(0, P.h, 1) : Wv(0, P.h, 1);
      // 柱（含上段）
      const colUtil = row.col.sigmaUtil;
      const beamUtil = row.beam.sigmaUtil;
      const cc = UTIL(colUtil), bc = UTIL(beamUtil);
      // 柱（必要时分段画到锚点）
      if (P.diagType === 'below' && P.r > 0) {
        tube(vBase, vA, 0.052, cc, G.frame);
        tube(vA, vJ, 0.048, cc, G.frame);
      } else {
        tube(vBase, vJ, 0.052, cc, G.frame);
        if (P.diagType !== 'none' && P.r > 0) tube(vJ, vA, 0.044, cc, G.frame);
      }
      // 挑梁
      tube(vJ, vTip, 0.052, bc, G.frame);
      // 斜杆
      if (P.diagType !== 'none' && P.r > 0) {
        const live = !fr.diagDropped;
        const dcol = !live ? 0x3a4a55 : (fr.diag && (-fr.diag._fl[0]) > 0 ? 0x44C7A9 : 0xFFB84D);
        tube(vA, vTip, live ? 0.032 : 0.02, dcol, G.frame);
      }
      // 基础
      box(c.base.x, -P.footH / 2, c.base.y, P.footB, P.footH, P.footB, 0x53636d, G.found, 0.95);
      // 顶梁标记 + 标签
      const lbl = labelSprite(c.id, UTIL(row.col.sigmaUtil) === 0x44C7A9 ? '#44C7A9' : UTIL(row.col.sigmaUtil) === 0xFFB84D ? '#FFB84D' : '#FF6B6B');
      lbl.position.set(c.base.x, P.h + (P.diagType !== 'none' ? P.r : 0) + 0.45, c.base.y);
      G.label.add(lbl);
      const lb2 = labelSprite(`悬臂${c.L.toFixed(2)} 分担${c.tw.toFixed(2)}m`, '#9FB4C2');
      lb2.scale.multiplyScalar(0.72);
      lb2.position.set(c.tip.x, P.h - (c.L / geo.netW) * geo.rise + 0.22 + (ci % 2) * 0.28, geo.netW + 0.1);
      G.label.add(lb2);

      /* 荷载箭头 */
      const Pv = -row.Pvert, Fx = row.Fx;
      const tipW = { x: c.tip.x, y: P.h - (c.L / geo.netW) * geo.rise, z: geo.netW };
      if (Math.abs(Pv) > 1) {
        const up = Pv > 0, hgt = 0.85;
        const a = { x: tipW.x, y: up ? tipW.y + hgt : tipW.y - hgt, z: tipW.z };
        const b = { x: tipW.x, y: up ? tipW.y + 0.06 : tipW.y - 0.06, z: tipW.z };
        arrow3(a, b, 0xFF9F43, G.load, 0.038);
      }
      if (Math.abs(Fx) > 1) {
        const s = Fx > 0 ? 1 : -1;
        arrow3({ x: tipW.x, y: tipW.y + 0.22, z: tipW.z - 0.9 * s },
               { x: tipW.x, y: tipW.y + 0.22, z: tipW.z - 0.06 * s }, 0x5CC8FF, G.load, 0.034);
      }
      /* 支反力 */
      const b = row.base;
      if (b.N < 0) arrow3({ x: c.base.x, y: 0.8, z: c.base.y }, { x: c.base.x, y: 0.06, z: c.base.y }, 0xFF5A5A, G.reac, 0.042);
      else arrow3({ x: c.base.x, y: -0.8, z: c.base.y }, { x: c.base.x, y: -0.05, z: c.base.y }, 0x5CC8FF, G.reac, 0.042);
    });

    /* 沿墙纵梁 */
    const xs = geo.cols.map(c => c.base.x);
    tube({ x: Math.min(...xs), y: P.h, z: geo.cols[0].base.y }, { x: Math.max(...xs), y: P.h, z: geo.cols[0].base.y },
         0.036, 0x7d8f9b, G.frame);
    /* 外缘边梁 */
    tube({ x: 0, y: P.h - geo.rise, z: geo.netW }, { x: geo.netL, y: P.h - geo.rise, z: geo.netW }, 0.036, 0x7d8f9b, G.frame);

    /* 风 */
    if (o.showWind !== false) {
      const wh = P.h + 1.1;
      for (let k = 0; k < 5; k++) {
        const x = geo.netL * (0.12 + 0.19 * k);
        arrow3({ x, y: wh, z: geo.netW + 1.6 }, { x, y: wh, z: geo.netW + 0.15 }, 0x4FA8FF, G.load, 0.028);
      }
      const wl = labelSprite(`风 ${R.W.v.toFixed(0)} m/s  ${R.W.beaufort}`, '#5CC8FF');
      wl.position.set(geo.netL / 2, wh + 0.55, geo.netW + 0.9); G.label.add(wl);
    }
    if (o.showNet === false) G.net.visible = false;
    if (o.showLoad === false) G.load.visible = false;
    if (o.showReac === false) G.reac.visible = false;
    if (o.showFrame === false) G.frame.visible = false;
    if (o.showFound === false) G.found.visible = false;
    if (o.showLabel === false) G.label.visible = false;
    draw();
  }

  /* 切回三维页时，把已有的 canvas 重新挂回宿主（切 tab 会重建面板，旧 canvas 会被丢弃） */
  function attach(el) {
    if (!ok || !canvas) return false;
    host = el;
    if (canvas.parentNode !== el) { el.innerHTML = ''; el.appendChild(canvas); }
    resize();
    return true;
  }
  function setVisible(g, v) { if (ok && groups[g]) { groups[g].visible = v; draw(); } }
  function isOk() { return ok; }
  function whyNot() { return why; }
  function probe() {
    const out = [];
    const pts = [[0,0,0],[8,0,0],[8,3.5,4],[0,0,4],[4,0,2]];
    for (const p of pts) {
      const v = new THREE.Vector3(p[0], p[1], p[2]).project(camera);
      out.push(p.join(',') + ' -> ' + v.x.toFixed(2) + ',' + v.y.toFixed(2) + ',' + v.z.toFixed(2));
    }
    return out.join(' | ');
  }
  function debug() {
    if (!ok) return { ok: false, why };
    return { ok: true, tris: renderer.info.render.triangles, calls: renderer.info.render.calls,
             kids: scene.children.length, camPos: camera.position.toArray().map(v => +v.toFixed(2)),
             cw: canvas.width, ch: canvas.height, cwCss: canvas.clientWidth, chCss: canvas.clientHeight };
  }

  return { init, attach, build, draw, resize, resetView, topView, frontView, endView, setVisible, isOk, whyNot, debug, probe, UTIL };
})();
