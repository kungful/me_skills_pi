// ============================================================================
// transport.js —— 前端与设备之间的唯一出入口
//
// 在 App 里：调用原生 window.SunNet.invoke(reqId, op, argsJson)，
//            原生异步完成后回调 window.__apiResult(reqId, ok, payload)。
// 在电脑浏览器里：没有 SunNet，自动退化成 fetch()，
//            所以这个页面同时也能当普通网页用（固件的 LittleFS WebUI 就是这么跑）。
// ============================================================================
'use strict';

const API = (() => {
  const HAS_BRIDGE = typeof window.SunNet !== 'undefined' && !!window.SunNet;
  let seq = 0;
  const pending = new Map();
  const listeners = [];
  let status = { mode: 'none', host: '192.168.4.1', port: 80, bleConnected: false, bleReady: false, blePerm: false };

  // ---- 原生 → 前端 的两个回调 ----
  window.__apiResult = function (id, ok, payload) {
    const p = pending.get(id);
    if (!p) return;
    pending.delete(id);
    if (ok === 1 || ok === true) {
      let data = payload;
      if (typeof data === 'string') {
        try { data = JSON.parse(data); } catch (e) { data = { ok: true, raw: payload }; }
      }
      p.resolve(data);
    } else {
      p.reject(new Error(payload || '调用失败'));
    }
  };

  window.__event = function (name, json) {
    let data = json;
    if (typeof data === 'string') { try { data = JSON.parse(data); } catch (e) { data = { raw: json }; } }
    if (name === 'conn') {
      if (data.state === 'connected') status = Object.assign(status, { mode: data.mode || status.mode }, data);
      if (data.state === 'disconnected') status = Object.assign(status, { mode: 'none', bleConnected: false });
      if (data.state === 'perm') { /* 权限变化：下一次 status 会刷新 */ }
    }
    listeners.forEach((f) => { try { f(name, data); } catch (e) {} });
  };

  // ---- 原生桥 ----
  function invoke(op, args) {
    return new Promise((resolve, reject) => {
      const id = 'r' + (++seq);
      pending.set(id, { resolve, reject });
      try {
        window.SunNet.invoke(id, op, JSON.stringify(args || {}));
      } catch (e) {
        pending.delete(id);
        reject(new Error('原生通道异常: ' + e));
      }
      setTimeout(() => {
        if (pending.has(id)) { pending.delete(id); reject(new Error('超时（设备没响应）')); }
      }, 15000);
    });
  }

  // ---- 浏览器退化路径 ----
  let base = localStorage.getItem('sunnet.host') || '192.168.4.1';
  async function fetchJson(path, body) {
    const url = 'http://' + base + path;
    const opt = body == null
      ? { cache: 'no-store' }
      : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
    const r = await fetch(url, opt);
    const t = await r.text();
    let j;
    try { j = JSON.parse(t); } catch (e) { throw new Error('返回不是 JSON: ' + t.slice(0, 120)); }
    if (!j.ok && r.status >= 400) throw new Error(j.error || ('HTTP ' + r.status));
    return j;
  }

  // ---- 对外 ----
  const api = {
    hasBridge: HAS_BRIDGE,
    invoke,
    get status() { return status; },
    onEvent(f) { listeners.push(f); },
    host: () => base,

    async status() {
      if (!HAS_BRIDGE) return status;
      try { status = Object.assign(status, await invoke('status', {})); } catch (e) { /* 忽略 */ }
      return status;
    },

    async connectWifi(host) {
      host = (host || '').trim();
      if (!host) throw new Error('请填设备地址');
      if (HAS_BRIDGE) {
        const r = await invoke('wifi', { host });
        base = host.replace(/:\d+$/, '');
        localStorage.setItem('sunnet.host', base);
        status = Object.assign(status, { mode: 'http', host: base });
        return r;
      }
      base = host.replace(/:\d+$/, '');
      try {
        localStorage.setItem('sunnet.host', base);
        await fetchJson('/api/health');
        status = Object.assign(status, { mode: 'http', host: base });
        return { ok: true };
      } catch (e) {
        throw new Error('连不上 http://' + base + ' —— ' + e.message);
      }
    },

    async scanBle(ms) {
      if (!HAS_BRIDGE) throw new Error('BLE 只能在 App 里用');
      const list = await invoke('ble.scan', { ms: ms || 6000 });
      return Array.isArray(list) ? list : [];
    },

    async connectBle(dev) {
      if (!HAS_BRIDGE) throw new Error('BLE 只能在 App 里用');
      const r = await invoke('ble.connect', { id: dev.id, name: dev.name });
      status = Object.assign(status, { mode: 'ble', bleConnected: true, name: dev.name });
      return r;
    },

    async askBlePermission() { if (HAS_BRIDGE) return invoke('ble.perm', {}); },

    async disconnect() {
      if (HAS_BRIDGE) { try { await invoke('ble.disconnect', {}); } catch (e) {} }
      status = Object.assign(status, { mode: 'none', bleConnected: false });
    },

    async get(path) {
      if (!HAS_BRIDGE) return fetchJson(path, null);
      return invoke('get', { path });
    },

    async post(path, body) {
      if (!HAS_BRIDGE) return fetchJson(path, body);
      return invoke('post', { path: path, body: JSON.stringify(body || {}) });
    },
  };
  return api;
})();
