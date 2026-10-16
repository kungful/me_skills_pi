/* ===========================================================
   app.js — 钢琴墙 3D 演示（Three.js / WebGL）
   单位：模型里是米（mm / 1000），参数面板里是 mm
   =========================================================== */
(function () {
  'use strict';
  var PW = window.PianoWall, fmt = PW.fmt;
  var MM = 0.001;

  /* ---------------- 参数 ---------------- */
  var P = Object.assign({}, PW.DEFAULTS);
  var data = PW.layout(P);

  var PARAM_DEFS = [
    { k: 'wallLen', label: '墙长', min: 4000, max: 24000, step: 100 },
    { k: 'wallH', label: '墙高', min: 1200, max: 4000, step: 50 },
    { k: 'whiteW', label: '白键宽', min: 200, max: 900, step: 5 },
    { k: 'blackW', label: '黑键宽', min: 100, max: 600, step: 5 },
    { k: 'blackH', label: '黑键高', min: 300, max: 2600, step: 10 },
    { k: 'baseH', label: '踢脚高', min: 0, max: 500, step: 5 },
    { k: 'gap', label: '键缝', min: 0, max: 30, step: 1 },
    { k: 'wallT', label: '墙体厚', min: 60, max: 400, step: 10 },
    { k: 'protrude', label: '凸出', min: 0, max: 80, step: 5 },
    { k: 'mirror', label: '转角镜像', toggle: true }
  ];

  /* ---------------- 3D 场景 ---------------- */
  var renderer, scene, camera, canvas;
  var wallRoot, dimRoot, figure, groundMesh, grid;
  var state = { dims: true, scale: true, spin: false, legend: false };   /* 标注 / 人形 / 自动旋转 / 数据面板 */
  var G = { white: null, black: null, back: null, dark: null };
  var selRoot = null, selObj = null, selDims = null, dimLeaders = null;
  var ray = new THREE.Raycaster();
  var UP = new THREE.Vector3(0, 1, 0);
  var curView = '全景', userMoved = false;

  /* 视角：目标点 + 方向 + 需要的距离（自动按当前画布宽高比算，横竖屏都装得下） */
  function viewPose(name) {
    var L = data.spanW * MM, H = P.wallH * MM;
    var c = new THREE.Vector3(L / 2, H * 0.5, L / 2);
    var vHalf = camera.fov * Math.PI / 360;
    var hHalf = Math.atan(Math.tan(vHalf) * camera.aspect);
    var tan = Math.tan(Math.min(vHalf, hHalf));
    function dist(radius, mul) { return radius / tan * (mul || 1.06); }
    var R = Math.hypot(L, H) * 0.80;
    if (name === '全景') {
      var d = dist(R);
      return { tgt: c, pos: c.clone().add(new THREE.Vector3(1, 0.78, 1).normalize().multiplyScalar(d)), up: UP };
    }
    if (name === '人视') {
      return {
        tgt: new THREE.Vector3(L * 0.08, H * 0.55, L * 0.08),
        pos: new THREE.Vector3(L * 0.82, 1.68, L * 0.82), up: UP
      };
    }
    if (name === '正视') {
      return {
        tgt: new THREE.Vector3(L / 2, H * 0.5, 0),
        pos: new THREE.Vector3(L / 2, H * 0.5, dist(L * 0.64)), up: UP
      };
    }
    if (name === '俯视') {
      var d2 = dist(L * 0.72);
      return { tgt: new THREE.Vector3(L / 2, 0, L / 2), pos: new THREE.Vector3(L / 2 + 0.001, d2, L / 2 + 0.001), up: new THREE.Vector3(0, 0, -1) };
    }
    if (name === '转角') {
      return { tgt: new THREE.Vector3(0.5, H * 0.6, 0.5), pos: new THREE.Vector3(3.3, H * 0.95, 3.3), up: UP };
    }
    /* 黑键特写 */
    var bk = data.wallA.blacks[1] || data.wallA.blacks[0] || { x: P.whiteW };
    var cx0 = bk.x * MM;
    return {
      tgt: new THREE.Vector3(cx0, H * 0.5, 0),
      pos: new THREE.Vector3(cx0 - 0.45, H * 0.55, 3.4), up: UP
    };
  }

  function initGL() {
    canvas = document.getElementById('gl');
    renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, powerPreference: 'high-performance' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.02;

    scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0xc9d3de, 45, 150);

    camera = new THREE.PerspectiveCamera(50, 1, 0.05, 900);

    /* 天空 */
    var skyMat = new THREE.ShaderMaterial({
      side: THREE.BackSide, depthWrite: false, fog: false,
      uniforms: { top: { value: new THREE.Color(0x7fa6d8) }, bot: { value: new THREE.Color(0xe8e4dc) } },
      vertexShader: 'varying vec3 vP; void main(){ vP=(modelMatrix*vec4(position,1.)).xyz; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
      fragmentShader: 'uniform vec3 top; uniform vec3 bot; varying vec3 vP; void main(){ float t=clamp(normalize(vP).y*.55+.42,0.,1.); gl_FragColor=vec4(mix(bot,top,t),1.);}'
    });
    scene.add(new THREE.Mesh(new THREE.SphereGeometry(300, 32, 16), skyMat));

    /* 光 */
    scene.add(new THREE.HemisphereLight(0xbdd4f2, 0x8b8577, 0.75));
    var sun = new THREE.DirectionalLight(0xfff3e2, 2.35);
    sun.position.set(16, 20, 9);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    var sc = sun.shadow.camera;
    sc.left = -20; sc.right = 20; sc.top = 20; sc.bottom = -20; sc.near = 1; sc.far = 70;
    sun.shadow.bias = -0.0007;
    sun.shadow.normalBias = 0.02;
    sun.target.position.set(4.5, 0.8, 4.5);
    scene.add(sun); scene.add(sun.target);

    /* 地面 */
    groundMesh = new THREE.Mesh(
      new THREE.PlaneGeometry(200, 200),
      new THREE.MeshStandardMaterial({ color: 0xb3b0aa, roughness: 0.97, metalness: 0 })
    );
    groundMesh.rotation.x = -Math.PI / 2;
    groundMesh.receiveShadow = true;
    scene.add(groundMesh);
    grid = new THREE.GridHelper(60, 60, 0x8d949c, 0x9aa1a8);
    grid.material.transparent = true; grid.material.opacity = 0.18;
    grid.position.y = 0.002;
    scene.add(grid);

    G.white = new THREE.MeshStandardMaterial({ color: 0xf3f1ec, roughness: 0.62, metalness: 0.02 });
    G.black = new THREE.MeshStandardMaterial({ color: 0x101010, roughness: 0.4, metalness: 0.12 });
    G.back = new THREE.MeshStandardMaterial({ color: 0x353b43, roughness: 0.95 });
    G.dark = new THREE.MeshStandardMaterial({ color: 0x2f3b4a, roughness: 0.85 });

    /* 人形参考 */
    figure = new THREE.Group();
    var body = new THREE.Mesh(new THREE.CapsuleGeometry(0.21, 1.0, 6, 16), G.dark);
    body.position.y = 0.72; body.castShadow = true;
    var head = new THREE.Mesh(new THREE.SphereGeometry(0.125, 20, 14), G.dark);
    head.position.y = 1.55; head.castShadow = true;
    figure.add(body, head);
    figure.position.set(2.9, 0, 1.35);
    scene.add(figure);

    /* 选中单块时，在这里临时挂它的尺寸标注 */
    selRoot = new THREE.Group();
    scene.add(selRoot);

    window.addEventListener('resize', resize);
    if (window.ResizeObserver) new ResizeObserver(resize).observe(canvas.parentElement);
  }

  function resize() {
    if (!renderer) return;
    var host = canvas.parentElement;
    var w = host.clientWidth || window.innerWidth;
    var h = host.clientHeight || window.innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(1, h);
    camera.updateProjectionMatrix();
    if (!userMoved) setView(curView, true);
  }

  /* ---------------- 建墙 ---------------- */
  function box(w, h, d, mat) { return new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); }

  /* back = -1：墙身向 -Z 延伸；back = +1：墙身向 +Z 延伸（转角处旋转 -90° 用） */
  function buildWall(L, layoutW, back, wid) {
    var g = new THREE.Group();
    var T = P.wallT * MM, p = P.protrude * MM, gap = P.gap * MM;
    var H = P.wallH * MM, baseH = layoutW.baseH * MM, whiteH = layoutW.whiteH * MM;
    var blackH = layoutW.blackH * MM, blackW = P.blackW * MM;

    /* 背板（把拼缝堵住，同时是深色底） */
    var back_panel = box(L, H, 0.018, G.back);
    back_panel.position.set(L / 2, H / 2, back * (T + 0.009));
    back_panel.castShadow = true; back_panel.receiveShadow = true;
    g.add(back_panel);

    /* 白键板（每块 500 宽，留缝）—— 每块都带上自己的身份，可点击查看尺寸 */
    layoutW.whites.forEach(function (w) {
      var m = box(w.w * MM - gap, whiteH, T, G.white);
      m.position.set((w.x0 + w.x1) / 2 * MM, baseH + whiteH / 2, back * T / 2);
      m.castShadow = true; m.receiveShadow = true;
      m.userData.key = { kind: 'white', wall: wid, idx: w.idx, m: w.m, x0: w.x0, x1: w.x1 };
      g.add(m);
    });

    /* 底部黑色踢脚带 */
    var base = box(L, Math.max(baseH, 0.001), T + p, G.black);
    base.position.set(L / 2, baseH / 2, back * (T - p) / 2);
    base.castShadow = true; base.receiveShadow = true;
    base.userData.key = { kind: 'base', wall: wid };
    g.add(base);

    /* 黑键（凸出白键面 p） */
    layoutW.blacks.forEach(function (b) {
      var m = box(blackW, blackH, T + p, G.black);
      m.position.set(b.x * MM, H - blackH / 2, back * (T - p) / 2);
      m.castShadow = true; m.receiveShadow = true;
      m.userData.key = { kind: 'black', wall: wid, after: b.after, m: b.m, x: b.x };
      g.add(m);
    });
    return g;
  }

  function rebuildWalls() {
    select(null);
    if (wallRoot) { scene.remove(wallRoot); disposeTree(wallRoot); }
    wallRoot = new THREE.Group();
    var L = data.spanW * MM;
    wallRoot.add(buildWall(L, data.wallA, -1, 'A'));
    var wb = buildWall(L, data.wallB, +1, 'B');
    wb.rotation.y = -Math.PI / 2;
    wallRoot.add(wb);
    scene.add(wallRoot);
  }

  function disposeTree(root) {
    root.traverse(function (o) {
      if (o.geometry) o.geometry.dispose();
      if (o.material && o.material.map) o.material.map.dispose();
      if (o.material && o.material.isSpriteMaterial) o.material.dispose();
    });
  }

  /* ---------------- 尺寸标注 ---------------- */
  var LABELS = [];      /* 屏幕恒定字号的标注精灵 */
  function makeLabel(text, o) {
    o = o || {};
    var fs = 128, pad = 26;
    var c = document.createElement('canvas'), g = c.getContext('2d');
    var font = '700 ' + fs + 'px "PingFang SC","Microsoft YaHei",system-ui,sans-serif';
    g.font = font;
    var w = Math.ceil(g.measureText(text).width) + pad * 2;
    var h = fs + pad * 1.4;
    c.width = w; c.height = h;
    g = c.getContext('2d');
    g.font = font; g.textAlign = 'center'; g.textBaseline = 'middle';
    var r = h * 0.26;
    g.beginPath();
    g.moveTo(r, 0); g.lineTo(w - r, 0); g.quadraticCurveTo(w, 0, w, r);
    g.lineTo(w, h - r); g.quadraticCurveTo(w, h, w - r, h);
    g.lineTo(r, h); g.quadraticCurveTo(0, h, 0, h - r);
    g.lineTo(0, r); g.quadraticCurveTo(0, 0, r, 0); g.closePath();
    g.fillStyle = o.bg || 'rgba(255,255,255,.94)'; g.fill();
    g.lineWidth = 5; g.strokeStyle = o.border || 'rgba(10,88,200,.55)'; g.stroke();
    g.fillStyle = o.color || '#0a3d8f';
    g.fillText(text, w / 2, h / 2 + fs * 0.04);
    var tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 4;
    var sp = new THREE.Sprite(new THREE.SpriteMaterial({
      map: tex, transparent: true, depthWrite: false, depthTest: true
    }));
    sp.renderOrder = 10;
    sp.userData.px = o.px || 14;       /* 想要的屏幕高度（CSS 像素） */
    sp.userData.ratio = w / h;
    sp.scale.set(0.3 * w / h, 0.3, 1);
    LABELS.push(sp);
    return sp;
  }

  /* 让标注文字不管远近都保持差不多的屏幕字号 */
  function updateLabelScale() {
    var h = renderer.domElement.clientHeight || 600;
    var mpp = 2 * Math.tan(camera.fov * Math.PI / 360) / h;   /* 距相机 1 m 处，1 CSS 像素 = 多少米 */
    for (var i = 0; i < LABELS.length; i++) {
      var sp = LABELS[i];
      var d = sp.position.distanceTo(camera.position);
      var sz = Math.min(1.6, Math.max(0.04, d * mpp * sp.userData.px));
      sp.scale.set(sz * sp.userData.ratio, sz, 1);
    }
  }

  function dashLine(a, b, color, dash, gap) {
    var geo = new THREE.BufferGeometry().setFromPoints([a, b]);
    var m = new THREE.LineDashedMaterial({
      color: color, dashSize: dash || 0.13, gapSize: gap || 0.09,
      transparent: true, depthWrite: false
    });
    var l = new THREE.Line(geo, m);
    l.computeLineDistances();
    return l;
  }
  function solidLine(a, b, color, op) {
    var m = new THREE.LineBasicMaterial({ color: color, transparent: op != null, opacity: op == null ? 1 : op });
    return new THREE.Line(new THREE.BufferGeometry().setFromPoints([a, b]), m);
  }
  var V = function (x, y, z) { return new THREE.Vector3(x, y, z); };

  /* 线性尺寸：从 a 量到 b，偏移 off（Vector3），label 显示在中间 */
  function dimLinear(a, b, off, label, o) {
    o = o || {};
    var c = o.color || 0x0a3d8f, grp = new THREE.Group();
    var A = a.clone().add(off), B = b.clone().add(off);
    var dir = new THREE.Vector3().subVectors(B, A).normalize();
    var perp = off.clone().normalize();
    grp.add(solidLine(a.clone().add(perp.clone().multiplyScalar(0.04)), A.clone().add(perp.clone().multiplyScalar(o.ext || 0.3)), c, 0.55));
    grp.add(solidLine(b.clone().add(perp.clone().multiplyScalar(0.04)), B.clone().add(perp.clone().multiplyScalar(o.ext || 0.3)), c, 0.55));
    grp.add(dashLine(A, B, c));
    var s = o.arrowSize || 0.13;
    [A, B].forEach(function (pt, i) {
      var cone = new THREE.Mesh(new THREE.ConeGeometry(s * 0.34, s, 10),
        new THREE.MeshBasicMaterial({ color: c }));
      cone.position.copy(pt);
      var d = i === 0 ? dir.clone().negate() : dir.clone();
      cone.quaternion.setFromUnitVectors(V(0, 1, 0), d);
      grp.add(cone);
    });
    var lb = makeLabel(label, { px: o.px || 14 });
    lb.position.copy(A.clone().add(B).multiplyScalar(0.5)).add(perp.clone().multiplyScalar(o.lbOff || 0.34));
    grp.add(lb);
    return grp;
  }

  function leaderLabel(from, to, label, o) {
    o = o || {};
    var grp = new THREE.Group(), c = o.color || 0x0a3d8f;
    grp.add(solidLine(from, to, c, 0.85));
    var cone = new THREE.Mesh(new THREE.ConeGeometry(0.05, 0.16, 10), new THREE.MeshBasicMaterial({ color: c }));
    cone.position.copy(from);
    cone.quaternion.setFromUnitVectors(V(0, 1, 0), new THREE.Vector3().subVectors(from, to).normalize());
    grp.add(cone);
    var lb = makeLabel(label, { px: o.px || 13, bg: o.bg, border: o.border, color: o.tc });
    lb.position.copy(to);
    grp.add(lb);
    return grp;
  }

  function rebuildDims() {
    if (dimRoot) { scene.remove(dimRoot); disposeTree(dimRoot); }
    LABELS = [];
    dimRoot = new THREE.Group();
    var L = data.spanW * MM, H = P.wallH * MM, baseH = data.baseH * MM;

    /* A / B 面墙长 */
    dimRoot.add(dimLinear(V(0, 0.05, 0), V(L, 0.05, 0), V(0, 0, 1.15), fmt(data.spanW)));
    dimRoot.add(dimLinear(V(0, 0.05, 0), V(0, 0.05, L), V(1.15, 0, 0), fmt(data.spanW)));
    /* 高度（两面墙的自由端） */
    dimRoot.add(dimLinear(V(L, 0, 0), V(L, H, 0), V(0.95, 0, 0), fmt(P.wallH), { lbOff: 0.02, px: 15 }));
    dimRoot.add(dimLinear(V(0, 0, L), V(0, H, L), V(0, 0, 0.95), fmt(P.wallH), { lbOff: 0.02, px: 15 }));

    /* 90° 转角 */
    var r = 1.75, pts = [];
    for (var i = 0; i <= 32; i++) {
      var t = i / 32 * Math.PI / 2;
      pts.push(V(Math.cos(t) * r, 0.03, Math.sin(t) * r));
    }
    dimRoot.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color: 0xc1121f })));
    dimRoot.add(solidLine(V(0, 0.03, 0), V(r * 1.12, 0.03, 0), 0xc1121f, 0.8));
    dimRoot.add(solidLine(V(0, 0.03, 0), V(0, 0.03, r * 1.12), 0xc1121f, 0.8));
    var ang = makeLabel('90°', { px: 15, color: '#c1121f', border: 'rgba(193,18,31,.5)' });
    ang.position.set(Math.cos(Math.PI / 4) * r * 1.5, 0.32, Math.sin(Math.PI / 4) * r * 1.5);
    dimRoot.add(ang);

    /* 引注：沿墙分散，避免堆在转角（选中某一块时自动收起来） */
    dimLeaders = new THREE.Group();
    dimRoot.add(dimLeaders);
    function blackAt(idx) {
      var a = data.wallA.blacks;
      return a[Math.min(idx, a.length - 1)] || a[0];
    }
    var b1 = blackAt(Math.round(data.wallA.blacks.length * 0.28));
    if (b1) dimLeaders.add(leaderLabel(
      V(b1.x * MM, H - data.blackH * MM * 0.55, 0.035),
      V(b1.x * MM, H + 0.55, 1.35),
      '黑键 ' + fmt(P.blackW) + ' × ' + fmt(data.blackH)));
    var b2 = blackAt(Math.round(data.wallA.blacks.length * 0.72));
    if (b2) dimLeaders.add(leaderLabel(
      V(b2.x * MM + P.whiteW * MM * 0.5, H - data.blackH * MM * 0.7, 0.035),
      V(b2.x * MM + P.whiteW * MM * 1.2, H + 0.15, 1.15),
      '白键宽 ' + fmt(P.whiteW), { tc: '#0a7a5a', border: 'rgba(10,122,90,.5)' }));
    var b3 = blackAt(data.wallA.blacks.length - 2);
    if (b3) dimLeaders.add(leaderLabel(
      V(b3.x * MM + P.whiteW * MM * 0.5 - P.gap * MM, H - data.blackH * MM * 0.95, 0.035),
      V(b3.x * MM + P.whiteW * MM * 0.5, H * 0.62, 1.5),
      '白键缝 ' + fmt(P.gap), { tc: '#333', border: 'rgba(0,0,0,.35)', px: 12.5 }));
    /* B 面墙上的踢脚带 + 高度 */
    dimLeaders.add(leaderLabel(
      V(0.035, baseH * 0.5, L * 0.55),
      V(1.35, 0.45, L * 0.58),
      '黑踢脚 ' + fmt(data.baseH), { tc: '#333', border: 'rgba(0,0,0,.35)' }));
    dimLeaders.add(leaderLabel(
      V(0.035, H * 0.5, L * 0.3),
      V(1.35, H * 0.62, L * 0.26),
      '墙高 ' + fmt(P.wallH), { tc: '#333', border: 'rgba(0,0,0,.35)' }));

    dimRoot.visible = state.dims;
    scene.add(dimRoot);
  }

  /* ============ 点某一块键板 → 看这块的尺寸 ============ */
  var HL = {
    white: new THREE.MeshStandardMaterial({ color: 0xffe08a, roughness: 0.42, emissive: 0x6b4a00, emissiveIntensity: 0.45 }),
    black: new THREE.MeshStandardMaterial({ color: 0x3f7bff, roughness: 0.35, emissive: 0x0b2a66, emissiveIntensity: 0.7 }),
    base: new THREE.MeshStandardMaterial({ color: 0xffb454, roughness: 0.45, emissive: 0x5a3200, emissiveIntensity: 0.45 })
  };
  var NOTE = ['do', 're', 'mi', 'fa', 'sol', 'la', 'si'];
  var SHARP = { 1: 'do#', 2: 're#', 4: 'fa#', 5: 'sol#', 6: 'la#' };

  /* 墙面局部坐标 → 世界坐标。u 沿墙，v 高度，w 向室内（也就是键面正面） */
  function P3(wall, u, v, w) { return wall === 'A' ? V(u, v, w) : V(w, v, u); }
  function D3(wall, du, dv, dw) { return wall === 'A' ? V(du, dv, dw) : V(dw, dv, du); }

  function pickAt(clientX, clientY) {
    var r = canvas.getBoundingClientRect();
    var ndc = new THREE.Vector2(
      ((clientX - r.left) / r.width) * 2 - 1,
      -((clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    var hits = ray.intersectObjects(wallRoot.children, true);
    for (var i = 0; i < hits.length; i++) {
      if (hits[i].object.userData && hits[i].object.userData.key) return hits[i].object;
    }
    return null;
  }

  function select(obj) {
    if (selObj) { selObj.material = selObj.userData.baseMat; selObj = null; }
    if (selDims) { selRoot.remove(selDims); disposeTree(selDims); selDims = null; }
    var card = document.getElementById('keycard');
    var prm = document.getElementById('params');
    if (!obj) {
      if (dimLeaders) dimLeaders.visible = state.dims;
      if (card) card.hidden = true;
      if (prm) prm.hidden = false;
      applyLegend();
      setTimeout(resize, 30);
      return;
    }
    selObj = obj;
    if (dimLeaders) dimLeaders.visible = false;
    obj.userData.baseMat = obj.material;
    obj.material = HL[obj.userData.key.kind] || G.white;
    selDims = buildKeyDims(obj.userData.key, obj);
    selRoot.add(selDims);
    showKeyCard(obj.userData.key);
    card.hidden = false;
    if (prm) prm.hidden = true;           /* 参数区让位给这块的尺寸 */
    applyLegend();
    setTimeout(resize, 30);
  }

  /* 单块键板的尺寸标注（三维，跟着这块走） */
  function buildKeyDims(k, obj) {
    var g = new THREE.Group();
    var w = k.wall, T = P.wallT * MM, H = P.wallH * MM, pr = P.protrude * MM;
    var baseH = data.baseH * MM, blackH = data.blackH * MM;

    if (k.kind === 'white') {
      var u0 = k.x0 * MM, u1 = k.x1 * MM;
      g.add(dimLinear(P3(w, u0, 0.28, 0), P3(w, u1, 0.28, 0), D3(w, 0, 0, 0.9), fmt(P.whiteW),
        { px: 15, color: 0x0a7a5a }));
      g.add(dimLinear(P3(w, u0, baseH, 0), P3(w, u0, H, 0), D3(w, -0.75, 0, 0.65), fmt(data.whiteH),
        { px: 15, color: 0x0a7a5a, lbOff: 0.02 }));
      g.add(leaderLabel(
        P3(w, (u0 + u1) / 2, baseH + (H - baseH) * 0.42, 0),
        P3(w, (u0 + u1) / 2 + 0.75, baseH + (H - baseH) * 0.75, 1.45),
        '白键板 ' + fmt(P.whiteW - P.gap) + ' × ' + fmt(data.whiteH) + ' × ' + fmt(P.wallT),
        { tc: '#0a7a5a', border: 'rgba(10,122,90,.55)', px: 13 }));
    } else if (k.kind === 'black') {
      var u = k.x * MM, hw = P.blackW * MM / 2;
      g.add(dimLinear(P3(w, u - hw, H - 0.25, pr), P3(w, u + hw, H - 0.25, pr), D3(w, 0, 0, 1.05),
        fmt(P.blackW), { px: 15, color: 0x141414 }));
      g.add(dimLinear(P3(w, u + hw, H - blackH, pr), P3(w, u + hw, H, pr), D3(w, 0.7, 0, 0.75),
        fmt(data.blackH), { px: 15, color: 0x141414, lbOff: 0.02 }));
      g.add(leaderLabel(
        P3(w, u, H - blackH * 0.35, pr),
        P3(w, u + 0.7, H - blackH * 0.15, 1.5),
        '黑键 ' + fmt(P.blackW) + ' × ' + fmt(data.blackH) + ' × ' + fmt(P.protrude),
        { px: 13, tc: '#0a3d8f', border: 'rgba(10,88,200,.55)' }));
    } else {
      var uc = data.spanW * MM * 0.5;
      g.add(dimLinear(P3(w, uc, H - baseH, pr), P3(w, uc, H, pr), D3(w, 1.2, 0, 0.8), fmt(data.baseH),
        { px: 15, color: 0x8a5a00, lbOff: 0.02 }));
      g.add(leaderLabel(
        P3(w, uc, H - baseH * 0.5, pr),
        P3(w, uc + 1.4, 0.75, 1.4),
        '黑踢脚带 通长' + fmt(data.spanW) + ' × ' + fmt(data.baseH) + ' × ' + fmt(P.protrude),
        { px: 13, tc: '#8a5a00', border: 'rgba(255,180,84,.6)' }));
    }
    return g;
  }

  /* 数据卡 */
  function showKeyCard(k) {
    var rows = [], title = '';
    var wallName = k.wall === 'A' ? 'A 面' : 'B 面';
    if (k.kind === 'white') {
      var n = ((k.idx - 1) % 7) + 1;
      title = '白键板 · ' + wallName + ' 第 ' + k.idx + ' 块';
      rows = [
        ['尺寸 宽×高×厚', fmt(P.whiteW - P.gap) + ' × ' + fmt(data.whiteH) + ' × ' + fmt(P.wallT) + ' mm'],
        ['键距 / 拼缝', fmt(P.whiteW) + ' / ' + fmt(P.gap) + ' mm'],
        ['距转角', fmt(k.x0) + ' – ' + fmt(k.x1) + ' mm'],
        ['离地', fmt(data.baseH) + ' – ' + fmt(P.wallH) + ' mm'],
        ['分组 / 音名', '第 ' + Math.ceil(k.idx / 7) + ' 组 · 第 ' + n + ' 键（' + NOTE[n - 1] + '）' +
          (n === 1 ? ' · 右侧有黑键' : (n === 7 ? ' · 右侧无黑键' : ''))]
      ];
    } else if (k.kind === 'black') {
      var m = k.m, gi = Math.ceil(k.after / 7);
      title = '黑键条 · ' + wallName + (SHARP[m] ? '（' + SHARP[m] + '）' : '');
      rows = [
        ['尺寸 宽×高×凸', fmt(P.blackW) + ' × ' + fmt(data.blackH) + ' × ' + fmt(P.protrude) + ' mm'],
        ['中心距转角', fmt(k.x) + ' mm'],
        ['离地（下沿）', fmt(data.blackBottom) + ' mm'],
        ['落在接缝', '第 ' + k.after + ' 块白键右侧（' + NOTE[((k.after - 1) % 7)] + ' / ' + (SHARP[m] || '') + '）'],
        ['分组', '第 ' + gi + ' 组 · 第 ' + (PW.BLACK_AFTER.indexOf(m) + 1) + ' 个黑键']
      ];
    } else {
      title = '黑踢脚带 · ' + wallName;
      rows = [
        ['通长', fmt(data.spanW) + ' mm'],
        ['高度 / 凸出', fmt(data.baseH) + ' / ' + fmt(P.protrude) + ' mm'],
        ['离地', '0 – ' + fmt(data.baseH) + ' mm']
      ];
    }
    document.getElementById('kc-title').textContent = title;
    var html = '';
    rows.forEach(function (r, i) {
      html += '<tr' + (i < 2 ? ' class="hl"' : '') + '><td>' + r[0] + '</td><td>' + r[1] + '</td></tr>';
    });
    document.getElementById('kc-body').innerHTML = html;
  }

  /* 镜头定位到选中的这块 */
  function focusSelected() {
    if (!selObj) return;
    var b = new THREE.Box3().setFromObject(selObj);
    var c = b.getCenter(new THREE.Vector3());
    var k = selObj.userData.key;
    var size = Math.max(b.max.y - b.min.y, 0.55);
    var d = Math.max(3.6, size * 2.8);                      /* 留出上下文，不要贴脸 */
    var n = k.wall === 'A' ? V(0, 0, 1) : V(1, 0, 0);       /* 墙面法线朝室内 */
    var t = k.wall === 'A' ? V(1, 0, 0) : V(0, 0, 1);       /* 沿墙方向 */
    /* 目标点居中，不要把这块顶得太高 */
    var tgt = c.clone();
    var pos = c.clone().addScaledVector(n, d).addScaledVector(t, d * 0.32).add(V(0, 0.18, 0));
    animTo(pos, tgt, UP);
  }

  /* ---------------- 相机控制 ---------------- */
  var camState = { tgt: new THREE.Vector3(3.4, 0.9, 3.4), r: 24, theta: Math.PI / 4, phi: 1.16, up: new THREE.Vector3(0, 1, 0) };
  var anim = null;

  function applyCam() {
    var sp = Math.sin(camState.phi), cp = Math.cos(camState.phi);
    camera.position.set(
      camState.tgt.x + camState.r * sp * Math.sin(camState.theta),
      camState.tgt.y + camState.r * cp,
      camState.tgt.z + camState.r * sp * Math.cos(camState.theta)
    );
    camera.up.copy(camState.up);
    camera.lookAt(camState.tgt);
  }

  /* 把镜头平移到指定位置/目标（带缓动） */
  function animTo(pos, tgt, up, instant) {
    up = up || UP;
    var d = pos.clone().sub(tgt);
    var r = Math.max(0.6, d.length());
    var phi = Math.acos(Math.max(-1, Math.min(1, d.y / r)));
    var theta = Math.atan2(d.x, d.z);
    var to = { tgt: tgt.clone(), r: r, theta: theta, phi: phi, up: up.clone() };
    if (instant) {
      camState.tgt.copy(to.tgt); camState.r = to.r; camState.theta = to.theta;
      camState.phi = to.phi; camState.up.copy(to.up); applyCam(); return;
    }
    while (to.theta - camState.theta > Math.PI) to.theta -= Math.PI * 2;
    while (to.theta - camState.theta < -Math.PI) to.theta += Math.PI * 2;
    anim = {
      t0: performance.now(), dur: 560, from: {
        tgt: camState.tgt.clone(), r: camState.r, theta: camState.theta, phi: camState.phi,
        up: camState.up.clone()
      }, to: to
    };
  }

  function setView(name, instant) {
    if (!name) return;
    curView = name;
    userMoved = false;
    var v = viewPose(name);
    animTo(v.pos, v.tgt, v.up, instant);
  }

  function tickAnim(now) {
    if (!anim) return;
    var t = Math.min(1, (now - anim.t0) / anim.dur);
    var e = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;   /* easeInOutCubic */
    var f = anim.from, o = anim.to;
    camState.tgt.lerpVectors(f.tgt, o.tgt, e);
    camState.r = f.r + (o.r - f.r) * e;
    camState.theta = f.theta + (o.theta - f.theta) * e;
    camState.phi = f.phi + (o.phi - f.phi) * e;
    camState.up.lerpVectors(f.up, o.up, e);
    applyCam();
    if (t >= 1) anim = null;
  }

  function bindControls() {
    var pointers = new Map(), lastDist = 0, lastMid = null, multi = false;
    canvas.addEventListener('pointerdown', function (e) {
      canvas.setPointerCapture(e.pointerId);
      pointers.set(e.pointerId, { x: e.clientX, y: e.clientY, sx: e.clientX, sy: e.clientY, t0: Date.now(), moved: 0 });
      anim = null;
      if (pointers.size >= 2) {
        multi = true;
        var p = Array.from(pointers.values());
        lastDist = Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y);
        lastMid = { x: (p[0].x + p[1].x) / 2, y: (p[0].y + p[1].y) / 2 };
      } else {
        multi = false;
      }
    });
    canvas.addEventListener('pointermove', function (e) {
      var prev = pointers.get(e.pointerId); if (!prev) return;
      var dx = e.clientX - prev.x, dy = e.clientY - prev.y;
      prev.x = e.clientX; prev.y = e.clientY;
      prev.moved += Math.abs(dx) + Math.abs(dy);
      if (prev.moved > 6) userMoved = true;
      if (pointers.size === 1) {
        if (prev.moved > 4) {
          camState.theta -= dx * 0.006;
          camState.phi = Math.max(0.07, Math.min(1.62, camState.phi - dy * 0.006));
        }
      } else if (pointers.size === 2) {
        var p = Array.from(pointers.values());
        var dist = Math.hypot(p[0].x - p[1].x, p[0].y - p[1].y);
        var mid = { x: (p[0].x + p[1].x) / 2, y: (p[0].y + p[1].y) / 2 };
        if (lastDist > 0) camState.r = Math.max(0.8, Math.min(120, camState.r * lastDist / Math.max(1, dist)));
        if (lastMid) {
          var f = camState.r * 0.0016;
          var right = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 0);
          var up = new THREE.Vector3().setFromMatrixColumn(camera.matrix, 1);
          camState.tgt.addScaledVector(right, -(mid.x - lastMid.x) * f);
          camState.tgt.addScaledVector(up, (mid.y - lastMid.y) * f);
        }
        lastDist = dist; lastMid = mid;
      }
      applyCam();
    });
    function up(e) {
      var p = pointers.get(e.pointerId);
      pointers.delete(e.pointerId);
      if (pointers.size < 2) { lastDist = 0; lastMid = null; }
      /* 轻点（没怎么动、时间很短、非双指）= 选中这块键板 */
      if (p && !multi && p.moved < 12 && Date.now() - p.t0 < 450) {
        select(pickAt(e.clientX, e.clientY));
      }
    }
    canvas.addEventListener('pointerup', up);
    canvas.addEventListener('pointercancel', function (e) {
      pointers.delete(e.pointerId);
      if (pointers.size < 2) { lastDist = 0; lastMid = null; }
    });
    canvas.addEventListener('wheel', function (e) {
      e.preventDefault();
      userMoved = true;
      camState.r = Math.max(0.8, Math.min(120, camState.r * Math.exp(e.deltaY * 0.0012)));
      applyCam();
    }, { passive: false });
    /* 双击 = 镜头定位到点中的那块 */
    canvas.addEventListener('dblclick', function (e) {
      select(pickAt(e.clientX, e.clientY));
      focusSelected();
    });
  }

  /* ---------------- 主循环 ---------------- */
  var last = 0, frames = 0;
  function loop(now) {
    requestAnimationFrame(loop);
    tickAnim(now);
    if (state.spin && !anim && pointersIdle()) { camState.theta += 0.0035; applyCam(); }
    /* 镜头贴得很近时自动把人形参考藏起来，不挡画面 */
    if (figure) figure.visible = state.scale && camera.position.distanceTo(figure.position) > 4.5;
    updateLabelScale();
    renderer.render(scene, camera);
  }
  function pointersIdle() { return true; }

  /* ---------------- 全量刷新 ---------------- */
  var pending = null;
  function updateAll(now) {
    data = PW.layout(P);
    rebuildWalls();
    rebuildDims();
    updateLegend();
    updateSpec();
    drawSheets();
    fitViewBox();
  }
  function schedule() {
    if (pending) return;
    pending = requestAnimationFrame(function () { pending = null; updateAll(); });
  }
  function fitViewBox() {
    /* 墙长/墙高变了，把人形参考摆好；当前视角若是「适配类」视角则重新套用 */
    figure.visible = state.scale;
    figure.position.set(data.spanW * MM * 0.26, 0, 1.35);
    if (!userMoved && (curView === '全景' || curView === '正视' || curView === '俯视')) setView(curView, true);
  }

  /* ---------------- 图纸 ---------------- */
  function drawSheets() {
    window.Draw2D.drawAll(data);
    var el = document.getElementById('dimtable');
    if (el) el.innerHTML = window.Draw2D.dimTable(data);
  }

  function applyLegend() {
    var el = document.getElementById('legend');
    if (el) el.hidden = !state.legend;
    var btn = document.querySelector('[data-toggle="legend"]');
    if (btn) btn.classList.toggle('on', !!state.legend);
  }

  /* ---------------- 侧栏 UI ---------------- */
  function updateLegend() {
    document.getElementById('legend').innerHTML =
      '墙长 <b>' + fmt(data.spanW) + '</b> × 2 面 ｜ 墙高 <b>' + fmt(P.wallH) + '</b> mm<br>' +
      '总展开长 <i>' + fmt(data.totalLen) + '</i> mm ＝ <i>' + (data.totalLen / 1000).toFixed(1) + '</i> m<br>' +
      '白键 <b>' + fmt(P.whiteW) + '</b> × ' + data.nWhiteTotal + ' 块 ｜ 黑键 <span class="k">' + fmt(P.blackW) + '×' + fmt(data.blackH) + '</span> × ' + data.nBlackTotal + ' 块<br>' +
      '踢脚带 <span class="k">' + fmt(data.baseH) + '</span> ｜ 转角 <b>90°</b><br>' +
      '<span style="color:#9dbaff">👆 点任意一块键板 / 黑键 / 踢脚带 → 看这块的尺寸</span>';
    document.getElementById('subtitle').textContent =
      'L 型转角墙 ' + fmt(data.spanW) + ' × ' + fmt(P.wallH) + ' mm × 2 面 ＝ ' + fmt(data.totalLen) + ' mm';
  }

  function updateSpec() {
    var s = '';
    s += '<h2>一、项目尺寸（图纸值）</h2><table>' +
      row('墙身形制', '两面墙 90° 相接，L 形') +
      row('单面墙长 × 高', fmt(data.spanW) + ' × ' + fmt(P.wallH) + ' mm') +
      row('两面墙总展开长', fmt(data.totalLen) + ' mm（' + (data.totalLen / 1000).toFixed(1) + ' m）') +
      row('总立面面积', PW.fmt2(data.totalFace) + ' m²') +
      row('墙体（面板）厚度', fmt(P.wallT) + ' mm') +
      '</table>';
    s += '<h2>二、图案排布</h2>' +
      '<p>白键按 <code>' + fmt(P.whiteW) + ' mm</code> 等宽排布，每 <b>7 个白键为一组</b>（do re mi fa sol la si，一组 ' + fmt(data.octaveW) + ' mm）；' +
      '黑键落在每组第 <b>1、2、4、5、6</b> 个白键的右侧接缝上，即「2 白键组 + 3 白键组」的经典键盘分群。</p>' +
      '<table>' +
      row('白键宽（分块宽）', fmt(P.whiteW) + ' mm') +
      row('黑键宽', fmt(P.blackW) + ' mm（白键的 ' + (data.blackRatioW * 100).toFixed(1) + '%）') +
      row('黑键高（自墙顶下量）', fmt(data.blackH) + ' mm（墙高的 ' + (data.blackRatioH * 100).toFixed(1) + '%）') +
      row('黑键下沿离地', fmt(data.blackBottom) + ' mm') +
      row('底部黑踢脚带', fmt(data.baseH) + ' mm') +
      row('白键板净高', fmt(data.whiteH) + ' mm') +
      row('键板拼缝 / 黑键凸出', fmt(P.gap) + ' mm / ' + fmt(P.protrude) + ' mm') +
      row('转角做法', P.mirror ? '两面墙各自从整键起排（转角左右对称）' : '图案跨转角连续（相位偏移 ' + (data.nWhite % 7) + ' 键）') +
      '</table>';
    s += '<h2>三、分块与数量</h2><table>' +
      row('白键板', data.nWhiteTotal + ' 块 · 每块 ' + fmt(P.whiteW - P.gap) + '×' + fmt(data.whiteH) + '×' + fmt(P.wallT) + ' mm') +
      row('黑键条', data.nBlackTotal + ' 块 · 每块 ' + fmt(P.blackW) + '×' + fmt(data.blackH) + '×' + fmt(P.protrude) + ' mm（贴面）') +
      row('黑踢脚带', '2 条 · ' + fmt(data.spanW) + '×' + fmt(data.baseH) + '×' + fmt(P.protrude) + ' mm') +
      row('基层背板', '2 张 · ' + fmt(data.spanW) + '×' + fmt(P.wallH) + ' mm（深色，封缝）') +
      '</table>';
    s += '<h2>四、面积与油漆估算</h2><table>' +
      row('白色面漆面积', PW.fmt2(data.whiteArea) + ' m²') +
      row('黑色面漆面积', PW.fmt2(data.blackArea) + ' m²（含踢脚带）') +
      row('白色面漆用量', data.paintWhite.toFixed(1) + ' L（0.12 L/m²·遍 × 2 遍 + 10% 损耗）') +
      row('黑色面漆用量', data.paintBlack.toFixed(1) + ' L（同上）') +
      '</table>';
    s += '<h2>五、施工要点</h2><p>' + +
      '<span class="tagline">1 放线</span>先钉转角基准，自转角起每 ' + fmt(P.whiteW) + ' mm 弹一条竖向墨线；每 7 键复尺一次（累积误差 ≤ 3 mm）。' +
      '<span class="tagline">2 留缝</span>白键板之间留 ' + fmt(P.gap) + ' mm 缝，缝后必须是深色背板，否则缝里会透出亮色。' +
      '<span class="tagline">3 转角</span>转角先立角柱 / 双面收口条，两面墙的键面在转角处错开一个板厚，避免两块板打架。' +
      '<span class="tagline">4 黑键</span>黑键用 ' + fmt(P.protrude) + ' mm 厚板（或薄板加垫条）贴在白键面上，凸出 ' + fmt(P.protrude) + ' mm，投影会自己形成立体感。' +
      '<span class="tagline">5 表面</span>户外用外墙乳胶漆 / 氟碳漆，白色两遍、黑色两遍；黑键建议做哑光，避免反光发灰。' +
      '<span class="tagline">6 排水</span>踢脚带下沿离地 ' + fmt(P.baseH) + ' mm，底部留 10 mm 漏水缝或打密封胶，防雨水上返。' +
      '</p><div class="warnbox">三维页里<b>点任意一块键板 / 黑键 / 踢脚带</b>，会高亮这块并弹出它的尺寸（宽×高×厚、距转角、离地、所在分组）；<b>双击</b>或点数据卡上的「镜头定位」可把镜头拉到这块。全部数字都可以在下面「图案参数」里拖动改，三维模型、四张图纸和这张清单会一起重算。</div>';
    document.getElementById('spec').innerHTML = s;
    function row(a, b) { return '<tr><th>' + a + '</th><td class="n">' + b + '</td></tr>'; }
  }

  function buildParams() {
    var host = document.getElementById('pgrid');
    host.innerHTML = '';
    PARAM_DEFS.forEach(function (d) {
      var row = document.createElement('div');
      row.className = 'prow';
      if (d.toggle) {
        var b = document.createElement('button');
        b.className = 'chip toggle' + (P[d.k] ? ' on' : '');
        b.textContent = d.label + '：' + (P[d.k] ? '开' : '关');
        b.onclick = function () {
          P[d.k] = P[d.k] ? 0 : 1;
          b.className = 'chip toggle' + (P[d.k] ? ' on' : '');
          b.textContent = d.label + '：' + (P[d.k] ? '开' : '关');
          schedule();
        };
        row.appendChild(b);
        host.appendChild(row);
        return;
      }
      row.innerHTML = '<label>' + d.label + '</label><input type="range" min="' + d.min + '" max="' + d.max +
        '" step="' + d.step + '" value="' + P[d.k] + '"><output>' + P[d.k] + ' mm</output>';
      var inp = row.querySelector('input'), out = row.querySelector('output');
      inp.addEventListener('input', function () {
        P[d.k] = +inp.value;
        out.textContent = inp.value + ' mm';
        if (d.k === 'whiteW' && P.blackW > P.whiteW) { P.blackW = Math.round(P.whiteW * 0.59); }
        schedule();
      });
      host.appendChild(row);
    });
  }

  /* ---------------- 存图 ---------------- */
  function toast(msg) {
    var t = document.getElementById('toast');
    t.textContent = msg; t.classList.add('on');
    clearTimeout(toast._t);
    toast._t = setTimeout(function () { t.classList.remove('on'); }, 2200);
  }
  function savePng(name, url) {
    if (window.AndroidSAVE && window.AndroidSAVE.savePng) {
      try { window.AndroidSAVE.savePng(name, url); } catch (e) { toast('保存失败：' + e); }
    } else {
      var a = document.createElement('a');
      a.href = url; a.download = name + '.png'; a.click();
      toast('已导出 ' + name + '.png');
    }
  }

  /* ---------------- 事件绑定 ---------------- */
  function bindUI() {
    document.querySelectorAll('.tab').forEach(function (b) {
      b.onclick = function () {
        document.querySelectorAll('.tab').forEach(function (x) { x.classList.remove('on'); });
        document.querySelectorAll('.tabpane').forEach(function (x) { x.classList.remove('on'); });
        b.classList.add('on');
        document.getElementById('tab-' + b.dataset.tab).classList.add('on');
        if (b.dataset.tab !== 'view3d') select(null);   /* 离开 3D 页就取消选中，参数区回来 */
        if (b.dataset.tab === 'view3d') { resize(); }
        if (b.dataset.tab === 'draw') { drawSheets(); }
      };
    });
    document.querySelectorAll('[data-view]').forEach(function (b) {
      b.onclick = function () {
        document.querySelectorAll('[data-view]').forEach(function (x) { x.classList.remove('on'); });
        b.classList.add('on');
        setView(b.dataset.view);
      };
    });
    document.querySelectorAll('[data-toggle]').forEach(function (b) {
      b.onclick = function () {
        var k = b.dataset.toggle;
        state[k] = !state[k];
        b.classList.toggle('on', state[k]);
        if (k === 'dims' && dimRoot) dimRoot.visible = state.dims;
        if (k === 'scale' && figure) figure.visible = state.scale;
        if (k === 'legend') applyLegend();
      };
    });
    document.querySelectorAll('[data-sheet]').forEach(function (b) {
      if (b.classList.contains('chip')) {
        b.onclick = function () {
          var k = b.dataset.sheet;
          document.querySelectorAll('.hud [data-sheet]').forEach(function (x) { x.classList.remove('on'); });
          b.classList.add('on');
          document.querySelectorAll('#sheets .sheet').forEach(function (f) {
            f.hidden = !(k === 'all' || f.dataset.sheet === k);
          });
        };
      }
    });
    document.getElementById('btn-reset').onclick = function () {
      P = Object.assign({}, PW.DEFAULTS);
      buildParams(); updateAll();
      toast('已还原到图纸尺寸');
    };
    document.getElementById('btn-fold').onclick = function () {
      var box = document.getElementById('params');
      var folded = box.classList.toggle('folded');
      this.textContent = folded ? '展开' : '收起';
      setTimeout(resize, 30);
    };
    document.getElementById('kc-x').onclick = function () { select(null); };
    document.getElementById('kc-zoom').onclick = function () { focusSelected(); };
    document.getElementById('btn-shot3d').onclick = function () {
      renderer.render(scene, camera);
      savePng('钢琴墙_3D_' + stamp(), canvas.toDataURL('image/png'));
      toast('已保存到相册 Pictures/PianoWall');
    };
    document.getElementById('btn-shotdw').onclick = function () {
      var on = document.querySelector('.hud [data-sheet].on');
      var k = on ? on.dataset.sheet : 'elev';
      if (k === 'all' || k === 'table') k = 'elev';
      savePng('钢琴墙_' + k + '_' + stamp(), window.Draw2D.exportPng(k, data));
      toast('图纸已保存到相册 Pictures/PianoWall');
    };
  }
  function stamp() {
    var d = new Date(), p = function (n) { return (n < 10 ? '0' : '') + n; };
    return d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) + '_' + p(d.getHours()) + p(d.getMinutes());
  }

  /* ---------------- 启动 ---------------- */
  /* 支持 #draw / #spec 直接打开对应页（也方便外部唤起与截图） */
  function applyHash() {
    var tab = (location.hash || '').replace('#', '');
    if (['view3d', 'draw', 'spec'].indexOf(tab) < 0) return;
    document.querySelectorAll('.tab').forEach(function (x) {
      var on = x.dataset.tab === tab;
      x.classList.toggle('on', on);
      document.getElementById('tab-' + x.dataset.tab).classList.toggle('on', on);
    });
    if (tab === 'draw') drawSheets();
  }

  function boot() {
    try { initGL(); } catch (e) {
      document.getElementById('legend').innerHTML = 'WebGL 初始化失败：' + e;
      return;
    }
    bindControls(); bindUI(); buildParams();
    resize();
    setView('全景', true);
    updateAll();
    applyLegend();
    applyHash();
    window.__pw = { scene: scene, camera: camera, renderer: renderer, state: state, data: function () { return data; }, P: P };
    requestAnimationFrame(loop);
    setTimeout(function () { resize(); applyHash(); }, 260);
    setTimeout(function () { toast('👆 点任意一块键板 / 黑键，可看这块的尺寸'); }, 1400);
  }
  if (document.readyState === 'complete' || document.readyState === 'interactive') setTimeout(boot, 0);
  else window.addEventListener('DOMContentLoaded', boot);
})();
