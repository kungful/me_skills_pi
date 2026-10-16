// ============================================================================
// app.js —— 太阳网控制器 App 前端
// 所有请求都走 API.*（transport.js → 原生桥 → WiFi/HTTP 或 BLE），
// 命令格式与固件 Controller::handleJson() 完全一致。
// ============================================================================
'use strict';

const $ = (id) => document.getElementById(id);
let S = null;              // 最近一次 state
let lastLog = 0;
let cfgEdit = {};
let cfgDirty = false;
let online = false;

const pct = (raw) => (raw / 4095 * 100);
const dirLabel = { cw: 'CW 追日', ccw: 'CCW 回程', stop: '停止' };

function toast(msg, bad) {
  const el = document.createElement('div');
  el.className = 'toast' + (bad ? ' bad' : '');
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 2600);
}

async function cmd(obj, quiet) {
  try {
    const j = await API.post('/api/cmd', obj);
    if (!j.ok && !quiet) toast('失败: ' + (j.error || '?'), true);
    if (j.ok && !quiet && obj.cmd !== 'state') toast('已执行: ' + obj.cmd);
    return j;
  } catch (e) {
    if (!quiet) toast('错误: ' + e.message, true);
    return { ok: false, error: String(e.message || e) };
  }
}

// ---------------------------------------------------------------- 连接
function setConnChips() {
  const st = API.status;
  const m = st.mode;
  $('connChip').textContent = m === 'http' ? ('WiFi ' + (st.host || ''))
    : m === 'ble' ? ((st.name || 'BLE') + (st.bleConnected ? ' 已连' : ' 未连'))
    : '未连接';
  $('connChip').className = 'chip ' + (online ? 'ok' : 'err');

  $('btnModeWifi').className = m === 'http' ? 'chip act' : 'chip';
  $('btnModeBle').className = m === 'ble' ? 'chip act' : 'chip';
  $('wifiBox').style.display = m === 'ble' ? 'none' : '';
  $('bleBox').style.display = m === 'ble' ? '' : 'none';
}

async function bindConn() {
  $('btnModeWifi').onclick = () => {
    $('wifiBox').style.display = '';
    $('bleBox').style.display = 'none';
    $('hostInput').value = API.host();
    $('connHelp').textContent = '手机先连设备热点（默认 pcbsun-XXXX / pcbsun1234），再点「连接」。';
  };
  $('btnModeBle').onclick = async () => {
    $('wifiBox').style.display = 'none';
    $('bleBox').style.display = '';
    $('connHelp').textContent = '蓝牙不需要切 WiFi：直连设备的 BLE 广播名 pcbsun。';
    await API.status();
    setConnChips();
    if (!API.status.blePerm) toast('需要蓝牙权限，点「扫描设备」会请求', true);
  };

  $('btnConnect').onclick = async () => {
    $('btnConnect').disabled = true;
    try {
      await API.connectWifi($('hostInput').value);
      const j = await API.get('/api/state');
      online = true;
      render(j);
      toast('已连上 ' + API.host());
      loadConfig(); loadLog();
    } catch (e) {
      online = false;
      toast(e.message, true);
    } finally {
      $('btnConnect').disabled = false;
      setConnChips();
    }
  };

  $('btnScan').onclick = async () => {
    const box = $('devList');
    box.innerHTML = '<p class="hint">扫描中…（6 秒，设备要先上电）</p>';
    try {
      const list = await API.scanBle(6000);
      if (!list.length) { box.innerHTML = '<p class="hint">没扫到设备。确认板子已上电、BLE 在广播，且手机蓝牙开着。</p>'; return; }
      box.innerHTML = '';
      list.forEach((d) => {
        const row = document.createElement('div');
        row.className = 'dev' + (d.ours ? ' mine' : '');
        row.innerHTML = '<div><b>' + esc(d.name) + '</b><br><small>' + esc(d.id) +
          ' · ' + d.rssi + ' dBm' + (d.ours ? ' · 本设备' : '') + '</small></div>';
        const b = document.createElement('button');
        b.textContent = '连接';
        b.onclick = async () => {
          b.disabled = true; b.textContent = '连接中…';
          try {
            await API.connectBle(d);
            online = true;
            const j = await API.get('/api/state');
            render(j);
            toast('BLE 已连接');
            loadConfig();
          } catch (e) {
            b.disabled = false; b.textContent = '连接';
            toast(e.message, true);
          }
          setConnChips();
        };
        row.appendChild(b);
        box.appendChild(row);
      });
    } catch (e) {
      box.innerHTML = '<p class="hint">' + esc(e.message) + '</p>';
      if (/权限/.test(e.message)) API.askBlePermission();
    }
    setConnChips();
  };

  $('btnDisc').onclick = async () => {
    await API.disconnect();
    online = false;
    setConnChips();
    toast('已断开');
  };

  API.onEvent(() => setConnChips());
  await API.status();
  $('hostInput').value = API.host();
  setConnChips();

  // App 里如果上次连的是 WiFi，进来直接试一次
  if (API.hasBridge) {
    API.connectWifi(API.host()).then(() => API.get('/api/state')).then((j) => {
      online = true; render(j); loadConfig(); loadLog(); setConnChips();
    }).catch(() => { online = false; setConnChips(); });
  }
}

function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// ---------------------------------------------------------------- 渲染
function render(s) {
  S = s;
  online = true;
  $('linkDot').classList.add('on');

  $('modeChip').textContent = s.mode === 'auto' ? '自动跟踪' : '手动';
  $('modeChip').className = 'chip ' + (s.mode === 'auto' ? 'ok' : '');

  const fault = s.fault || 'none';
  $('faultChip').textContent = s.estop ? '急停锁存' : (fault === 'none' ? '无故障' : '故障:' + fault);
  $('faultChip').className = 'chip ' + (s.estop || fault !== 'none' ? 'err' : 'ok');
  if (s.night) $('faultChip').textContent += ' · 夜间';

  const n = s.net || {};
  $('netChip').textContent = n.mode === 'off' ? 'WiFi 关'
    : (n.ip || '-') + (n.staIp && n.staIp !== '-' ? ' / LAN ' + n.staIp : '');
  $('netChip').className = 'chip ' + (n.http ? 'ok' : 'warn');
  $('netChip').style.display = API.status.mode === 'ble' ? 'none' : '';

  $('pinLightTag').textContent = 'IO' + s.pins.light;
  $('pinPotTag').textContent = 'IO' + s.pins.pot;
  $('barLight').style.width = pct(s.light.f) + '%';
  $('valLight').textContent = s.light.f + ' (' + s.light.pct + '%)';
  $('barPot').style.width = pct(s.pot.f) + '%';
  $('valPot').textContent = s.pot.f + ' (' + s.pot.pct + '%)';
  $('thDown').style.left = pct(s.th.down) + '%';
  $('thUp').style.left = pct(s.th.up) + '%';
  $('valTh').textContent = s.th.up + ' / ' + s.th.down + ' (hyst ' + s.th.hyst + ')';
  $('valRain').textContent = s.rain.raw + ' · ' + (s.rain.wet ? '有雨' : '无雨');
  $('valWind').textContent = s.wind.active ? '大风' : '无风';
  $('valNight').textContent = s.night ? '夜间(停追)' : '白天';

  const m = s.motor;
  $('valMotor').textContent = m.run ? (dirLabel[m.dir] || m.dir) + ' ' + m.duty + '%' : (dirLabel[m.dir] || '停止');
  $('valSource').textContent = m.source;
  $('valRun').textContent = m.runMinThisHour + ' min/h';
  $('valJogs').textContent = m.jogs;
  $('btnAuto').textContent = s.mode === 'auto' ? '切到手动' : '切到自动跟踪';
  $('btnAuto').className = 'wide ' + (s.mode === 'auto' ? '' : 'auto');
  $('btnEstop').disabled = !!s.estop;

  const L = s.limits || { a: false, b: false, stowed: false, en: 1, travel: 'none' };
  $('valLimits').textContent = (L.a ? 'A 触发' : 'A—') + ' / ' + (L.b ? 'B 触发' : 'B—') + (L.en ? '' : ' (已旁路)');
  $('valStow').textContent = L.stowed ? '已收拢' : (L.travel && L.travel !== 'none'
    ? ('走向 ' + String(L.travel).toUpperCase() + ' 限位…') : '未收拢');
  $('valEstopHw').textContent = s.estopHw ? '触发(已断电)' : '正常';
  $('valModeSel').textContent = s.modeSel === 'grace' ? '上电宽限…'
    : (s.modeSel === 'manual' ? '手动位' : '自动位');
  $('valPower').textContent = m.power ? '带电(IO' + s.pins.motEn + ')' : '断电';
  $('valImon').textContent = (s.imon && s.imon.en) ? (s.imon.ma + ' mA') : '未启用';
  $('btnDeploy').disabled = !L.en;
  $('btnStow').disabled = !L.en;

  $('btn3').textContent = s.btn.mode ? '按下' : '—';
  $('btn4').textContent = s.btn.cw ? '按下' : '—';
  $('btn5').textContent = s.btn.ccw ? '按下' : '—';
  $('btnBoot').textContent = s.btn.boot ? '按下' : '—';

  if (s.selftest && s.selftest.items) renderSelftest(s.selftest);

  $('fwVer').textContent = s.ver;
  $('uptime').textContent = s.up + 's';
  $('bleInfo').textContent = (s.ble && s.ble.conn) ? ('已连接 ×' + s.ble.clients) : ('广播 ' + (s.ble ? s.ble.adv : '-'));
}

function renderSelftest(r) {
  const el = $('selftestOut');
  if (!r || !r.items) { el.textContent = '自检失败：' + ((r && r.error) || '无响应'); return; }
  const lines = ['结果：' + (r.ok ? '通过' : '有失败项') + '　' + r.pass + ' 通过 / ' + r.warn + ' 警告 / ' + r.fail + ' 失败', ''];
  r.items.forEach((it) => { lines.push((it.ok ? '✔ ' : '✘ ') + String(it.k).padEnd(10) + it.t); });
  el.textContent = lines.join('\n');
}

async function poll() {
  if (API.status.mode === 'none') return;
  try {
    const j = await API.get('/api/state');
    render(j);
  } catch (e) {
    online = false;
    $('linkDot').classList.remove('on');
    setConnChips();
  }
  if (Date.now() - lastLog > 3000) { lastLog = Date.now(); loadLog(); }
}

async function loadLog() {
  if (API.status.mode === 'ble') { $('log').textContent = '（BLE 通道没有日志接口；连 WiFi 通道或串口 CLI 看 log）'; return; }
  try {
    const j = await API.get('/api/log?n=14');
    $('log').textContent = (j.log || []).slice().reverse()
      .map((e) => `${(e.ms / 1000).toFixed(1)}s [${['INF', 'WRN', 'ERR'][e.lvl] || '??'}] ${e.t}`).join('\n');
  } catch (e) { /* 忽略 */ }
}

// ---------------------------------------------------------------- 交互
function bindMotorButtons() {
  const duty = () => +$('duty').value;
  const ms = () => +$('jogMs').value;

  $('duty').oninput = () => $('dutyVal').textContent = $('duty').value + '%';
  $('jogMs').oninput = () => $('jogVal').textContent = $('jogMs').value + 'ms';

  const press = (el, dir) => {
    const fire = () => cmd({ cmd: 'jog', dir: dir, duty: duty(), ms: ms() }, true);
    let timer = null;
    const down = (ev) => {
      ev.preventDefault();
      fire();
      timer = setInterval(fire, 700);
    };
    const up = () => { clearInterval(timer); timer = null; cmd({ cmd: 'stop' }, true); };
    el.addEventListener('touchstart', down, { passive: false });
    el.addEventListener('touchend', up);
    el.addEventListener('touchcancel', up);
    el.addEventListener('mousedown', down);
    el.addEventListener('mouseup', up);
    el.addEventListener('mouseleave', up);
  };
  press($('btnCW'), 'cw');
  press($('btnCCW'), 'ccw');

  $('btnStop').onclick = () => cmd({ cmd: 'stop' });
  $('btnEstop').onclick = () => { if (confirm('急停？电机立刻停并锁存，需手动解除。')) cmd({ cmd: 'estop' }); };
  $('btnClear').onclick = () => cmd({ cmd: 'clear' });
  $('btnAuto').onclick = () => cmd({ cmd: 'mode', value: (S && S.mode === 'auto') ? 'manual' : 'auto' });
  $('btnDeploy').onclick = () => cmd({ cmd: 'deploy' });
  $('btnStow').onclick = () => cmd({ cmd: 'stow' });
  $('btnSelftest').onclick = async () => {
    $('selftestOut').textContent = '自检中…';
    const r = await cmd({ cmd: 'selftest' }, true);
    renderSelftest(r);
  };
}

function bindPanelSim() {
  document.querySelectorAll('[data-press]').forEach((el) => {
    el.onclick = () => {
      if (el.dataset.press === 'mode') cmd({ cmd: 'mode', value: (S && S.mode === 'auto') ? 'manual' : 'auto' });
      else cmd({ cmd: 'clear' });
    };
  });
  document.querySelectorAll('[data-hold]').forEach((el) => {
    const dir = el.dataset.hold;
    const fire = () => cmd({ cmd: 'jog', dir: dir, duty: 50, ms: 800 }, true);
    el.addEventListener('touchstart', (e) => { e.preventDefault(); fire(); el._h = setInterval(fire, 500); }, { passive: false });
    ['touchend', 'touchcancel', 'mouseup', 'mouseleave'].forEach((ev) =>
      el.addEventListener(ev, () => { clearInterval(el._h); cmd({ cmd: 'stop' }, true); }));
  });
}

function bindLeds() {
  const send = () => cmd({ cmd: 'led', run: +$('ledRun').value, motor: +$('ledMotor').value });
  $('ledRun').onchange = send;
  $('ledMotor').onchange = send;
}

function bindScanMap() {
  $('btnScanIo').onclick = async () => {
    if (API.status.mode === 'ble') { $('scanOut').textContent = '（BLE 通道没有 GPIO 探针；连 WiFi 通道用）'; return; }
    $('scanOut').textContent = '扫描中…';
    try {
      const j = await API.get('/api/scan?gpio=' + $('scanGpio').value + '&ms=120');
      $('scanOut').textContent = JSON.stringify(j, null, 1);
    } catch (e) { $('scanOut').textContent = 'ERR ' + e.message; }
  };
  $('roleSel').onchange = () => {
    const map = { light: S ? S.pins.light : 5, rain: S ? S.pins.rain : 6, wind: S ? S.pins.wind : 8, pot: S ? S.pins.pot : 4 };
    $('roleGpio').value = map[$('roleSel').value];
    $('scanGpio').value = map[$('roleSel').value];
  };
  $('btnMap').onclick = async () => {
    const j = await cmd({ cmd: 'map', role: $('roleSel').value, gpio: +$('roleGpio').value });
    if (j.ok) { $('scanOut').textContent = '已改绑 ' + $('roleSel').value + ' → IO' + $('roleGpio').value; poll(); }
  };
}

// ---------------------------------------------------------------- 配置表单
const CFG_FIELDS = [
  ['autoDutyPct', '自动占空 %'], ['jogDefaultMs', '点动默认 ms'], ['jogMinMs', '点动最短 ms'],
  ['jogMaxMs', '点动上限 ms'], ['minDwellMs', '动作最小间隔 ms'], ['runBudgetSecHr', '每小时运行预算 s'],
  ['thUp', '追日上限(-1=跟电位器)'], ['thDown', '回程下限(-1=跟电位器)'], ['thHyst', '迟滞 raw'],
  ['nightLight', '夜晚阈值 raw'], ['nightHoldMs', '夜晚保持 ms'],
  ['rainThreshold', '雨判定阈值 raw'], ['rainActiveLow', '雨=低电平 0/1'],
  ['windActiveLow', '风=低电平 0/1'], ['rainInhibit', '下雨禁自动 0/1'], ['windInhibit', '大风禁自动 0/1'],
  ['windAutoClear', '风停自动清 0/1'], ['ledEnabled', 'LED 使能 0/1'], ['emaShift', '滤波移位 0..6'],
  ['telemPeriodMs', '遥测周期 ms'],
  ['limitEnabled', '启用限位 0/1'], ['limitAStopsCw', 'A 限位挡 CW 0/1'],
  ['limitBStopsCcw', 'B 限位挡 CCW 0/1'], ['limitDebounceMs', '限位去抖 ms'],
  ['hwEstopEnabled', '读 J10 硬急停 0/1'], ['modeSelEnabled', '读 J11 模式开关 0/1'],
  ['imonEnabled', '电流检测 0/1'], ['stallMa', '堵转阈值 mA(0=关)'],
  ['stallHoldMs', '堵转保持 ms'], ['retractOnWeather', '风雨自动拉收 0/1'],
  ['retractOnNight', '夜间自动拉收 0/1'], ['retractDutyPct', '拉收占空 %'],
  ['retractMaxMs', '走限位超时 ms'], ['travelDwellMs', '走限位点动间隔 ms'],
];

async function loadConfig() {
  try {
    const j = await API.get('/api/config');
    const cfg = j.cfg || {};
    cfgEdit = {}; cfgDirty = false;
    $('cfgStatus').textContent = '已读取 ' + Object.keys(cfg).length + ' 项';
    return cfg;
  } catch (e) {
    $('cfgStatus').textContent = '读取失败: ' + e.message;
    return null;
  }
}

async function renderCfgGrid() {
  const cfg = await loadConfig();
  if (!cfg) return;
  const grid = $('cfgGrid');
  grid.innerHTML = '';
  CFG_FIELDS.forEach(([key, label]) => {
    if (cfg[key] === undefined) return;
    const wrap = document.createElement('label');
    wrap.textContent = label;
    const inp = document.createElement('input');
    inp.type = 'number';
    inp.value = cfg[key];
    inp.oninput = () => { cfgEdit[key] = inp.value; cfgDirty = true; };
    wrap.appendChild(inp);
    grid.appendChild(wrap);
  });
  $('roleGpio').value = cfg.pinLight;
}

async function saveConfig() {
  if (!cfgDirty) { toast('没有改动'); return; }
  let n = 0;
  for (const [k, v] of Object.entries(cfgEdit)) {
    const j = await cmd({ cmd: 'set', key: k, value: v }, true);
    if (!j.ok) { toast('写 ' + k + ' 失败: ' + j.error, true); break; }
    n++;
  }
  toast('已写入 NVS（' + n + ' 项）');
  await renderCfgGrid();
  poll();
}

// ---------------------------------------------------------------- 分页 + 返回键
function showTab(name) {
  document.querySelectorAll('nav.tabs button').forEach((b) => b.classList.toggle('act', b.dataset.tab === name));
  document.querySelectorAll('main > section.tab').forEach((s) => s.classList.toggle('act', s.dataset.tab === name));
  if (name === 'cfg') renderCfgGrid();
}

// ---------------------------------------------------------------- 散装页（清单/接线/组装）
const BOM_KEY = 'sunnet.bom.got';
let bomGot = {};
try { bomGot = JSON.parse(localStorage.getItem(BOM_KEY) || '{}') || {}; } catch (e) { bomGot = {}; }

function bomSave() { try { localStorage.setItem(BOM_KEY, JSON.stringify(bomGot)); } catch (e) {} }

function bomTotalText() {
  let sum = 0, have = 0;
  for (const it of BOM_A) {
    sum += it.price * it.qty;
    if (bomGot[it.id]) have += it.price * it.qty;
  }
  return { sum: Math.round(sum), have: Math.round(have), got: BOM_A.filter((i) => bomGot[i.id]).length };
}

// 一行清单：checkbox(可省) + 名称 + ⚡电压 + 板上位号 + 详细规格 + 搜索词 + 单价
function itemRow(it, plain) {
  const got = !!bomGot[it.id];
  const row = document.createElement('div');
  row.className = 'bomrow' + (got ? ' got' : '') + (plain ? ' plain' : '');
  const price = typeof it.price === 'number' ? '¥' + (it.price * it.qty).toFixed(1) : it.price;
  row.innerHTML =
    (plain ? '' : '<div class="bx">' + (got ? '✔' : '○') + '</div>') +
    '<div>' +
      '<div class="bn">' + it.name + ' <em>×' + it.qty + '</em></div>' +
      '<div class="bs">' +
        '<i class="bv">⚡ ' + (it.volt || '无源') + '</i>' +
        '<span class="bq">' + (it.part ? '对应板上 <b>' + it.part + '</b> · ' : '') + (it.why || '') + '</span>' +
      '</div>' +
      (it.spec ? '<div class="bsp">买什么规格：' + it.spec + '</div>' : '') +
      (it.kw ? shopBar(it.kw) : '') +
    '</div>' +
    '<div class="bp">' + price + '<small>' + it.qty + ' 件</small></div>';

  const kwBtn = row.querySelector('button.kw');
  if (kwBtn) {
    kwBtn.onclick = (ev) => {
      ev.stopPropagation();
      copy(kwBtn.dataset.kw, '关键词已复制，去搜索框粘贴：' + kwBtn.dataset.kw);
    };
  }
  row.querySelectorAll('button.shop').forEach((b) => {
    b.onclick = (ev) => { ev.stopPropagation(); openShop(b.dataset.shop, b.dataset.kw); };
  });
  if (!plain) {
    row.onclick = () => {
      if (bomGot[it.id]) delete bomGot[it.id]; else bomGot[it.id] = 1;
      bomSave(); renderBom(); renderBomHead();
    };
  }
  return row;
}

function renderBom() {
  const box = $('bomList');
  if (!box) return;
  box.innerHTML = '';
  for (const it of BOM_A) box.appendChild(itemRow(it, false));
  renderBomHead();
}

function renderBomHead() {
  const t = bomTotalText();
  const c = $('bomCount'); if (c) c.textContent = t.got + '/' + BOM_A.length + ' 已买';
  const b = $('bomTotal'); if (b) b.textContent = '合计 ≈ ¥' + t.sum + '（已买 ¥' + t.have + '）';
}

function bomText() {
  const L = ['太阳网控制器 · 散装模块采购清单（方案 A）', ''];
  for (const it of BOM_A) {
    L.push((bomGot[it.id] ? '[x] ' : '[ ] ') + it.name + ' ×' + it.qty +
            '  ¥' + (it.price * it.qty).toFixed(1) + '  （对应板上 ' + (it.part || '—') + '）');
    L.push('    电压：' + (it.volt || '无源'));
    if (it.spec) L.push('    规格：' + it.spec);
    L.push('    搜索：' + it.kw);
  }
  L.push('', '合计 ≈ ¥' + bomTotalText().sum + '（不含运费）');
  L.push('固件与 App 不变，只改 board.h 引脚表。');
  return L.join('\n');
}

// 只导出搜索词，一行一个，方便在淘宝/1688 直接粘
function bomKwText() {
  const L = [];
  for (const it of BOM_A) L.push(it.kw + (it.qty > 1 ? ' x' + it.qty : ''));
  return L.join('\n');
}

// 电压层级 + 接线表（同一套卡片样式）
function wireRows(list) {
  return list.map((w) =>
    '<div class="wirerow">' +
      '<div class="wp">' + w.part + '</div>' +
      '<div>' +
        '<div class="wn">' + (w.mod || w.why || '') + '</div>' +
        (w.gpio ? '<div class="wg"><i class="gpio">' + w.gpio + '</i>' +
                  '<i class="bv">⚡ ' + w.volt + '</i></div>'
                : '<div class="wnote">' + w.volt + '</div>') +
        (w.gpio && w.note ? '<div class="wnote">' + w.note + '</div>' : '') +
      '</div>' +
    '</div>').join('');
}

function renderVolt() {
  const box = $('voltTable');
  if (!box || typeof VOLT_SYS === 'undefined') return;
  box.innerHTML = VOLT_SYS.map((r) =>
    '<div class="wirerow">' +
      '<div class="wp">' + r[0] + '</div>' +
      '<div>' +
        '<div class="wn">' + r[1] + '</div>' +
        '<div class="wnote">' + r[2] + '</div>' +
        '<div class="wnote">⚠ ' + r[3] + '</div>' +
      '</div>' +
    '</div>').join('');
}

function wireText() {
  const L = ['太阳网散装 · 接线表（板上位号 → 模块 → GPIO → 电压）', ''];
  for (const w of WIRING) {
    L.push(w.part + ' → ' + w.mod + ' | ' + w.gpio + ' | ' + w.volt + (w.note ? ' | ' + w.note : ''));
  }
  L.push('');
  L.push('干接点：一端接 GPIO、一端接 GND，固件开内部上拉。模拟量只能 GPIO1-GPIO10（ADC1），输入 0-3.3V。');
  return L.join('\n');
}

function renderAlt(el, arr) {
  if (!el || !arr) return;
  el.innerHTML = '';
  for (const it of arr) el.appendChild(itemRow(normAlt(it), true));
}

// 方案 B/C/D 的条目是数组：[名称, 搜索词, 数量, 价格, 规格]
function normAlt(a) {
  if (!Array.isArray(a)) return a;
  return { name: a[0], kw: a[1], qty: a[2], price: a[3], spec: a[4] };
}

function renderDiy() {
  renderBom();
  renderVolt();
  const wb = $('wireTable'); if (wb) wb.innerHTML = wireRows(WIRING);
  renderAlt($('bomB'), BOM_B);
  renderAlt($('bomC'), BOM_C);
  renderAlt($('bomD'), BOM_D);

  const sl = $('stepList');
  if (sl) {
    sl.innerHTML = '';
    for (const [t, d] of STEPS) {
      const e = document.createElement('div');
      e.className = 'step';
      e.innerHTML = '<div class="n"></div><div><div class="t">' + t + '</div><div class="d">' + d + '</div></div>';
      e.onclick = () => e.classList.toggle('fold');
      sl.appendChild(e);
    }
  }

  const nl = $('noteList');
  if (nl) nl.innerHTML = NOTES.map((s) => '<div class="note"><i>⚠</i><div>' + s + '</div></div>').join('');

  const pp = $('pinPatch'); if (pp) pp.textContent = PIN_PATCH;

  $('btnCopyBom').onclick = () => copy(bomText(), '清单已复制（含电压和规格）');
  $('btnCopyKw').onclick = () => copy(bomKwText(), '17 个搜索词已复制，一行一个');
  $('btnCopyWire').onclick = () => copy(wireText(), '接线表已复制');
  $('btnCopyPin').onclick = () => copy(PIN_PATCH, '引脚表已复制');
  $('btnClearBom').onclick = () => { bomGot = {}; bomSave(); renderBom(); toast('已清空勾选'); };
  $('btnSkipBom').onclick = () => {
    bomGot = {};
    for (const it of BOM_A) if (BOM_MIN_SKIP.indexOf(it.id) < 0) bomGot[it.id] = 1;
    bomSave(); renderBom();
    toast('已标记最小集（跳过大风/急停/模式开关）');
  };
}

// 一行搜索条：关键词 + 复制 + 三个平台直接跳搜
function shopBar(kw) {
  return '<div class="bk">搜：<em>' + kw + '</em></div>' +
    '<div class="bbar">' +
      '<button class="kw" data-kw="' + kw + '">复制关键词</button>' +
      '<button class="shop tb" data-shop="taobao" data-kw="' + kw + '">淘宝</button>' +
      '<button class="shop pdd" data-shop="pdd" data-kw="' + kw + '">拼多多</button>' +
      '<button class="shop ali" data-shop="1688" data-kw="' + kw + '">1688</button>' +
    '</div>';
}

// 每个平台给几个候选链接，从前往后试；App 深链失败会自动退到网页版
const SHOPS = {
  taobao: {
    name: '淘宝',
    urls: (k) => ['taobao://s.taobao.com/search?q=' + k,
                  'taobao://m.taobao.com/tbopen/index.html?action=ali.open.nav&url=' +
                    encodeURIComponent('https://s.taobao.com/search?q=' + k),
                  'https://s.taobao.com/search?q=' + k],
  },
  pdd: {
    name: '拼多多',
    urls: (k) => ['pinduoduo://com.xunmeng.pinduoduo/search_result.html?search_key=' + k +
                    '&search_type=goods',
                  'https://mobile.yangkeduo.com/search_result.html?search_key=' + k],
  },
  1688: {
    name: '1688',
    urls: (k) => ['openapp://webview?url=' +
                    encodeURIComponent('https://s.1688.com/selloffer/offer_search.htm?keywords=' + k),
                  'https://s.1688.com/selloffer/offer_search.htm?keywords=' + k],
  },
};

function openShop(shop, kw) {
  const s = SHOPS[shop];
  if (!s) return;
  const list = s.urls(encodeURIComponent(kw));
  if (!API.hasBridge) { window.open(list[list.length - 1], '_blank'); return; }
  API.invoke('open', { urls: list }).then((r) => {
    if (r && r.ok) toast('已跳' + s.name + '搜：' + kw);
    else copy(kw, '没打开' + s.name + '，已复制关键词：' + kw);
  }).catch(() => copy(kw, '没打开' + s.name + '，已复制关键词：' + kw));
}

function copy(text, okMsg) {
  if (API.hasBridge) {
    API.invoke('copy', { text: text }).then((r) => {
      toast(r && r.ok ? okMsg : '复制失败', !(r && r.ok));
    }).catch(() => toast('复制失败', true));
    return;
  }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => toast(okMsg)).catch(() => toast('复制失败', true));
  } else {
    const ta = document.createElement('textarea');
    ta.value = text; document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); toast(okMsg); } catch (e) { toast('复制失败', true); }
    ta.remove();
  }
}
window.__back = function () {
  const cur = document.querySelector('nav.tabs button.act');
  if (cur && cur.dataset.tab !== 'ctrl') { showTab('ctrl'); return; }
  if (window.__backArmed) { API.invoke('exit', {}); return; }
  window.__backArmed = true;
  toast('再按一次返回键退出');
  setTimeout(() => { window.__backArmed = false; }, 1500);
};

// ---------------------------------------------------------------- 启动
(async function boot() {
  document.querySelectorAll('nav.tabs button').forEach((b) => {
    b.onclick = () => showTab(b.dataset.tab);
  });
  bindMotorButtons();
  bindPanelSim();
  bindLeds();
  bindScanMap();
  $('btnSaveCfg').onclick = saveConfig;
  renderDiy();
  $('btnReload').onclick = () => { renderCfgGrid(); toast('已重新读取'); };
  $('duty').oninput(); $('jogMs').oninput();
  showTab('ctrl');

  await bindConn();
  if (!API.hasBridge) $('connHelp').textContent = '浏览器模式：只能填设备 IP 连（没有 BLE）。';

  poll();
  setInterval(poll, 1000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); });
})();
