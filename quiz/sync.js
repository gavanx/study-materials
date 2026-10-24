/**
 * 云同步（腾讯云开发 CloudBase）
 *
 * 设计：本地优先 + 事件日志。
 * - 做题/收藏先写 localStorage，立即生效；
 * - 同时追加一条事件到云端（失败就进本地队列，联网后重试）；
 * - 打开页面时拉取同一「家庭口令」下的事件，合并回本地。
 *
 * 事件模型（集合 quiz_events）：
 *   { family, kind: 'done'|'wrong'|'fav'|'unfav', qid, date, ok, ts, uid }
 * 合并规则：done 每天取最早一条；wrong 按次数累计；fav/unfav 取时间最新的一条。
 */
(function () {
  'use strict';

  const CFG = (window.QUIZ_CONFIG || {}).cloudbase || {};
  const SDK_URLS = [
    'https://static.cloudbase.net/cloudbase-js-sdk/2.17.3/cloudbase.full.js',
    'https://static.cloudbase.net/cloudbase-js-sdk/latest/cloudbase.full.js'
  ];
  const FAMILY_KEY = 'quiz_family';
  const QUEUE_KEY = 'quiz_sync_queue';

  const state = {
    configured: !!(CFG.envId && CFG.accessKey),
    ready: false,
    syncing: false,
    error: '',
    uid: '',
    family: readLS(FAMILY_KEY) || ''
  };
  let app = null;
  let db = null;
  const listeners = new Set();

  /* ---------- 基础工具 ---------- */
  function readLS(k) {
    try { return localStorage.getItem(k) || ''; } catch (e) { return ''; }
  }
  function writeLS(k, v) {
    try { localStorage.setItem(k, v); } catch (e) { /* 隐私模式忽略 */ }
  }
  function notify() {
    listeners.forEach(fn => { try { fn(snapshot()); } catch (e) { /* noop */ } });
  }
  function snapshot() {
    return {
      configured: state.configured,
      ready: state.ready,
      syncing: state.syncing,
      error: state.error,
      family: state.family
    };
  }
  function queue() {
    try { return JSON.parse(readLS(QUEUE_KEY) || '[]'); } catch (e) { return []; }
  }
  function saveQueue(arr) {
    try { localStorage.setItem(QUEUE_KEY, JSON.stringify(arr.slice(-500))); } catch (e) { /* noop */ }
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src;
      s.onload = resolve;
      s.onerror = () => reject(new Error('加载 SDK 失败: ' + src));
      document.head.appendChild(s);
    });
  }

  async function ensureSdk() {
    if (window.cloudbase) return;
    for (const url of SDK_URLS) {
      try { await loadScript(url); if (window.cloudbase) return; } catch (e) { /* 试下一个 */ }
    }
    throw new Error('CloudBase SDK 加载失败，请检查网络');
  }

  /* ---------- 初始化 ---------- */
  async function init() {
    if (!state.configured) { notify(); return snapshot(); }
    state.syncing = true; notify();
    try {
      await ensureSdk();
      app = window.cloudbase.init({
        env: CFG.envId,
        region: CFG.region || 'ap-shanghai',
        accessKey: CFG.accessKey,
        auth: { detectSessionInUrl: true }
      });
      const auth = app.auth;
      const session = auth.getSession && (await auth.getSession());
      if (!session || !session.data || !session.data.session) {
        const res = await auth.signInAnonymously();
        if (res && res.error) throw new Error(res.error.message || '匿名登录失败');
      }
      const session2 = await auth.getSession();
      state.uid = (session2 && session2.data && session2.data.session && session2.data.session.user
        && session2.data.session.user.uid) || '';
      db = app.database();
      state.ready = true;
      state.error = '';
      if (!state.family) setFamily(genCode(), { silent: true });
    } catch (e) {
      state.error = e.message || String(e);
      state.ready = false;
    } finally {
      state.syncing = false;
      notify();
    }
    return snapshot();
  }

  /* ---------- 家庭口令 ---------- */
  function genCode() {
    const abc = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    let out = '';
    const buf = new Uint8Array(10);
    (window.crypto || window.msCrypto).getRandomValues(buf);
    for (let i = 0; i < buf.length; i++) out += abc[buf[i] % abc.length];
    return out;
  }
  function setFamily(code, opts) {
    state.family = String(code || '').trim().toUpperCase();
    writeLS(FAMILY_KEY, state.family);
    if (!opts || !opts.silent) notify();
  }

  /* ---------- 写事件 ---------- */
  function normalizeAdd(dbRef, doc) {
    // 不同版本 SDK 的 add 参数形态不同：v1 直接传对象，v2 可能要 {data}
    try {
      const p = dbRef.add(doc);
      if (p && typeof p.then === 'function') return p;
    } catch (e) { /* 走下面的形态 */ }
    return dbRef.add({ data: doc });
  }

  async function push(evt) {
    const full = Object.assign({ family: state.family, ts: Date.now(), uid: state.uid }, evt);
    if (!state.ready || !db || !state.family) {
      saveQueue(queue().concat(full));
      return false;
    }
    try {
      await normalizeAdd(db.collection(CFG.collection || 'quiz_events'), full);
      return true;
    } catch (e) {
      state.error = '写入失败：' + (e.message || e);
      saveQueue(queue().concat(full));
      notify();
      return false;
    }
  }

  async function flushQueue() {
    const q = queue();
    if (!q.length || !state.ready) return;
    const rest = [];
    for (const evt of q) {
      try {
        await normalizeAdd(db.collection(CFG.collection || 'quiz_events'), evt);
      } catch (e) { rest.push(evt); }
    }
    saveQueue(rest);
    if (rest.length !== q.length) notify();
  }

  /* ---------- 读事件 ---------- */
  function rowsOf(res) {
    if (!res) return [];
    const d = res.data;
    if (Array.isArray(d)) return d;
    if (d && Array.isArray(d.list)) return d.list;
    if (d && d.data && Array.isArray(d.data)) return d.data;
    return [];
  }

  async function pullAll(maxPages) {
    if (!state.ready || !db || !state.family) return [];
    const coll = db.collection(CFG.collection || 'quiz_events');
    const pageSize = 100;
    const out = [];
    for (let page = 0; page < (maxPages || 10); page++) {
      let res;
      try {
        res = await coll.where({ family: state.family })
          .orderBy('ts', 'asc').skip(page * pageSize).limit(pageSize).get();
      } catch (e) {
        state.error = '读取失败：' + (e.message || e);
        notify();
        break;
      }
      const rows = rowsOf(res);
      out.push.apply(out, rows);
      if (rows.length < pageSize) break;
    }
    return out;
  }

  /* ---------- 合并 ---------- */
  // 把云端事件合并进本地三本账，返回 {progress, wrong, fav} 合并后的对象
  function merge(local, events) {
    const progress = Object.assign({}, local.progress || {});
    const wrong = Object.assign({}, local.wrong || {});
    const fav = Object.assign({}, local.fav || {});

    events.forEach(ev => {
      if (!ev || !ev.kind) return;
      if (ev.kind === 'done' && ev.date && !progress[ev.date]) {
        progress[ev.date] = { qid: ev.qid, ok: !!ev.ok, ts: ev.ts };
      } else if (ev.kind === 'wrong' && ev.qid) {
        const cur = wrong[ev.qid];
        if (!cur) wrong[ev.qid] = { ts: ev.ts, times: 1 };
        else if (ev.ts > cur.ts) { cur.times = (cur.times || 1) + 1; cur.ts = ev.ts; }
      } else if (ev.kind === 'fav' && ev.qid) {
        if (!fav[ev.qid] || ev.ts > (fav[ev.qid].ts || 0)) fav[ev.qid] = { ts: ev.ts };
      } else if (ev.kind === 'unfav' && ev.qid) {
        if (fav[ev.qid] && ev.ts >= (fav[ev.qid].ts || 0)) delete fav[ev.qid];
      }
    });
    return { progress, wrong, fav };
  }

  async function syncDown() {
    if (!state.ready) return null;
    state.syncing = true; notify();
    try {
      await flushQueue();
      const events = await pullAll();
      state.error = '';
      return events;
    } finally {
      state.syncing = false;
      notify();
    }
  }

  window.QuizSync = {
    init,
    push,
    syncDown,
    flushQueue,
    pullAll,
    merge,
    status: snapshot,
    onChange(fn) { listeners.add(fn); return () => listeners.delete(fn); },
    getFamily: () => state.family,
    setFamily,
    genCode
  };
})();
