/* LigtasPH mass banner announcements — offline-capable popup.
 * - Fetches /api/announcements (with city + geolocation when available)
 * - Caches last good feed in localStorage; on fetch failure (offline),
 *   falls back to cache and filters by time window client-side.
 * - Shows a blocking modal popup; "Acknowledge" stores per-ID ack in
 *   localStorage so it disappears and stays dismissed for that banner.
 */
(function () {
  'use strict';
  var CACHE_KEY = 'ligtasph_ann_cache_v1';
  var POS_KEY = 'ligtasph_ann_pos_v1';
  var CITY_KEY = 'ligtasph_ann_city_v1';

  function ackKey(id) { return 'ligtasph_ann_ack_' + id; }
  function isAcked(id) {
    try { return !!localStorage.getItem(ackKey(id)); } catch (e) { return false; }
  }
  function setAcked(id) {
    try { localStorage.setItem(ackKey(id), new Date().toISOString()); } catch (e) {}
  }
  function nowMs() { return Date.now(); }
  function parseTime(s) {
    if (!s) return NaN;
    var t = Date.parse(String(s).replace(' ', 'T') + (String(s).indexOf('Z') >= 0 || String(s).indexOf('+') >= 0 ? '' : 'Z'));
    return t;
  }
  function inWindow(a) {
    var t = nowMs(), s = parseTime(a.starts_at), e = parseTime(a.ends_at);
    if (isNaN(s) || isNaN(e)) return true; // server already filtered; be permissive
    return s <= t && t <= e;
  }
  function getPos() {
    try {
      var raw = localStorage.getItem(POS_KEY);
      if (raw) { var p = JSON.parse(raw); if (p && p.lat) return p; }
    } catch (e) {}
    return null;
  }
  function getCity() {
    try { return localStorage.getItem(CITY_KEY) || ''; } catch (e) { return ''; }
  }
  // Refresh cached geolocation quietly (best-effort, never blocks banner).
  function refreshPos() {
    if (!('geolocation' in navigator)) return;
    try {
      navigator.geolocation.getCurrentPosition(function (pos) {
        try {
          localStorage.setItem(POS_KEY, JSON.stringify({
            lat: pos.coords.latitude, lon: pos.coords.longitude, at: new Date().toISOString()
          }));
        } catch (e) {}
      }, function () {}, { maximumAge: 3600000, timeout: 5000 });
    } catch (e) {}
  }

  function fetchLive() {
    var pos = getPos(), city = getCity();
    var q = [];
    if (city) q.push('city=' + encodeURIComponent(city));
    if (pos && pos.lat != null && pos.lon != null) {
      q.push('lat=' + encodeURIComponent(pos.lat));
      q.push('lon=' + encodeURIComponent(pos.lon));
    }
    var url = '/api/announcements' + (q.length ? '?' + q.join('&') : '');
    return fetch(url, { headers: { Accept: 'application/json' } }).then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.json();
    }).then(function (data) {
      if (Array.isArray(data)) {
        try { localStorage.setItem(CACHE_KEY, JSON.stringify({ at: new Date().toISOString(), items: data })); } catch (e) {}
      }
      return data;
    });
  }
  function loadCache() {
    try {
      var raw = localStorage.getItem(CACHE_KEY);
      if (!raw) return [];
      var c = JSON.parse(raw);
      var items = Array.isArray(c) ? c : (c.items || []);
      return items.filter(inWindow);
    } catch (e) { return []; }
  }

  var SEV_STYLE = {
    info: { bar: '#3b6ef5', bg: 'rgba(239,246,255,0.95)', border: 'rgba(178,221,255,0.8)', text: '#1849A9' },
    warning: { bar: '#e08a0e', bg: 'rgba(255,250,235,0.95)', border: 'rgba(254,223,137,0.8)', text: '#7A4D07' },
    critical: { bar: '#D92D20', bg: 'rgba(254,243,242,0.97)', border: 'rgba(254,205,202,0.9)', text: '#7A271A' }
  };

  function ensureStyles() {
    if (document.getElementById('ann-style')) return;
    var s = document.createElement('style');
    s.id = 'ann-style';
    s.textContent = [
      '#ann-modal-overlay{position:fixed;inset:0;background:rgba(16,24,40,0.45);backdrop-filter:blur(4px);z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px;}',
      '#ann-modal{background:var(--surface,#fff);color:var(--text,#1b2330);border-radius:16px;max-width:480px;width:100%;box-shadow:0 20px 60px rgba(0,0,0,0.25);overflow:hidden;border:1px solid var(--glass-border,transparent);}',
      '#ann-modal-head{height:6px;}',
      '#ann-modal-body{padding:20px;}',
      '#ann-modal h2{margin:0 0 8px;font-size:18px;}',
      '#ann-modal p{margin:0 0 6px;font-size:14px;line-height:1.5;}',
      '#ann-modal-meta{font-size:12px;color:var(--text-secondary,#5f6b7a);margin-top:8px;}',
      '#ann-topbar{position:sticky;top:64px;z-index:1060;margin-bottom:12px;border-radius:12px;padding:10px 14px;font-size:13px;display:flex;gap:10px;align-items:center;justify-content:space-between;border:1px solid;}'
    ].join('\n');
    document.head.appendChild(s);
  }

  function showModal(a) {
    if (document.getElementById('ann-modal-overlay')) return;
    ensureStyles();
    var sev = SEV_STYLE[a.severity] || SEV_STYLE.info;
    var ov = document.createElement('div');
    ov.id = 'ann-modal-overlay';
    ov.setAttribute('role', 'alertdialog');
    ov.setAttribute('aria-modal', 'true');
    ov.setAttribute('aria-label', a.title || 'Announcement');
    ov.innerHTML =
      '<div id="ann-modal">' +
        '<div id="ann-modal-head" style="background:' + sev.bar + '"></div>' +
        '<div id="ann-modal-body">' +
          '<h2></h2><p class="ann-msg"></p>' +
          '<div id="ann-modal-meta"></div>' +
          '<button id="ann-ack" class="btn btn-primary" style="width:100%;margin-top:14px;">Acknowledge</button>' +
        '</div>' +
      '</div>';
    ov.querySelector('h2').textContent = a.title || 'Announcement';
    ov.querySelector('.ann-msg').textContent = a.message || '';
    var meta = [];
    if (a.severity === 'critical') meta.push('Critical notice');
    if (a.scope && a.scope !== 'all') meta.push(a.scope === 'city' ? ('For ' + (a.city || '')) : 'For your area');
    if (a.ends_at) meta.push('Until ' + String(a.ends_at).replace('T', ' ').slice(0, 16) + ' UTC');
    ov.querySelector('#ann-modal-meta').textContent = meta.join(' • ');
    ov.querySelector('#ann-ack').textContent = 'Acknowledge';
    ov.querySelector('#ann-ack').addEventListener('click', function () {
      setAcked(a.id);
      ov.remove();
      showNext();
    });
    // Non-critical modals are Esc-dismissable (critical requires acknowledge).
    if (a.severity !== 'critical') {
      ov.querySelector('#ann-ack').addEventListener('keydown', function (e) {
        if (e && (e.key === 'Escape' || e.key === 'Esc')) {
          setAcked(a.id);
          ov.remove();
          showNext();
        }
      });
    }
    // Critical popups require acknowledge — no overlay-click dismiss.
    document.body.appendChild(ov);
    ov.querySelector('#ann-ack').focus();
  }

  function showTopbar(a) {
    if (document.getElementById('ann-topbar')) return;
    ensureStyles();
    var sev = SEV_STYLE[a.severity] || SEV_STYLE.info;
    var bar = document.createElement('div');
    bar.id = 'ann-topbar';
    bar.setAttribute('role', 'status');
    bar.style.background = sev.bg;
    bar.style.borderColor = sev.border;
    bar.style.color = sev.text;
    var span = document.createElement('span');
    var st = document.createElement('strong');
    st.textContent = a.title || 'Announcement';
    var sm = document.createElement('span');
    sm.textContent = ' — ' + (a.message || '');
    span.appendChild(st);
    span.appendChild(sm);
    var btn = document.createElement('button');
    btn.className = 'btn btn-secondary';
    btn.style.cssText = 'padding:6px 12px;font-size:12px;flex:0 0 auto;min-height:44px;';
    btn.textContent = 'Acknowledge';
    btn.addEventListener('click', function () { setAcked(a.id); bar.remove(); showNext(); });
    bar.appendChild(span);
    bar.appendChild(btn);
    var container = document.querySelector('.container');
    if (container && container.parentNode) container.parentNode.insertBefore(bar, container);
    else document.body.insertBefore(bar, document.body.firstChild);
  }

  var queue = [];
  function showNext() {
    var pending = queue.filter(function (a) { return !isAcked(a.id); });
    queue = pending;
    if (!pending.length) return;
    var a = pending[0];
    if (a.severity === 'critical') showModal(a);
    else if (!document.getElementById('ann-modal-overlay')) showModal(a);
    // Non-critical also uses the modal (per spec: popup until acknowledged);
    // topbar is reserved for future non-blocking use.
  }

  function run(list) {
    queue = (Array.isArray(list) ? list : []).filter(function (a) {
      return a && a.id != null && !isAcked(a.id) && inWindow(a);
    });
    noteSeen(queue);
    showNext();
  }

  // IDs already shown this session — used to spot genuinely new banners
  // arriving between syncs (vs. ones the user already saw/dismissed).
  var seenIds = {};
  function noteSeen(list) {
    (list || []).forEach(function (a) { if (a && a.id != null) seenIds[a.id] = 1; });
  }

  // Background sync: revalidate the feed every SYNC_MS while visible.
  // A brand-new critical banner interrupts with a modal (emergency use);
  // new non-critical ones wait silently in queue for the next navigation.
  function syncTick() {
    if (!popupsEnabled()) return;
    if (document.getElementById('ann-modal-overlay')) return; // don't stack
    fetchLive().then(function (data) {
      var fresh = (Array.isArray(data) ? data : []).filter(function (a) {
        return a && a.id != null && !isAcked(a.id) && inWindow(a);
      });
      var crit = null, i, a;
      for (i = 0; i < fresh.length; i++) {
        a = fresh[i];
        if (!seenIds[a.id] && a.severity === 'critical' && !crit) crit = a;
      }
      noteSeen(fresh);
      queue = fresh;
      if (crit) showModal(crit);
    }, function () {});
  }

  function syncMs() {
    try {
      if (window.LigtasPrefs && window.LigtasPrefs.SYNC_MS) return window.LigtasPrefs.SYNC_MS;
    } catch (e) {}
    return 5 * 60 * 1000;
  }

  // Master kill-switch from Settings (LigtasPrefs may load after us —
  // both scripts are deferred in order, but read live to be safe).
  function popupsEnabled() {
    try {
      if (window.LigtasPrefs) return window.LigtasPrefs.announcementsEnabled();
      return localStorage.getItem('ligtasph_ann_enabled') !== '0';
    } catch (e) { return true; }
  }

  document.addEventListener('DOMContentLoaded', function () {
    // Skip on admin pages so editors aren't interrupted while publishing.
    if (window.location.pathname.indexOf('/admin') === 0) return;
    // Skip on home: the banner + bell replace the modal there.
    if (document.getElementById('home-ann-banner')) return;
    // Skip on the map: fullbleed map chrome (zoom controls, dock, sheet)
    // must never be covered — announcements live on the home tab.
    if (document.querySelector('.map-shell')) return;
    if (!popupsEnabled()) return;
    refreshPos();
    fetchLive().then(run, function () { run(loadCache()); });
    // Keep the feed in sync while the tab stays open (SYNC_MS cadence).
    try {
      if (window.LigtasPrefs && window.LigtasPrefs.everyVisible) {
        window.LigtasPrefs.everyVisible(syncMs(), syncTick);
      } else {
        setInterval(function () {
          if (!document.hidden) { try { syncTick(); } catch (e) {} }
        }, syncMs());
      }
    } catch (e) {}
  });
})();
