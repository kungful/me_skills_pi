/* 万物原理 —— 引擎 */
(function () {
  'use strict';

  var MODS = (window.COSMOS && window.COSMOS.modules) || [];
  var APP = document.getElementById('app');

  /* ---------------- 存储 ---------------- */
  var KEY = 'cosmos.progress.v1';
  var hasNative = typeof Native !== 'undefined' && Native && Native.save;

  function blank() {
    return { done: {}, quiz: {}, streak: 0, lastDay: '', forgeBest: 0, forgePlays: 0, opened: 0 };
  }
  var P = blank();

  function loadProgress() {
    var raw = '';
    try { raw = hasNative ? Native.load() : (localStorage.getItem(KEY) || ''); } catch (e) { raw = ''; }
    if (raw) {
      try {
        var o = JSON.parse(raw);
        P = { done: o.done || {}, quiz: o.quiz || {}, streak: o.streak || 0,
              lastDay: o.lastDay || '', forgeBest: o.forgeBest || 0,
              forgePlays: o.forgePlays || 0, opened: o.opened || 0 };
      } catch (e2) { P = blank(); }
    }
    tickStreak();
  }
  function saveProgress() {
    var raw = JSON.stringify(P);
    try { if (hasNative) Native.save(raw); else localStorage.setItem(KEY, raw); } catch (e) {}
  }
  function today() {
    var d = new Date();
    return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate();
  }
  function tickStreak() {
    var t = today();
    if (P.lastDay === t) return;
    var y = new Date(); y.setDate(y.getDate() - 1);
    var yk = y.getFullYear() + '-' + (y.getMonth() + 1) + '-' + y.getDate();
    P.streak = (P.lastDay === yk) ? (P.streak + 1) : 1;
    P.lastDay = t;
    saveProgress();
  }

  /* ---------------- 工具 ---------------- */
  /* 只放行 <b>/<em> 两种行内标签，其余一律转义（内容里全是中文，安全且够用） */
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;')
      .replace(/&lt;(\/?)(b|em)&gt;/g, '<$1$2>');
  }
  function buzz(ms) { try { if (typeof Native !== 'undefined' && Native.buzz) Native.buzz(ms || 12); } catch (e) {} }
  function toast(m) { try { if (typeof Native !== 'undefined' && Native.toast) Native.toast(m); else console.log(m); } catch (e) {} }

  function allLessons() {
    var a = [];
    MODS.forEach(function (m) {
      (m.lessons || []).forEach(function (l) { a.push({ m: m, l: l }); });
    });
    return a;
  }
  function lessonTotal() { return allLessons().length; }
  function masteredCount() {
    var n = 0; Object.keys(P.quiz).forEach(function (k) { if (P.quiz[k] && P.quiz[k].pass) n++; });
    return n;
  }
  function readCount() { return Object.keys(P.done).length; }
  function modStat(m) {
    var ls = m.lessons || [], read = 0, ok = 0;
    ls.forEach(function (l) {
      if (P.done[l.id]) read++;
      if (P.quiz[l.id] && P.quiz[l.id].pass) ok++;
    });
    return { total: ls.length, read: read, pass: ok };
  }
  function findLesson(id) {
    var all = allLessons();
    for (var i = 0; i < all.length; i++) if (all[i].l.id === id) return all[i];
    return null;
  }

  /* ---------------- 路由 ---------------- */
  var stack = [];
  function nav(screen, push) {
    if (push !== false) stack.push(screen);
    render();
    window.scrollTo(0, 0);
    syncBack();
  }
  function replaceRoot(screen) { stack = [screen]; render(); window.scrollTo(0, 0); syncBack(); }
  function syncBack() {
    try { if (typeof Native !== 'undefined' && Native.setCanBack) Native.setCanBack(stack.length > 1); } catch (e) {}
  }
  window.__cosmosBack = function () {
    if (stack.length > 1) { stack.pop(); render(); window.scrollTo(0, 0); syncBack(); }
  };

  /* ---------------- 渲染 ---------------- */
  var TAB = 'home';

  function render() {
    var s = stack[stack.length - 1] || { n: 'home' };
    var html = '';
    if (s.n === 'home') html = viewHome();
    else if (s.n === 'mod') html = viewMod(s.id);
    else if (s.n === 'lesson') html = viewLesson(s.id);
    else if (s.n === 'forge') html = viewForge();
    else if (s.n === 'search') html = viewSearch();
    else if (s.n === 'me') html = viewMe();
    else if (s.n === 'list') html = viewAll();
    APP.innerHTML = html;
    if (s.n !== 'lesson' && s.n !== 'forge') renderTabbar();
    else renderTabbar();
    postRender(s);
  }

  function renderTabbar() {
    var old = document.getElementById('tabbar');
    if (old) old.parentNode.removeChild(old);
    var tabs = [
      { k: 'home', i: '🧭', t: '学科地图' },
      { k: 'forge', i: '🔥', t: '熔炉' },
      { k: 'search', i: '🔍', t: '搜索' },
      { k: 'me', i: '⚔', t: '我的' }
    ];
    var cur = stack[stack.length - 1];
    var act = cur.n === 'forge' ? 'forge' : cur.n === 'search' ? 'search' : cur.n === 'me' ? 'me' : 'home';
    var d = document.createElement('div');
    d.id = 'tabbar'; d.className = 'tabbar';
    d.innerHTML = '<div class="in">' + tabs.map(function (t) {
      return '<button data-tab="' + t.k + '" class="' + (act === t.k ? 'on' : '') + '">' +
        '<span class="i">' + t.i + '</span>' + t.t + '</button>';
    }).join('') + '</div>';
    document.body.appendChild(d);
    d.querySelectorAll('button').forEach(function (b) {
      b.addEventListener('click', function () {
        buzz(10);
        var k = b.getAttribute('data-tab');
        replaceRoot({ n: k === 'home' ? 'home' : k });
      });
    });
  }

  function top(title, crumb, backTo) {
    return '<div class="top row">' +
      '<button class="back" data-act="back">‹</button>' +
      '<div class="grow"><div class="crumb">' + esc(crumb || '') + '</div>' +
      '<h1 class="nowrap">' + esc(title) + '</h1></div></div>';
  }

  /* ---------- 首页 ---------- */
  function viewHome() {
    var total = lessonTotal(), ok = masteredCount(), read = readCount();
    var h = '';
    h += '<div class="hero">' +
      '<div class="t1">万物原理</div>' +
      '<div class="t2">从原子到资本 · 一套能听懂的宇宙运行手册</div>' +
      '<div class="t3">这个 App 只赌一件事：<b style="color:#ffd7c4">你不是学不会，你只是没遇到用大白话讲的人。</b>每一课先给你一句话本质，再打一个比方，最后告诉你哪里最容易搞错。</div>' +
      '</div>';
    h += '<div class="stats">' +
      '<div class="stat"><b>' + ok + '</b><span>已掌握</span></div>' +
      '<div class="stat"><b>' + P.streak + '</b><span>连续天数</span></div>' +
      '<div class="stat"><b>' + P.forgeBest + '</b><span>熔炉最佳</span></div>' +
      '</div>';
    h += '<div class="card mt tiny muted">总进度：已读完 <b style="color:#f0d18a">' + read + '</b> / ' + total +
      ' 课　·　已通过测验 <b style="color:#f0d18a">' + ok + '</b> 课</div>';

    h += '<div class="sec-title">学科地图 · 十一块拼图</div>';
    h += '<div class="mgrid">';
    MODS.forEach(function (m) {
      var st = modStat(m);
      var pct = st.total ? Math.round(st.pass / st.total * 100) : 0;
      h += '<button class="mod" data-act="mod" data-id="' + m.id + '">' +
        '<span class="glow" style="background:' + m.hue + '"></span>' +
        '<div class="ic">' + m.icon + '</div>' +
        '<div class="nm">' + esc(m.name) + '</div>' +
        '<div class="tg">' + esc(m.tag) + '</div>' +
        '<div class="bar"><i style="width:' + pct + '%;background:' + m.hue + '"></i></div>' +
        '<div class="pct"><span>' + st.pass + '/' + st.total + ' 掌握</span><span>' + pct + '%</span></div>' +
        '</button>';
    });
    h += '</div>';

    h += '<div class="sec-title">怎么用这个 App</div>';
    h += '<div class="card tiny" style="color:#c3cfe3;line-height:1.9">' +
      '① 一天只啃 <b>2～3 课</b>，读完立刻做那 2 道题，错了看解析——这比通读 50 页强十倍。<br>' +
      '② 每课结尾的「<b>记住这句话</b>」，是这门学科的一根钢筋，背下来，以后能挂住一整面墙。<br>' +
      '③ 攒够 5 课之后，去底部「<b>🔥 熔炉</b>」打一场限时混测，把知识从"认识"逼成"会"。</div>';

    h += '<div class="sec-title">全部课程速览</div>';
    h += '<button class="btn block" data-act="list">📚 查看全部 ' + total + ' 课</button>';
    h += '<div style="height:20px"></div>';
    return h;
  }

  function viewAll() {
    var h = top('全部课程', '速览', 1);
    MODS.forEach(function (m) {
      h += '<div class="sec-title">' + m.icon + ' ' + esc(m.name) + '</div>';
      (m.lessons || []).forEach(function (l, i) {
        h += rowLesson(m, l, i + 1);
      });
    });
    h += '<div style="height:20px"></div>';
    return h;
  }

  function rowLesson(m, l, n) {
    var done = P.done[l.id];
    var pass = P.quiz[l.id] && P.quiz[l.id].pass;
    return '<button class="lrow ' + (done || pass ? 'on' : '') + '" data-act="lesson" data-id="' + l.id + '">' +
      '<span class="no">' + (pass ? '✓' : n) + '</span>' +
      '<span class="grow"><span class="tt">' + esc(l.title) + '</span>' +
      (l.essence ? '<span class="es">' + esc(l.essence) + '</span>' : '') + '</span>' +
      (pass ? '<span class="tag">已掌握</span>' : done ? '<span class="pill">已读</span>' : '') +
      '</button>';
  }

  /* ---------- 学科页 ---------- */
  function viewMod(id) {
    var m = MODS.filter(function (x) { return x.id === id; })[0];
    if (!m) return '<div class="empty">没有这个学科</div>';
    var st = modStat(m);
    var h = top(m.name, m.tag, 1);
    h += '<div class="card" style="border-color:' + m.hue + '55">' +
      '<div style="font-size:15.5px;line-height:1.85;color:#dbe3f0">' + esc(m.blurb) + '</div>' +
      '<div class="hr"></div>' +
      '<div class="row tiny muted"><span>共 ' + st.total + ' 课</span><span>·</span>' +
      '<span>已读 ' + st.read + '</span><span>·</span><span style="color:#5fd39a">已掌握 ' + st.pass + '</span></div>' +
      '</div>';
    // 找到第一篇没掌握的，作为"继续"
    var next = null;
    (m.lessons || []).forEach(function (l) {
      if (!next && !(P.quiz[l.id] && P.quiz[l.id].pass)) next = l;
    });
    if (next) {
      h += '<div class="mt"><button class="btn gold block" data-act="lesson" data-id="' + next.id + '">' +
        (st.read ? '▶ 继续：' : '▶ 从这里开始：') + esc(next.title) + '</button></div>';
    } else {
      h += '<div class="mt"><div class="card center tiny" style="color:#5fd39a">🏅 这一学科你已经全部通关。去 🔥 熔炉压一压速度。</div></div>';
    }
    h += '<div class="sec-title">课程</div>';
    (m.lessons || []).forEach(function (l, i) { h += rowLesson(m, l, i + 1); });
    h += '<div style="height:20px"></div>';
    return h;
  }

  /* ---------- 课程页 ---------- */
  function viewLesson(id) {
    var f = findLesson(id);
    if (!f) return '<div class="empty">课程不存在</div>';
    var m = f.m, l = f.l;
    var idx = (m.lessons || []).indexOf(l);
    var prev = idx > 0 ? m.lessons[idx - 1] : null;
    var next = idx < m.lessons.length - 1 ? m.lessons[idx + 1] : null;

    if (!P.done[l.id]) { P.done[l.id] = 1; saveProgress(); }

    var h = top(l.title, m.icon + ' ' + m.name + ' · 第 ' + (idx + 1) + '/' + m.lessons.length + ' 课', 1);

    if (l.essence) h += '<div class="blk"><div class="lb">一句话本质</div><div class="essence">' + esc(l.essence) + '</div></div>';
    if (l.analogy) h += '<div class="blk"><div class="lb">打个比方</div><div class="analogy">' + esc(l.analogy) + '</div></div>';

    if (l.steps && l.steps.length) {
      h += '<div class="blk"><div class="lb">一步步拆开</div>';
      l.steps.forEach(function (s) {
        h += '<div class="step">' + (s.h ? '<div class="sh">' + esc(s.h) + '</div>' : '') +
          '<div class="sp">' + s.p + '</div></div>';
      });
      h += '</div>';
    }

    if (l.deep) {
      h += '<div class="blk"><div class="lb">想再深一点</div>' +
        '<div class="deep"><div class="dh" data-act="fold">▸ 展开这一段（不想看也能跳过）</div>' +
        '<div class="db" style="display:none">' + l.deep + '</div></div></div>';
    }

    if (l.myths && l.myths.length) {
      h += '<div class="blk"><div class="lb">最容易搞错的地方</div>';
      l.myths.forEach(function (my) {
        h += '<div class="myth"><div class="mq">✗ ' + esc(my.q) + '</div>' +
          '<div class="ma">✓ ' + esc(my.a) + '</div></div>';
      });
      h += '</div>';
    }

    if (l.remember) {
      h += '<div class="blk"><div class="rem"><div class="rl">记 住 这 句 话</div>' +
        '<div class="rt">' + esc(l.remember) + '</div></div></div>';
    }

    if (l.quiz && l.quiz.length) {
      h += '<div class="blk"><div class="lb">自测 · 答错才有收获</div>' +
        '<div id="quizBox" data-lesson="' + l.id + '"></div>' +
        '<div id="quizEnd"></div></div>';
    }

    h += '<div class="nav2">' +
      (prev ? '<button class="btn" data-act="lesson" data-id="' + prev.id + '">‹ 上一课</button>' : '') +
      (next ? '<button class="btn gold" data-act="lesson" data-id="' + next.id + '">下一课 ›</button>'
            : '<button class="btn gold" data-act="mod" data-id="' + m.id + '">回到学科目录</button>') +
      '</div>';
    h += '<div class="center tiny muted mb">' + esc(m.name) + ' · ' + esc(l.title) + '</div>';
    h += '<div style="height:10px"></div>';
    return h;
  }

  /* ---------- 测验 ---------- */
  function renderQuiz(host, lessonId, list, onDone) {
    var i = 0, right = 0, answered = false;
    function draw() {
      if (i >= list.length) {
        var pass = right >= Math.ceil(list.length * 0.7);
        var old = P.quiz[lessonId];
        var best = old ? Math.max(old.best || 0, right) : right;
        P.quiz[lessonId] = { best: best, total: list.length, pass: (old && old.pass) || pass };
        saveProgress();
        host.innerHTML = '';
        document.getElementById('quizEnd').innerHTML =
          '<div class="card center" style="border-color:' + (pass ? '#2f6b48' : '#7a2b2b') + '">' +
          '<div style="font-size:34px">' + (pass ? '🏅' : '🧱') + '</div>' +
          '<div style="font-size:17px;font-weight:700;margin-top:6px">答对 ' + right + ' / ' + list.length + '</div>' +
          '<div class="tiny muted mt">' + (pass ? '这一课算掌握了。往下走。' : '没到 70%。回头把「一句话本质」再读一遍，再打一次。') + '</div>' +
          '<div class="mt"><button class="btn" data-act="retry" data-id="' + lessonId + '">重打一遍</button></div>' +
          '</div>';
        if (onDone) onDone(right, list.length, pass);
        buzz(pass ? 30 : 60);
        return;
      }
      var q = list[i];
      answered = false;
      host.innerHTML = '<div class="q"><div class="qq">' + (i + 1) + '. ' + esc(q.q) + '</div>' +
        q.opts.map(function (o, k) {
          return '<button class="opt" data-k="' + k + '"><span class="k">' + 'ABCD'[k] + '</span>' + esc(o) + '</button>';
        }).join('') + '</div><div id="whyHost"></div>';
      host.querySelectorAll('.opt').forEach(function (b) {
        b.addEventListener('click', function () {
          if (answered) return;
          answered = true;
          var k = parseInt(b.getAttribute('data-k'), 10);
          var correct = (k === q.a);
          if (correct) { right++; buzz(12); } else { buzz(60); }
          host.querySelectorAll('.opt').forEach(function (x) {
            var xk = parseInt(x.getAttribute('data-k'), 10);
            if (xk === q.a) x.classList.add('ok');
            else if (xk === k) x.classList.add('bad');
          });
          document.getElementById('whyHost').innerHTML =
            '<div class="why"><b>' + (correct ? '对。' : '不对。') + '</b>' + esc(q.why || '') + '</div>' +
            '<div class="mt"><button class="btn block" id="nextQ">' + (i === list.length - 1 ? '看结果' : '下一题') + '</button></div>';
          document.getElementById('nextQ').addEventListener('click', function () { i++; draw(); });
        });
      });
    }
    draw();
  }

  /* ---------- 熔炉 ---------- */
  var forgeState = null;
  function pickForge(n) {
    var pool = [];
    MODS.forEach(function (m) {
      (m.lessons || []).forEach(function (l) {
        if (l.quiz && l.quiz.length && P.done[l.id]) {
          l.quiz.forEach(function (q) { pool.push({ q: q, from: m.name + ' · ' + l.title }); });
        }
      });
    });
    if (pool.length < 4) {
      pool = [];
      MODS.forEach(function (m) {
        (m.lessons || []).forEach(function (l) {
          (l.quiz || []).forEach(function (q) { pool.push({ q: q, from: m.name + ' · ' + l.title }); });
        });
      });
    }
    for (var i = pool.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = pool[i]; pool[i] = pool[j]; pool[j] = t;
    }
    return pool.slice(0, n);
  }

  function viewForge() {
    if (!forgeState) {
      var h = top('熔炉挑战', '限时 · 跨学科混测', 1);
      h += '<div class="card">' +
        '<div style="font-size:15.5px;line-height:1.85;color:#dbe3f0">抽 8 道题，每道 <b>20 秒</b>。' +
        '你学过的学科越杂，这里越像"世界在你脑子里打架"——那正是它开始联通的感觉。</div>' +
        '<div class="hr"></div><div class="tiny muted">答对得 1 分，超时算错。最高分会被记住。</div>' +
        '<div class="mt row"><span class="pill">历史最佳 ' + P.forgeBest + ' 分</span>' +
        '<span class="pill">已挑战 ' + P.forgePlays + ' 次</span></div>' +
        '</div>' +
        '<div class="mt"><button class="btn red block" data-act="forgeStart">🔥 点燃熔炉</button></div>';
      var ls = allLessons().filter(function (x) { return P.done[x.l.id]; }).length;
      h += '<div class="tiny muted center mt">已读 ' + ls + ' 课。读得越多，熔炉里的题越对味。</div>';
      h += '<div style="height:20px"></div>';
      return h;
    }
    var st = forgeState;
    var cur = st.list[st.i];
    if (!cur) {
      var pass = st.score >= 6;
      var h2 = top('熔炉结算', '跨学科混测', 1);
      h2 += '<div class="forge-hd"><div class="big">' + st.score + ' <span style="font-size:17px;color:#93a1bb">/ ' + st.list.length + '</span></div>' +
        '<div class="muted mt">' + (pass ? '打穿了。你的知识开始连成网。' : '还不够。回去多读两课，再来。') + '</div></div>';
      if (st.score > P.forgeBest) { P.forgeBest = st.score; }
      P.forgePlays++;
      saveProgress();
      h2 += '<div class="mt"><button class="btn red block" data-act="forgeStart">再来一炉</button></div>';
      h2 += '<div class="mt"><button class="btn ghost block" data-act="forgeExit">离开熔炉</button></div>';
      return h2;
    }
    var h3 = top('第 ' + (st.i + 1) + ' / ' + st.list.length + ' 题', '熔炉 · ' + cur.from, 1);
    h3 += '<div class="timerbar"><i id="tbar" style="width:100%"></i></div>' +
      '<div class="tiny muted center" id="tnum">20s</div>';
    h3 += '<div class="q mt"><div class="qq">' + esc(cur.q.q) + '</div>' +
      cur.q.opts.map(function (o, k) {
        return '<button class="opt" data-k="' + k + '"><span class="k">' + 'ABCD'[k] + '</span>' + esc(o) + '</button>';
      }).join('') + '</div><div id="fwhy"></div>';
    h3 += '<div class="tiny muted center mt">当前得分 ' + st.score + '</div>';
    return h3;
  }

  function postRender(s) {
    if (s.n === 'lesson') {
      var host = document.getElementById('quizBox');
      var f = findLesson(s.id);
      if (host && f && f.l.quiz && f.l.quiz.length) {
        renderQuiz(host, f.l.id, f.l.quiz);
      }
    }
    if (s.n === 'forge' && forgeState && forgeState.list[forgeState.i]) {
      startForgeTimer();
    }
  }

  var forgeTimer = null;
  function startForgeTimer() {
    if (forgeTimer) clearInterval(forgeTimer);
    var left = 20;
    var cur = forgeState.list[forgeState.i];
    var host = APP.querySelector('.q');
    var answered = false;
    var bar = document.getElementById('tbar');
    var num = document.getElementById('tnum');
    function finish(correct, k) {
      answered = true;
      if (forgeTimer) clearInterval(forgeTimer);
      var q = cur.q;
      host.querySelectorAll('.opt').forEach(function (x) {
        var xk = parseInt(x.getAttribute('data-k'), 10);
        if (xk === q.a) x.classList.add('ok');
        else if (xk === k) x.classList.add('bad');
      });
      if (correct) { forgeState.score++; buzz(12); } else { buzz(60); }
      document.getElementById('fwhy').innerHTML =
        '<div class="why">' + (correct ? '<b>对。</b>' : '<b>' + (k === -1 ? '超时。' : '错。') + '</b>') + esc(q.why || '') + '</div>' +
        '<div class="mt"><button class="btn red block" id="fnext">' + (forgeState.i === forgeState.list.length - 1 ? '结算' : '下一个') + '</button></div>';
      document.getElementById('fnext').addEventListener('click', function () {
        forgeState.i++; render(); window.scrollTo(0, 0);
      });
    }
    host.querySelectorAll('.opt').forEach(function (b) {
      b.addEventListener('click', function () {
        if (answered) return;
        var k = parseInt(b.getAttribute('data-k'), 10);
        finish(k === cur.q.a, k);
      });
    });
    forgeTimer = setInterval(function () {
      left--;
      if (bar) bar.style.width = Math.max(0, left / 20 * 100) + '%';
      if (num) num.textContent = left + 's';
      if (left <= 0) finish(false, -1);
    }, 1000);
  }

  /* ---------- 搜索 ---------- */
  function viewSearch() {
    var h = top('搜索', '全库检索', 1);
    h += '<div class="search"><span>🔍</span><input id="qin" placeholder="输入关键词：原子 / 熵 / 剩余价值 / 孙子…" autocomplete="off"></div>';
    h += '<div id="qres" class="mt"></div>';
    return h;
  }
  function doSearch(kw) {
    var host = document.getElementById('qres');
    if (!host) return;
    kw = (kw || '').trim().toLowerCase();
    if (!kw) { host.innerHTML = '<div class="empty">随便打两个字试试。<br>比如「能量」「资本」「谬误」。</div>'; return; }
    var hits = [];
    allLessons().forEach(function (x) {
      var blob = [x.l.title, x.l.essence, x.l.analogy, x.l.remember, x.m.name, x.m.tag,
        (x.l.steps || []).map(function (s) { return s.h + s.p; }).join(' '),
        (x.l.myths || []).map(function (m) { return m.q + m.a; }).join(' ') ].join(' ').toLowerCase();
      if (blob.indexOf(kw) >= 0) hits.push(x);
    });
    if (!hits.length) { host.innerHTML = '<div class="empty">没有命中。<br>换个更短的词试试。</div>'; return; }
    host.innerHTML = '<div class="tiny muted mb">命中 ' + hits.length + ' 课</div>' +
      hits.map(function (x) { return rowLesson(x.m, x.l, 1); }).join('');
    host.querySelectorAll('[data-act="lesson"]').forEach(function (b) {
      b.addEventListener('click', function () { nav({ n: 'lesson', id: b.getAttribute('data-id') }); });
    });
  }

  /* ---------- 我的 ---------- */
  function viewMe() {
    var total = lessonTotal(), ok = masteredCount(), read = readCount();
    var h = top('我的', '进度与铁血', 1);
    h += '<div class="stats">' +
      '<div class="stat"><b>' + ok + '</b><span>已掌握</span></div>' +
      '<div class="stat"><b>' + read + '</b><span>已读</span></div>' +
      '<div class="stat"><b>' + P.streak + '</b><span>连续天数</span></div>' +
      '</div>';
    h += '<div class="card mt"><div class="spread"><span class="tiny muted">总掌握度</span>' +
      '<span class="tiny" style="color:#f0d18a">' + Math.round(ok / Math.max(1, total) * 100) + '%</span></div>' +
      '<div class="mod" style="padding:10px 0 0;border:none;background:none">' +
      '<div class="bar"><i style="width:' + Math.round(ok / Math.max(1, total) * 100) + '%;background:linear-gradient(90deg,#c1933a,#f0d18a)"></i></div></div>' +
      '<div class="tiny muted mt">共 ' + total + ' 课。一天 3 课，' + Math.ceil((total - read) / 3) + ' 天能横扫一遍。</div></div>';

    h += '<div class="sec-title">各学科掌握</div><div class="card">';
    MODS.forEach(function (m) {
      var st = modStat(m);
      var pct = Math.round(st.pass / Math.max(1, st.total) * 100);
      h += '<div style="margin-bottom:11px"><div class="spread tiny"><span>' + m.icon + ' ' + esc(m.name) + '</span>' +
        '<span class="muted">' + st.pass + '/' + st.total + '</span></div>' +
        '<div class="bar" style="margin-top:5px"><i style="width:' + pct + '%;background:' + m.hue + '"></i></div></div>';
    });
    h += '</div>';

    h += '<div class="sec-title">铁血 · 写在最前面的话</div>' +
      '<div class="iron">' +
      '<h3>勇气不是不怕，是怕了还往前走</h3>' +
      '<p>你现在看不懂化学，不代表你笨。只代表<b>还没人用你听得懂的话讲给你听</b>。这一页里没有一门学科需要天赋，它们全都只需要你愿意再读一遍。</p>' +
      '<p>真正的分水岭从来不是智商，是<b>遇到不懂的时候，你选择关掉，还是选择多问一句"为什么"</b>。</p>' +
      '<p>每天三课，八周之后你会用一种新的眼睛看世界：看到盐会想到离子，看到新闻会想到利益结构，看到失败会想到概率。<br>这就是"读懂世界运行逻辑"的全部秘密——<b>它不神秘，它只是需要有人先帮你把门推开。</b></p>' +
      '<p style="margin-bottom:0"><b>保持血性。你自己的脑子，比任何结论都值钱。</b></p>' +
      '</div>';

    h += '<div class="sec-title">设置</div>';
    h += '<div class="card"><div class="tiny muted">进度保存在这台手机上，不联网、不上传。</div>' +
      '<div class="mt"><button class="btn block" data-act="reset">清空全部进度</button></div></div>';
    h += '<div class="center tiny muted mt" id="devInfo"></div>';
    h += '<div style="height:20px"></div>';
    return h;
  }

  /* ---------- 事件 ---------- */
  document.addEventListener('click', function (e) {
    var el = e.target.closest ? e.target.closest('[data-act]') : null;
    if (!el) return;
    var act = el.getAttribute('data-act');
    buzz(8);
    if (act === 'back') { window.__cosmosBack(); return; }
    if (act === 'mod') { nav({ n: 'mod', id: el.getAttribute('data-id') }); return; }
    if (act === 'lesson') { nav({ n: 'lesson', id: el.getAttribute('data-id') }); return; }
    if (act === 'list') { nav({ n: 'list' }); return; }
    if (act === 'retry') {
      var f = findLesson(el.getAttribute('data-id'));
      var end = document.getElementById('quizEnd'); if (end) end.innerHTML = '';
      var host = document.getElementById('quizBox');
      if (f && host) renderQuiz(host, f.l.id, f.l.quiz);
      return;
    }
    if (act === 'fold') {
      var db = el.parentNode.querySelector('.db');
      var open = db.style.display !== 'none';
      db.style.display = open ? 'none' : 'block';
      el.textContent = (open ? '▸ ' : '▾ ') + (open ? '展开这一段（不想看也能跳过）' : '收起');
      return;
    }
    if (act === 'forgeStart') {
      forgeState = { list: pickForge(8), i: 0, score: 0 };
      render(); window.scrollTo(0, 0); syncBack();
      return;
    }
    if (act === 'forgeExit') { forgeState = null; replaceRoot({ n: 'forge' }); return; }
    if (act === 'reset') {
      if (confirm('确定清空全部学习进度？')) {
        P = blank(); saveProgress();
        try { if (hasNative) Native.clear(); } catch (err) {}
        toast('已清空');
        replaceRoot({ n: 'home' });
      }
      return;
    }
  });

  document.addEventListener('input', function (e) {
    if (e.target && e.target.id === 'qin') doSearch(e.target.value);
  });

  /* ---------- 启动 ---------- */
  loadProgress();
  stack = [{ n: 'home' }];
  render();
  syncBack();
  try { if (typeof Native !== 'undefined' && Native.info) { var di = document.getElementById('devInfo'); } } catch (e) {}
})();
