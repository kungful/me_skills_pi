// ============================================================================
// transport.js —— 页面与原生之间的唯一出入口
//
// App 内：window.Tea.invoke(reqId, op, argsJson)，原生完成后回调
//          window.__apiResult(reqId, ok, payload)。
// 电脑浏览器：没有 Tea，退化用 fetch()，方便在电脑上调试界面。
// ============================================================================
'use strict';

const Tea = (() => {
  const NATIVE = (typeof window.Tea !== 'undefined' && window.Tea) ? window.Tea : null;
  const HAS_BRIDGE = !!NATIVE;
  let seq = 0;
  const pending = new Map();
  const listeners = [];

  // ---- 原生 → 前端 ----
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
    listeners.forEach((f) => { try { f(name, data); } catch (e) {} });
  };

  function invoke(op, args, timeoutMs) {
    return new Promise((resolve, reject) => {
      const id = 'r' + (++seq);
      pending.set(id, { resolve, reject });
      try {
        NATIVE.invoke(id, op, JSON.stringify(args || {}));
      } catch (e) {
        pending.delete(id);
        reject(new Error('原生通道异常: ' + e));
        return;
      }
      setTimeout(() => {
        if (pending.has(id)) { pending.delete(id); reject(new Error('超时（网络太慢或接口没响应）')); }
      }, timeoutMs || 40000);
    });
  }

  // ---- 浏览器退化 ----
  async function browserHttp(url, opt) {
    const o = opt || {};
    const r = await fetch(url, {
      method: o.method || 'GET',
      headers: o.headers || {},
      body: o.body || undefined,
      cache: 'no-store',
    });
    const t = await r.text();
    return { status: r.status, charset: 'utf-8', body: t, headers: {} };
  }

  const api = {
    hasBridge: HAS_BRIDGE,
    invoke,
    onEvent(f) { listeners.push(f); },

    async status() {
      if (!HAS_BRIDGE) return { app: '茶叶军师', version: 'dev(浏览器)', model: navigator.userAgent };
      return invoke('status', {}, 8000);
    },

    /** 任意 HTTP；返回 {status, charset, body, headers} */
    async http(url, opt) {
      const o = Object.assign({ method: 'GET', timeout: 15 }, opt || {});
      if (!HAS_BRIDGE) return browserHttp(url, o);
      return invoke('http', {
        url: url,
        method: o.method || 'GET',
        headers: o.headers || {},
        body: o.body || '',
        encoding: o.encoding || '',
        timeout: o.timeout || 15,
      }, ((o.timeout || 15) + 10) * 1000);
    },

    /** 取文本 */
    async text(url, opt) {
      const r = await api.http(url, opt);
      if (r.status >= 400 && !r.body) throw new Error('HTTP ' + r.status);
      return r.body;
    },

    /** 取 JSON（自动剥 JSONP / 前后缀） */
    async json(url, opt) {
      const t = await api.text(url, opt);
      return parseLoose(t);
    },

    // ---- 本地设置 ----
    store: {
      async set(key, value) {
        if (!HAS_BRIDGE) { localStorage.setItem('tea.' + key, value); return { ok: true }; }
        return invoke('store.set', { key: key, value: String(value == null ? '' : value) }, 8000);
      },
      async get(key, def) {
        if (!HAS_BRIDGE) { const v = localStorage.getItem('tea.' + key); return v == null ? (def || '') : v; }
        const r = await invoke('store.get', { key: key, default: def || '' }, 8000);
        return r.value == null ? (def || '') : r.value;
      },
      async all() {
        if (!HAS_BRIDGE) {
          const o = {};
          for (let i = 0; i < localStorage.length; i++) {
            const k = localStorage.key(i);
            if (k.indexOf('tea.') === 0) o[k.slice(4)] = localStorage.getItem(k);
          }
          return o;
        }
        return invoke('store.all', {}, 8000);
      },
      async del(key) {
        if (!HAS_BRIDGE) { localStorage.removeItem('tea.' + key); return { ok: true }; }
        return invoke('store.del', { key: key }, 8000);
      },
    },

    async copy(text) { if (!HAS_BRIDGE) { try { await navigator.clipboard.writeText(text); } catch (e) {} return { ok: true }; } return invoke('copy', { text: text }, 8000); },
    async paste() { if (!HAS_BRIDGE) { try { return { ok: true, text: await navigator.clipboard.readText() }; } catch (e) { throw new Error('浏览器不允许读剪贴板'); } } return invoke('paste', {}, 8000); },
    async open(url) { if (!HAS_BRIDGE) { window.open(url, '_blank'); return { ok: true }; } return invoke('open', { url: url }, 8000); },
    async save(name, text) { if (!HAS_BRIDGE) { download(name, text); return { ok: true, path: '(浏览器下载)' }; } return invoke('save', { name: name, text: text }, 20000); },
    async share(title, text) { if (!HAS_BRIDGE) { try { await navigator.share({ title: title, text: text }); } catch (e) { await api.copy(text); } return { ok: true }; } return invoke('share', { title: title, text: text }, 15000); },

    // ---- 本地文档（客户台账等） ----
    async readDoc(name) {
      if (!HAS_BRIDGE) { return localStorage.getItem('doc.' + name) || ''; }
      const r = await invoke('io.read', { name: name }, 15000);
      return r.text || '';
    },
    async writeDoc(name, text) {
      if (!HAS_BRIDGE) { localStorage.setItem('doc.' + name, text); return { ok: true }; }
      return invoke('io.write', { name: name, text: text }, 15000);
    },

    // ---- 晨报 ----
    briefing: {
      async get() { if (!HAS_BRIDGE) return { ok: true, text: '', time: '' }; return invoke('briefing.get', {}, 8000); },
      async run(ai) { if (!HAS_BRIDGE) throw new Error('晨报只能在 App 里生成'); return invoke('briefing.run', { ai: ai !== false }, 150000); },
      async set(o) { if (!HAS_BRIDGE) { localStorage.setItem('tea.briefing', JSON.stringify(o)); return o; } return invoke('briefing.set', o, 10000); },
      async state() { if (!HAS_BRIDGE) { try { return JSON.parse(localStorage.getItem('tea.briefing') || '{}'); } catch (e) { return {}; } } return invoke('briefing.state', {}, 8000); },
    },

    async notifyPerm() { if (!HAS_BRIDGE) { if (window.Notification) await Notification.requestPermission(); return { ok: true }; } return invoke('notify.perm', {}, 8000); },
    async notifyTest() { if (!HAS_BRIDGE) { new Notification('茶叶军师', { body: '浏览器测试通知' }); return { ok: true }; } return invoke('notify.test', {}, 8000); },
  };
  // 内联 onclick 里用 TeaAPI（不能叫 Tea：window.Tea 是原生桥对象，会被替换掉）
  window.TeaAPI = api;
  return api;

  function download(name, text) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], { type: 'text/markdown' }));
    a.download = name;
    a.click();
  }
})();

/** 宽容的 JSON 解析：处理 JSONP、BOM、前后杂质、单引号 */
function parseLoose(t) {
  if (t == null) throw new Error('空响应');
  let s = String(t).replace(/^\uFEFF/, '').trim();
  const m = s.match(/^[A-Za-z_$][\w$]*\s*\(\s*([\s\S]*?)\s*\)\s*;?\s*$/);
  if (m) s = m[1];
  try { return JSON.parse(s); } catch (e) { /* 继续试 */ }
  const i = s.search(/[[{]/);
  if (i > 0) s = s.slice(i);
  const j = Math.max(s.lastIndexOf('}'), s.lastIndexOf(']'));
  if (j >= 0) s = s.slice(0, j + 1);
  try { return JSON.parse(s); } catch (e) { throw new Error('不是 JSON：' + s.slice(0, 100)); }
}
