/* ==================================================================
   SQL INJECTOR · 深空注入终端 — 前端控制逻辑
   ================================================================== */
(function () {
  'use strict';

  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ================================================================
     一、背景：星野 + 星云尘埃 + 数字雨
     ================================================================ */
  var starCanvas = document.getElementById('stars');
  var rainCanvas = document.getElementById('rain');
  var sctx = starCanvas.getContext('2d');
  var rctx = rainCanvas.getContext('2d');

  var W = 0, H = 0, DPR = 1;
  var stars = [];
  var shooting = null;
  var rainCols = [];
  var rainFont = 13;
  var GLYPHS = '01アイウエオカキクケコサシスセソタチツテトナニヌネノabcdef0123456789<>[]{}/\\|=+-*&%$#@!';

  function resize() {
    DPR = Math.min(window.devicePixelRatio || 1, 2);
    W = window.innerWidth;
    H = window.innerHeight;
    [starCanvas, rainCanvas].forEach(function (c) {
      c.width = Math.floor(W * DPR);
      c.height = Math.floor(H * DPR);
      c.style.width = W + 'px';
      c.style.height = H + 'px';
    });
    sctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    rctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    seedStars();
    seedRain();
  }

  function seedStars() {
    var count = Math.round(Math.min(420, (W * H) / 4200));
    stars = [];
    for (var i = 0; i < count; i++) {
      var depth = Math.random();
      stars.push({
        x: Math.random() * W,
        y: Math.random() * H,
        r: 0.35 + depth * 1.25,
        a: 0.18 + Math.random() * 0.72,
        tw: Math.random() * Math.PI * 2,
        tws: 0.4 + Math.random() * 1.6,
        vx: (Math.random() - 0.5) * (0.02 + depth * 0.10),
        vy: (Math.random() - 0.5) * (0.02 + depth * 0.10),
        hue: Math.random() < 0.12 ? 'violet' : (Math.random() < 0.2 ? 'magenta' : 'cyan')
      });
    }
  }

  function seedRain() {
    var cols = Math.ceil(W / 22);
    rainCols = [];
    for (var i = 0; i < cols; i++) {
      rainCols.push({
        x: i * 22 + 6,
        y: Math.random() * H,
        speed: 26 + Math.random() * 70,
        chars: [],
        len: 8 + Math.floor(Math.random() * 22)
      });
    }
  }

  function starColor(name, alpha) {
    if (name === 'violet') return 'rgba(157,107,255,' + alpha + ')';
    if (name === 'magenta') return 'rgba(255,79,216,' + alpha + ')';
    return 'rgba(190,238,255,' + alpha + ')';
  }

  var lastFrame = 0;
  var starPhase = 0;

  function drawStars(dt, t) {
    sctx.clearRect(0, 0, W, H);

    // 银河带：极淡的斜向光带
    var band = sctx.createLinearGradient(0, H * 0.15, W, H * 0.85);
    band.addColorStop(0, 'rgba(94,242,255,0)');
    band.addColorStop(0.42, 'rgba(94,242,255,0.030)');
    band.addColorStop(0.58, 'rgba(157,107,255,0.035)');
    band.addColorStop(1, 'rgba(157,107,255,0)');
    sctx.fillStyle = band;
    sctx.fillRect(0, 0, W, H);

    for (var i = 0; i < stars.length; i++) {
      var s = stars[i];
      s.x += s.vx * dt * 12;
      s.y += s.vy * dt * 12;
      if (s.x < -4) s.x = W + 4;
      if (s.x > W + 4) s.x = -4;
      if (s.y < -4) s.y = H + 4;
      if (s.y > H + 4) s.y = -4;

      var twinkle = 0.62 + 0.38 * Math.sin(t * s.tws + s.tw);
      var alpha = s.a * twinkle;
      sctx.beginPath();
      sctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      sctx.fillStyle = starColor(s.hue, alpha);
      sctx.fill();

      // 亮星带十字芒
      if (s.r > 1.15) {
        sctx.strokeStyle = starColor(s.hue, alpha * 0.42);
        sctx.lineWidth = 0.5;
        sctx.beginPath();
        sctx.moveTo(s.x - s.r * 2.6, s.y);
        sctx.lineTo(s.x + s.r * 2.6, s.y);
        sctx.moveTo(s.x, s.y - s.r * 2.6);
        sctx.lineTo(s.x, s.y + s.r * 2.6);
        sctx.stroke();
      }
    }

    // 流星
    if (!shooting && Math.random() < dt * 0.10) {
      shooting = {
        x: Math.random() * W * 0.8 + W * 0.1,
        y: Math.random() * H * 0.34,
        vx: 340 + Math.random() * 260,
        vy: 120 + Math.random() * 90,
        life: 0,
        max: 0.9 + Math.random() * 0.5
      };
    }
    if (shooting) {
      shooting.life += dt;
      shooting.x += shooting.vx * dt;
      shooting.y += shooting.vy * dt;
      var remain = 1 - shooting.life / shooting.max;
      if (remain <= 0) {
        shooting = null;
      } else {
        var tail = 130;
        var grad = sctx.createLinearGradient(
          shooting.x, shooting.y,
          shooting.x - shooting.vx * 0.16, shooting.y - shooting.vy * 0.16
        );
        grad.addColorStop(0, 'rgba(220,252,255,' + (0.85 * remain) + ')');
        grad.addColorStop(1, 'rgba(94,242,255,0)');
        sctx.strokeStyle = grad;
        sctx.lineWidth = 1.4;
        sctx.beginPath();
        sctx.moveTo(shooting.x, shooting.y);
        sctx.lineTo(shooting.x - shooting.vx * 0.14, shooting.y - shooting.vy * 0.10);
        sctx.stroke();
        sctx.beginPath();
        sctx.arc(shooting.x, shooting.y, 1.8, 0, Math.PI * 2);
        sctx.fillStyle = 'rgba(240,255,255,' + remain + ')';
        sctx.fill();
        void tail;
      }
    }
  }

  function drawRain(dt) {
    rctx.clearRect(0, 0, W, H);
    rctx.font = rainFont + 'px "Cascadia Mono", Consolas, monospace';
    rctx.textBaseline = 'top';

    for (var i = 0; i < rainCols.length; i++) {
      var col = rainCols[i];
      col.y += col.speed * dt;
      if (col.y - col.len * rainFont > H) {
        col.y = -Math.random() * H * 0.4;
        col.speed = 26 + Math.random() * 70;
      }
      for (var j = 0; j < col.len; j++) {
        var y = col.y - j * rainFont;
        if (y < -rainFont || y > H) continue;
        var ch = GLYPHS[(Math.floor((col.x + i + j + col.y * 0.01) ) + j * 7 + i * 13) % GLYPHS.length];
        var alpha = j === 0 ? 0.95 : Math.max(0, 0.55 - j / col.len * 0.6);
        rctx.fillStyle = j === 0
          ? 'rgba(190,252,255,' + alpha + ')'
          : 'rgba(94,242,255,' + alpha + ')';
        rctx.fillText(ch, col.x, y);
      }
    }
  }

  function loop(now) {
    var t = now / 1000;
    var dt = lastFrame ? Math.min(0.05, t - lastFrame) : 0.016;
    lastFrame = t;
    starPhase = t;
    drawStars(dt, t);
    if (!reduceMotion) drawRain(dt);
    requestAnimationFrame(loop);
  }

  window.addEventListener('resize', resize);
  if (reduceMotion) {
    resize();
    drawStars(0, 0);
    drawRain(0);
  } else {
    resize();
    requestAnimationFrame(loop);
  }

  /* ================================================================
     二、DOM 与工具
     ================================================================ */
  var $ = function (id) { return document.getElementById(id); };

  var el = {
    url: $('url'), cookie: $('cookie'), param: $('param'), delay: $('delay'),
    db: $('db'), allDb: $('allDb'),
    dumpDb: $('dumpDb'), table: $('table'), columns: $('columns'), limit: $('limit'),
    query: $('query'), forceBlind: $('forceBlind'),
    runBtn: $('runBtn'), stopBtn: $('stopBtn'),
    term: $('term'), intel: $('intel'), intelCount: $('intelCount'),
    rec: $('rec'), elapsed: $('elapsed'),
    clock: $('clock'), engineLed: $('engineLed'), engineText: $('engineText'),
    jobId: $('jobId'), jobMode: $('jobMode'), jobState: $('jobState'),
    modes: $('modes')
  };

  var state = {
    mode: 'detect',
    job: null,
    timer: null,
    pollTimer: null,
    startedAt: 0,
    renderedLines: [],
    lastLogLen: 0,
    running: false,
    reportShown: false,
    modeLabel: { detect: 'DETECT', enumerate: 'ENUMERATE', dump: 'DUMP', query: 'QUERY' }
  };

  function esc(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function pad(n) { return n < 10 ? '0' + n : '' + n; }

  function toast(message) {
    var node = document.querySelector('.toast');
    if (!node) {
      node = document.createElement('div');
      node.className = 'toast';
      document.body.appendChild(node);
    }
    node.textContent = message;
    node.classList.add('show');
    clearTimeout(node._timer);
    node._timer = setTimeout(function () { node.classList.remove('show'); }, 2600);
  }

  function api(action, options) {
    options = options || {};
    var url = 'sqlinjector.php?action=' + encodeURIComponent(action);
    if (options.job) url += '&job=' + encodeURIComponent(options.job);
    if (options.query) {
      Object.keys(options.query).forEach(function (key) {
        url += '&' + encodeURIComponent(key) + '=' + encodeURIComponent(options.query[key]);
      });
    }
    var init = { method: options.method || 'GET', cache: 'no-store' };
    if (options.body) {
      // 用表单编码提交：PHP 5.6 下 application/json 会触发
      // $HTTP_RAW_POST_DATA 弃用警告并污染 JSON 响应
      init.headers = { 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' };
      init.body = Object.keys(options.body).map(function (key) {
        return encodeURIComponent(key) + '=' + encodeURIComponent(options.body[key]);
      }).join('&');
    }
    return fetch(url, init).then(function (res) {
      return res.text().then(function (raw) {
        var data;
        try { data = JSON.parse(raw); } catch (e) { data = null; }
        if (!res.ok) {
          throw new Error((data && data.error) || ('HTTP ' + res.status));
        }
        if (data === null) throw new Error('响应解析失败');
        return data;
      });
    });
  }

  /* ================================================================
     三、终端输出
     ================================================================ */
  var MAX_LINES = 4000;
  var autoScroll = true;

  el.term.addEventListener('scroll', function () {
    var gap = el.term.scrollHeight - el.term.scrollTop - el.term.clientHeight;
    autoScroll = gap < 60;
  });

  function classify(line) {
    if (/^\[\*\]/.test(line)) return 'info';
    if (/^\[\+\]/.test(line)) return 'ok';
    if (/^\[!\]/.test(line)) return 'warn';
    if (/^\[-\]/.test(line)) return 'err';
    if (/^\[\.\]/.test(line)) return 'dbg';
    if (/^\[web\]/.test(line)) return 'sys';
    if (/^[╔║╚═]/.test(line)) return 'banner';
    if (/^\s*已读取\s\d+\/\d+/.test(line)) return 'live';
    return 'plain';
  }

  function makeLine(text) {
    var kind = classify(text);
    var div = document.createElement('div');
    div.className = 'term-line ' + kind;
    var prefix = '';
    var rest = text;
    var m = text.match(/^(\[\*\]|\[\+\]|\[!\]|\[-\]|\[\.\]|\[web\])\s?/);
    if (m) {
      prefix = m[1] + ' ';
      rest = text.slice(m[0].length);
    }
    if (prefix) {
      var span = document.createElement('span');
      span.className = 'pfx';
      span.textContent = prefix;
      div.appendChild(span);
    }
    div.appendChild(document.createTextNode(rest));
    div._text = text;
    return div;
  }

  function appendLines(lines) {
    var frag = document.createDocumentFragment();
    lines.forEach(function (line) {
      // 进度行（\r 覆盖式）直接替换上一条
      if (/^\s{2,}已读取\s/.test(line) && el.term.lastChild &&
          el.term.lastChild._text && /^\s{2,}已读取\s/.test(el.term.lastChild._text)) {
        el.term.lastChild.replaceWith(makeLine(line));
        return;
      }
      frag.appendChild(makeLine(line));
      state.renderedLines.push(line);
    });
    el.term.appendChild(frag);

    while (el.term.childElementCount > MAX_LINES) {
      el.term.removeChild(el.term.firstChild);
    }
    while (state.renderedLines.length > MAX_LINES) {
      state.renderedLines.shift();
    }
    if (autoScroll) el.term.scrollTop = el.term.scrollHeight;
  }

  function resetTerm() {
    el.term.innerHTML = '';
    state.renderedLines = [];
    state.lastLogLen = 0;
  }

  function renderLog(raw) {
    if (!raw) return;
    // PHP 截断提示：重置
    if (raw.indexOf('[... 日志过长') === 0) {
      resetTerm();
    }
    if (raw.length < state.lastLogLen) {
      resetTerm();
    }
    state.lastLogLen = raw.length;

    var all = raw.replace(/\r\n/g, '\n').split(/\n|\r/);
    // 去掉首部已被渲染的部分
    var fresh = all.slice(state.renderedLines.length);
    if (fresh.length) appendLines(fresh);
  }

  function termBoot() {
    var banner = [
      '╔══════════════════════════════════════════════════════════════╗',
      '║   S Q L   I N J E C T O R   ·   D E E P   S P A C E          ║',
      '║   GET 参数注入检测 / 元数据枚举 / 数据导出 · 仅限授权目标     ║',
      '╚══════════════════════════════════════════════════════════════╝'
    ];
    appendLines(banner);
    appendLines([
      '[*] 终端就绪，等待指令…',
      '[.] 快捷键：Ctrl + Enter 发起任务'
    ]);
  }

  /* ================================================================
     四、模式切换
     ================================================================ */
  el.modes.addEventListener('click', function (event) {
    var btn = event.target.closest('.mode');
    if (!btn || state.running) return;
    setMode(btn.getAttribute('data-mode'));
  });

  function setMode(mode) {
    state.mode = mode;
    Array.prototype.forEach.call(el.modes.querySelectorAll('.mode'), function (b) {
      b.classList.toggle('active', b.getAttribute('data-mode') === mode);
    });
    Array.prototype.forEach.call(document.querySelectorAll('.mode-fields'), function (block) {
      block.hidden = block.getAttribute('data-mode') !== mode;
    });
    el.jobMode.textContent = state.modeLabel[mode] || mode.toUpperCase();
  }

  /* ================================================================
     五、任务控制
     ================================================================ */
  function collect() {
    var body = {
      url: el.url.value.trim(),
      cookie: el.cookie.value.trim(),
      param: el.param.value.trim(),
      delay: parseFloat(el.delay.value) || 3,
      mode: state.mode,
      force_blind: el.forceBlind.checked
    };
    if (state.mode === 'enumerate') {
      body.db = el.db.value.trim();
      body.all_databases = el.allDb.checked;
    } else if (state.mode === 'dump') {
      body.db = el.dumpDb.value.trim();
      body.table = el.table.value.trim();
      body.columns = el.columns.value.trim();
      body.limit = parseInt(el.limit.value, 10) || 20;
    } else if (state.mode === 'query') {
      body.query = el.query.value.trim();
    }
    return body;
  }

  function setRunning(running) {
    state.running = running;
    el.runBtn.disabled = running;
    el.stopBtn.disabled = !running;
    document.body.classList.toggle('is-running', running);
    el.runBtn.querySelector('.btn-label').textContent = running ? 'SCANNING…' : 'INITIATE 扫描';
    el.rec.className = 'rec' + (running ? ' live' : '');
    el.rec.querySelector('b').textContent = running ? 'LIVE' : 'IDLE';
  }

  function startJob() {
    if (state.running) return;
    var body = collect();
    if (!body.url) { toast('请填写目标地址'); el.url.focus(); return; }
    if (body.mode === 'dump' && !body.table) { toast('导出模式需填写数据表'); el.table.focus(); return; }
    if (body.mode === 'query' && !body.query) { toast('查询模式需填写 SQL 表达式'); el.query.focus(); return; }

    resetTerm();
    state.reportShown = false;
    renderEmptyIntel('任务已启动 · SCANNING');
    el.term.classList.add('armed');

    appendLines([
      '[*] 发起任务：' + state.modeLabel[body.mode],
      '[*] 目标：' + body.url,
      '[*] 正在唤醒注入引擎…'
    ]);

    api('start', { method: 'POST', body: body }).then(function (data) {
      state.job = data.job;
      state.startedAt = Date.now();
      el.jobId.textContent = data.job;
      setRunning(true);
      setJobState('RUNNING', 'state-warn');
      el.rec.className = 'rec live';
      el.rec.querySelector('b').textContent = 'LIVE';
      appendLines(['[+] 引擎已启动 · JOB ' + data.job + ' · PID ' + data.pid]);
      startPolling();
    }).catch(function (err) {
      setRunning(false);
      appendLines(['[-] 启动失败：' + err.message]);
      toast('启动失败：' + err.message);
      setJobState('ERROR', 'state-err');
    });
  }

  function startPolling() {
    stopPolling();
    state.pollTimer = setInterval(poll, 900);
    poll();
    startClock();
  }

  function stopPolling() {
    if (state.pollTimer) { clearInterval(state.pollTimer); state.pollTimer = null; }
  }

  function startClock() {
    if (state.timer) clearInterval(state.timer);
    state.timer = setInterval(function () {
      if (!state.running) return;
      var seconds = Math.floor((Date.now() - state.startedAt) / 1000);
      el.elapsed.textContent = pad(Math.floor(seconds / 60)) + ':' + pad(seconds % 60);
    }, 500);
  }

  var pollFailures = 0;

  function poll() {
    if (!state.job) return;
    api('poll', { job: state.job }).then(function (data) {
      pollFailures = 0;
      renderLog(data.log || '');
      if (data.status === 'running') {
        el.rec.className = 'rec live';
        el.rec.querySelector('b').textContent = 'LIVE';
      } else {
        finish(data);
      }
    }).catch(function (err) {
      pollFailures++;
      if (pollFailures === 3) appendLines(['[!] 轮询异常：' + err.message]);
      if (pollFailures > 12) {
        stopPolling();
        appendLines(['[-] 与引擎失联，已停止轮询']);
        setRunning(false);
        setJobState('LOST', 'state-err');
      }
    });
  }

  function finish(data) {
    stopPolling();
    if (state.timer) { clearInterval(state.timer); state.timer = null; }
    setRunning(false);

    var status = data.status;
    var exit = data.exit;
    renderLog(data.log || '');

    if (status === 'done') {
      el.rec.className = 'rec done';
      el.rec.querySelector('b').textContent = 'COMPLETE';
      setJobState('COMPLETE', 'state-ok');
      appendLines(['[+] 任务结束 · 退出码 ' + exit + ' · 用时 ' + el.elapsed.textContent]);
    } else if (status === 'clean') {
      el.rec.className = 'rec error';
      el.rec.querySelector('b').textContent = 'NO SIGNAL';
      setJobState('CLEAN', 'state-warn');
      appendLines(['[!] 任务结束：未发现注入 · 退出码 ' + exit]);
    } else if (status === 'stopped') {
      el.rec.className = 'rec';
      el.rec.querySelector('b').textContent = 'ABORTED';
      setJobState('ABORTED', 'state-warn');
      appendLines(['[!] 任务被中断']);
    } else if (status === 'lost') {
      el.rec.className = 'rec error';
      el.rec.querySelector('b').textContent = 'LOST';
      setJobState('LOST', 'state-err');
      appendLines(['[-] 引擎进程丢失（可能被系统终止）']);
    } else {
      el.rec.className = 'rec error';
      el.rec.querySelector('b').textContent = 'ERROR';
      setJobState('ERROR', 'state-err');
      appendLines(['[-] 任务异常 · 退出码 ' + exit]);
    }

    loadReport();
  }

  function setJobState(text, cls) {
    el.jobState.textContent = text;
    el.jobState.className = cls || '';
  }

  function stopJob() {
    if (!state.job || !state.running) return;
    appendLines(['[!] 正在中止任务…']);
    api('stop', { job: state.job }).then(function () {
      appendLines(['[!] 已发送中断信号']);
    }).catch(function (err) {
      appendLines(['[-] 中止失败：' + err.message]);
    });
  }

  el.runBtn.addEventListener('click', startJob);
  el.stopBtn.addEventListener('click', stopJob);

  document.addEventListener('keydown', function (event) {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault();
      if (!state.running) startJob();
    }
  });

  /* ================================================================
     六、情报面板
     ================================================================ */
  function renderEmptyIntel(text) {
    el.intel.innerHTML = '<div class="empty"><span class="pulse-dot"></span>' +
      esc(text || '等待遥测数据 · AWAITING TELEMETRY') + '</div>';
    el.intelCount.textContent = '';
  }

  function loadReport() {
    if (!state.job) return;
    api('report', { job: state.job }).then(function (data) {
      if (!data.report) {
        if (!state.reportShown) {
          renderEmptyIntel('本次任务未生成报告');
        }
        return;
      }
      state.reportShown = true;
      renderReport(data.report, data.csv || []);
    }).catch(function (err) {
      appendLines(['[!] 报告读取失败：' + err.message]);
    });
  }

  function renderReport(report, csvFiles) {
    var findings = report.findings || {};
    var steps = report.steps || [];
    var html = [];

    var ok = !!report.vulnerable;
    html.push(
      '<div class="hero' + (ok ? '' : ' bad') + '">' +
        '<div class="hero-badge">' + (ok ? '◈' : '✕') + '</div>' +
        '<div><h3>' + (ok ? '注入确认 · INJECTION CONFIRMED' : '未发现注入 · NO INJECTION') + '</h3>' +
        '<p>' + esc(report.target || '') + '</p></div>' +
      '</div>'
    );

    var scalarKeys = ['注入参数', '检测手法', '闭合引号', '数据库类型', '当前数据库'];
    var kv = scalarKeys.filter(function (key) {
      return findings[key] !== undefined && findings[key] !== null && findings[key] !== '';
    });
    if (kv.length) {
      html.push('<div class="intel-section"><h4>目标情报</h4><div class="kv">');
      kv.forEach(function (key) {
        html.push('<div class="kv-item"><b>' + esc(key) + '</b><span>' + esc(findings[key]) + '</span></div>');
      });
      html.push('</div></div>');
    }

    var dbs = findings['数据库列表'];
    if (Array.isArray(dbs) && dbs.length) {
      var current = findings['当前数据库'];
      html.push('<div class="intel-section"><h4>数据库 · ' + dbs.length + '</h4><div class="chips">');
      dbs.forEach(function (db) {
        html.push('<span class="chip' + (db === current ? ' current' : '') + '">' + esc(db) + '</span>');
      });
      html.push('</div></div>');
    }

    var custom = findings['自定义查询'];
    if (custom && typeof custom === 'object') {
      html.push('<div class="intel-section"><h4>表达式结果</h4><div class="kv">');
      Object.keys(custom).forEach(function (key) {
        html.push('<div class="kv-item"><b>' + esc(key) + '</b><span>' + esc(custom[key]) + '</span></div>');
      });
      html.push('</div></div>');
    }

    var schema = findings['表结构'];
    if (schema && typeof schema === 'object') {
      html.push(renderSchema(schema));
    }

    var dump = findings['导出'];
    if (dump && typeof dump === 'object') {
      html.push(
        '<div class="intel-section"><h4>数据导出</h4><div class="kv">' +
        '<div class="kv-item"><b>数据库</b><span>' + esc(dump.database) + '</span></div>' +
        '<div class="kv-item"><b>数据表</b><span>' + esc(dump.table) + '</span></div>' +
        '<div class="kv-item"><b>行数</b><span>' + esc(dump.rows) + '</span></div>' +
        '<div class="kv-item"><b>列</b><span>' + esc((dump.columns || []).join(', ')) + '</span></div>' +
        '</div></div>'
      );
    }

    if (steps.length) {
      html.push('<div class="intel-section"><h4>行动轨迹</h4><ul class="steps">');
      steps.forEach(function (step) {
        var detail = step.detail;
        if (detail && typeof detail === 'object') detail = JSON.stringify(detail);
        html.push('<li><b>' + esc(step.name) + '</b><span>' + esc(detail) + '</span></li>');
      });
      html.push('</ul></div>');
    }

    if (csvFiles.length) {
      html.push('<div class="intel-section"><h4>战利品</h4><div class="exports">');
      csvFiles.forEach(function (file) {
        html.push('<a class="dl" href="sqlinjector.php?action=download&job=' +
          encodeURIComponent(state.job) + '&file=' + encodeURIComponent(file) + '">' +
          '<span>⤓</span>' + esc(file) + '</a>');
      });
      html.push('</div></div>');
    }

    el.intel.innerHTML = html.join('');
    bindSchemaToggles();

    var count = 0;
    if (Array.isArray(dbs)) count += dbs.length;
    if (schema) {
      Object.keys(schema).forEach(function (db) {
        count += Object.keys(schema[db] || {}).length;
      });
    }
    el.intelCount.textContent = count ? count + ' ITEMS' : '';
  }

  function renderSchema(schema) {
    var html = ['<div class="intel-section"><h4>表结构 · SCHEMA</h4>'];
    Object.keys(schema).forEach(function (db, index) {
      var tables = schema[db] || {};
      var names = Object.keys(tables);
      var collapsed = index > 0 ? ' collapsed' : '';
      html.push('<div class="db-block' + collapsed + '">');
      html.push('<button type="button" class="db-head">' +
        '<span class="db-name">' + esc(db) + '</span>' +
        '<span class="db-meta">' + names.length + ' TABLES</span>' +
        '<span class="chev"></span></button>');
      html.push('<div class="db-body">');
      if (!names.length) {
        html.push('<div class="tbl-empty">无表或无权限</div>');
      }
      names.forEach(function (name) {
        var table = tables[name] || {};
        var cols = table.columns || [];
        var meta = [];
        if (table.engine) meta.push('引擎 ' + table.engine);
        if (table.rows) meta.push(table.rows + ' 行');
        html.push('<div class="tbl-block">');
        html.push('<div class="tbl-head"><b>' + esc(name) + '</b><em>' +
          esc(meta.join(' · ') || 'N/A') + '</em><em>' + cols.length + ' 列</em></div>');
        if (!cols.length) {
          html.push('<div class="tbl-empty">未取得字段信息</div>');
        } else {
          html.push('<div class="tbl-scroll"><table class="cols"><thead><tr>' +
            '<th>列名</th><th>类型</th><th>键</th><th>默认</th><th>额外</th><th>备注</th>' +
            '</tr></thead><tbody>');
          cols.forEach(function (col) {
            var tags = '';
            if (col.key === 'PRI') tags += '<span class="tag pri">PRI</span>';
            else if (col.key) tags += '<span class="tag pri">' + esc(col.key) + '</span>';
            if (String(col.nullable).toUpperCase() === 'NO') tags += '<span class="tag nn">NN</span>';
            html.push('<tr>' +
              '<td class="name">' + esc(col.name) + '</td>' +
              '<td>' + esc(col.type || '-') + '</td>' +
              '<td>' + (tags || '<span class="dim">—</span>') + '</td>' +
              '<td>' + (col.default ? esc(col.default) : '<span class="dim">—</span>') + '</td>' +
              '<td>' + (col.extra ? esc(col.extra) : '<span class="dim">—</span>') + '</td>' +
              '<td>' + (col.comment ? esc(col.comment) : '<span class="dim">—</span>') + '</td>' +
              '</tr>');
          });
          html.push('</tbody></table></div>');
        }
        html.push('</div>');
      });
      html.push('</div></div>');
    });
    html.push('</div>');
    return html.join('');
  }

  function bindSchemaToggles() {
    Array.prototype.forEach.call(el.intel.querySelectorAll('.db-head'), function (head) {
      head.addEventListener('click', function () {
        head.parentNode.classList.toggle('collapsed');
      });
    });
  }

  /* ================================================================
     七、HUD 时钟 & 引擎自检
     ================================================================ */
  function tickClock() {
    var now = new Date();
    el.clock.textContent =
      pad(now.getHours()) + ':' + pad(now.getMinutes()) + ':' + pad(now.getSeconds()) +
      ' UTC' + (now.getTimezoneOffset() <= 0 ? '+' : '-') +
      pad(Math.abs(now.getTimezoneOffset() / 60));
  }
  tickClock();
  setInterval(tickClock, 1000);

  api('ping').then(function (data) {
    if (data.ok) {
      el.engineLed.className = 'led ok';
      el.engineText.textContent = 'ENGINE ONLINE';
      appendLines(['[+] 注入引擎在线 · ' + (data.python || 'Python')]);
    } else {
      el.engineLed.className = 'led err';
      el.engineText.textContent = 'ENGINE OFFLINE';
      appendLines(['[-] 注入引擎离线：请检查 venv 与 web_runner.py']);
    }
  }).catch(function () {
    el.engineLed.className = 'led err';
    el.engineText.textContent = 'ENGINE OFFLINE';
  });

  /* ================================================================
     八、启动
     ================================================================ */
  setMode('detect');
  termBoot();
  setJobState('STANDBY', '');
})();
