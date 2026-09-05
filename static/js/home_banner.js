/* Home announcement banner + bell history (home page only).
 * - Banner: first live unacknowledged announcement, expandable long text,
 *   dismiss button (persists via per-ID ack, shared with announcements.js).
 * - Bell (right side): unread count + history panel, newest first
 *   (from /api/announcements?history=1), each dismissible.
 * Honors the Settings master switch; works offline from cached feed.
 */
(function () {
  'use strict';

  var ACK_PREFIX = 'ligtasph_ann_ack_';
  var ENABLED_KEY = 'ligtasph_ann_enabled';
  var CITY_KEY = 'ligtasph_ann_city_v1';
  var POS_KEY = 'ligtasph_ann_pos_v1';
  var CACHE_KEY = 'ligtasph_ann_cache_v1';

  function P() { return window.LigtasPrefs || null; }
  function store(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function isAcked(id) { try { return !!localStorage.getItem(ACK_PREFIX + id); } catch (e) { return false; } }
  function setAcked(id) { try { localStorage.setItem(ACK_PREFIX + id, new Date().toISOString()); } catch (e) {} }
  function unack(ids) {
    try { (ids || []).forEach(function (id) { localStorage.removeItem(ACK_PREFIX + id); }); } catch (e) {}
  }
  var undoTimer = null;
  // 10-second undo after any dismiss: restores the ack keys, then repaints.
  function showUndo(ids, label) {
    var toast = document.getElementById('ann-undo');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'ann-undo';
      toast.className = 'card';
      toast.setAttribute('role', 'status');
      toast.innerHTML = '<span id="ann-undo-msg"></span><button id="ann-undo-btn" class="btn btn-primary" style="padding:10px 16px; font-size:13px; min-height:44px;">Undo</button>';
      document.body.appendChild(toast);
      toast.querySelector('#ann-undo-btn').addEventListener('click', function () {
        var back = toast._ids || [];
        toast.hidden = true;
        toast._ids = null;
        if (undoTimer) { clearTimeout(undoTimer); undoTimer = null; }
        unack(back);
        loadLive().then(renderBanner);
        refreshBadge();
        if (!document.getElementById('ann-history').hidden) loadHistory();
      });
    }
    toast._ids = ids || [];
    toast.querySelector('#ann-undo-msg').textContent = label || 'Dismissed.';
    toast.hidden = false;
    if (undoTimer) clearTimeout(undoTimer);
    undoTimer = setTimeout(function () { toast.hidden = true; toast._ids = null; undoTimer = null; }, 10000);
  }
  function enabled() {
    var p = P();
    if (p) return p.announcementsEnabled();
    return store(ENABLED_KEY) !== '0';
  }
  function nowMs() { return Date.now(); }
  function parseTime(s) {
    if (!s) return NaN;
    return Date.parse(String(s).replace(' ', 'T') + (/Z|\+/.test(String(s)) ? '' : 'Z'));
  }
  function inWindow(a) {
    var s = parseTime(a.starts_at), e = parseTime(a.ends_at);
    if (isNaN(s) || isNaN(e)) return true;
    return s <= nowMs() && nowMs() <= e;
  }
  function fmtRange(a) {
    // "2026-09-05 15:31:00" (UTC) -> "Sep 5, 3:31PM PHT"
    function pht(s) {
      var t = parseTime(s);
      if (isNaN(t)) return String(s || '').slice(0, 16);
      var d = new Date(t + 8 * 3600 * 1000);
      var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
      var h = d.getUTCHours(), ap = h >= 12 ? 'PM' : 'AM';
      h = h % 12 || 12;
      var m = ('0' + d.getUTCMinutes()).slice(-2);
      return months[d.getUTCMonth()] + ' ' + d.getUTCDate() + ', ' + h + ':' + m + ap + ' PHT';
    }
    return pht(a.starts_at) + ' → ' + pht(a.ends_at);
  }
  function scopeLabel(a) {
    if (a.scope === 'city') return 'For ' + (a.city || '');
    if (a.scope === 'radius') return 'For your area';
    return 'Everyone';
  }
  function sevColor(a) {
    return a.severity === 'critical' ? 'var(--red)' : a.severity === 'warning' ? 'var(--orange)' : 'var(--primary)';
  }

  function query(extra) {
    var q = extra ? [extra] : [];
    var city = store(CITY_KEY);
    if (city) q.push('city=' + encodeURIComponent(city));
    try {
      var p = JSON.parse(store(POS_KEY) || 'null');
      if (p && p.lat != null && p.lon != null) {
        q.push('lat=' + encodeURIComponent(p.lat));
        q.push('lon=' + encodeURIComponent(p.lon));
      }
    } catch (e) {}
    return q.length ? '?' + q.join('&') : '';
  }
  function getJSON(url) {
    return fetch(url, { headers: { Accept: 'application/json' } }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    });
  }

  var liveCache = null;

  function loadLive() {
    return getJSON('/api/announcements' + query()).then(function (data) {
      if (Array.isArray(data)) {
        liveCache = data;
        try { localStorage.setItem(CACHE_KEY, JSON.stringify({ at: new Date().toISOString(), items: data })); } catch (e) {}
      }
      return Array.isArray(data) ? data : [];
    }, function () {
      if (liveCache) return liveCache;
      try {
        var c = JSON.parse(store(CACHE_KEY) || 'null');
        var items = Array.isArray(c) ? c : ((c && c.items) || []);
        return items.filter(inWindow);
      } catch (e) { return []; }
    });
  }

  /* ---------- banner ---------- */
  function renderBanner(list) {
    var bar = document.getElementById('home-ann-banner');
    if (!bar) return;
    var next = (list || []).filter(function (a) { return a && a.id != null && !isAcked(a.id) && inWindow(a); })[0];
    if (!next || !enabled()) { bar.hidden = true; return; }
    bar.hidden = false;
    bar.className = 'card sev-' + (next.severity || 'info');
    bar.id = 'home-ann-banner';
    var critical = next.severity === 'critical';
    bar.setAttribute('role', critical ? 'alert' : 'status');
    var dot = document.getElementById('home-ann-dot');
    dot.style.background = sevColor(next);
    dot.setAttribute('aria-label', 'Severity: ' + (next.severity || 'info'));
    document.getElementById('home-ann-title').textContent = next.title || 'Announcement';
    var sevChip = document.getElementById('home-ann-sev');
    sevChip.textContent = critical ? 'Critical alert' : next.severity === 'warning' ? 'Warning' : 'Notice';
    sevChip.className = 'badge ' + (critical ? 'badge-full' : next.severity === 'warning' ? 'badge-nearly' : 'badge-unknown');
    sevChip.style.fontSize = '10px';
    var m = document.getElementById('home-ann-msg');
    m.textContent = next.message || '';
    // Critical alerts are never truncated; others clamp to one line with
    // the expander shown only on real overflow (measured, not guessed).
    m.classList.toggle('clamped', !critical);
    var exp = document.getElementById('home-ann-expand');
    exp.hidden = true;
    requestAnimationFrame(function () {
      var over = !critical && m.scrollHeight > m.clientHeight + 1;
      exp.hidden = !over;
      if (!over) m.classList.remove('clamped');
    });
    exp.textContent = 'Show more';
    exp.onclick = function () {
      var cl = m.classList.toggle('clamped');
      exp.textContent = cl ? 'Show more' : 'Show less';
    };
    document.getElementById('home-ann-meta').textContent = scopeLabel(next) + ' • ' + fmtRange(next);
    document.getElementById('home-ann-dismiss').onclick = function () {
      setAcked(next.id);
      renderBanner(list.filter(function (a) { return a.id !== next.id; }));
      refreshBadge();
      showUndo([next.id], 'Banner dismissed.');
    };
  }

  /* ---------- bell + history ---------- */
  function refreshBadge() {
    var badge = document.getElementById('ann-bell-count');
    if (!badge) return;
    loadLive().then(function (list) {
      var n = list.filter(function (a) { return a && !isAcked(a.id) && inWindow(a); }).length;
      badge.hidden = !(enabled() && n > 0);
      badge.textContent = n > 9 ? '9+' : String(n);
    });
  }

  function renderHistory(list) {
    var box = document.getElementById('ann-history-items');
    box.innerHTML = '';
    if (!list.length) {
      box.innerHTML = '<p style="color:var(--text-secondary); font-size:13px;">No announcements yet.</p>';
      return;
    }
    list.forEach(function (a) {
      var item = document.createElement('div');
      item.className = 'ann-hist-item' + (isAcked(a.id) ? ' is-dismissed' : '');
      var dot = document.createElement('span');
      dot.className = 'ann-hist-dot';
      dot.style.background = sevColor(a);
      dot.setAttribute('aria-label', 'Severity: ' + (a.severity || 'info'));
      dot.setAttribute('role', 'img');
      var body = document.createElement('div');
      body.style.cssText = 'flex:1; min-width:0;';
      var head = document.createElement('div');
      head.style.cssText = 'font-weight:700; font-size:13px;';
      head.textContent = (a.title || 'Announcement') + ' — ' + (a.severity === 'critical' ? 'Critical' : a.severity === 'warning' ? 'Warning' : 'Notice');
      var txt = document.createElement('div');
      txt.style.cssText = 'font-size:13px; margin-top:2px;';
      txt.textContent = a.message || '';
      var meta = document.createElement('div');
      meta.style.cssText = 'font-size:11px; color:var(--text-secondary); margin-top:4px;';
      meta.textContent = (a.expired ? 'Expired • ' : '') + scopeLabel(a) + ' • ' + fmtRange(a);
      body.appendChild(head);
      body.appendChild(txt);
      body.appendChild(meta);
      item.appendChild(dot);
      item.appendChild(body);
      if (!isAcked(a.id)) {
        var b = document.createElement('button');
        b.className = 'btn btn-secondary';
        b.style.cssText = 'padding:10px 14px; font-size:13px; min-height:44px; flex:0 0 auto; align-self:start;';
        b.textContent = 'Dismiss';
        b.addEventListener('click', function () {
          setAcked(a.id);
          loadHistory();
          loadLive().then(renderBanner);
          refreshBadge();
          showUndo([a.id], 'Announcement dismissed.');
        });
        item.appendChild(b);
      }
      box.appendChild(item);
    });
  }

  function loadHistory() {
    var box = document.getElementById('ann-history-items');
    getJSON('/api/announcements' + query('history=1')).then(function (data) {
      renderHistory(Array.isArray(data) ? data : []);
    }, function () {
      box.innerHTML = '<p style="color:var(--text-secondary); font-size:13px;">Offline — history unavailable.</p>';
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (!document.getElementById('home-ann-banner')) return; // home only
    loadLive().then(function (list) { renderBanner(list); refreshBadge(); });
    var bell = document.getElementById('ann-bell');
    var panel = document.getElementById('ann-history');
    bell.addEventListener('click', function () {
      var open = panel.hidden;
      panel.hidden = !open;
      bell.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (open) {
        loadHistory();
        var first = panel.querySelector('button');
        if (first) first.focus();
      }
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !panel.hidden) {
        panel.hidden = true;
        bell.setAttribute('aria-expanded', 'false');
        bell.focus();
      }
    });
    document.getElementById('ann-dismiss-all').addEventListener('click', function () {
      if (!confirm('Dismiss all announcements, including critical ones?')) return;
      loadLive().then(function (list) {
        var ids = list.filter(function (a) { return a && a.id != null; }).map(function (a) { return a.id; });
        ids.forEach(setAcked);
        renderBanner([]);
        refreshBadge();
        loadHistory();
        showUndo(ids, ids.length + ' announcement(s) dismissed.');
      });
    });
  });
})();
