/* LigtasPH shared preferences — single source of truth over localStorage.
 * Keys are shared with announcements.js, directory/hotlines city filters.
 * All prefs are per-device and work offline. No server round-trip needed
 * except the build-id check (server restarts invalidate cached feeds).
 */
(function (global) {
  'use strict';

  var K = {
    theme: 'ligtasph_theme',            // 'light' | 'dark' | 'system'
    annEnabled: 'ligtasph_ann_enabled', // '0' = popups off, missing = on
    city: 'ligtasph_ann_city_v1',
    pos: 'ligtasph_ann_pos_v1',
    annCache: 'ligtasph_ann_cache_v1',
    buildId: 'ligtasph_build_id_v1'
  };

  function get(key, fallback) {
    try {
      var v = global.localStorage.getItem(key);
      return v === null ? fallback : v;
    } catch (e) { return fallback; }
  }
  function set(key, value) {
    try {
      if (value === null || value === undefined) global.localStorage.removeItem(key);
      else global.localStorage.setItem(key, value);
    } catch (e) {}
  }
  function remove(key) {
    try { global.localStorage.removeItem(key); } catch (e) {}
  }

  function systemDark() {
    try {
      return !!(global.matchMedia && global.matchMedia('(prefers-color-scheme: dark)').matches);
    } catch (e) { return false; }
  }
  function effectiveTheme() {
    var t = get(K.theme, 'system');
    if (t === 'dark') return 'dark';
    if (t === 'light') return 'light';
    return systemDark() ? 'dark' : 'light';
  }
  function applyTheme() {
    try {
      var doc = global.document;
      if (!doc || !doc.documentElement) return;
      doc.documentElement.setAttribute('data-theme', effectiveTheme());
    } catch (e) {}
  }
  function setTheme(mode) {
    if (mode !== 'light' && mode !== 'dark') mode = 'system';
    set(K.theme, mode);
    applyTheme();
  }

  function announcementsEnabled() {
    return get(K.annEnabled, '1') !== '0';
  }
  function setAnnouncementsEnabled(on) {
    set(K.annEnabled, on ? '1' : '0');
  }
  // Re-show previously dismissed banners (clears per-ID acks, keeps the
  // master switch and everything else).
  function resetAcknowledged() {
    try {
      var drop = [];
      for (var i = 0; i < global.localStorage.length; i++) {
        var k = global.localStorage.key(i);
        if (k && k.indexOf('ligtasph_ann_ack_') === 0) drop.push(k);
      }
      drop.forEach(function (k) { global.localStorage.removeItem(k); });
      return drop.length;
    } catch (e) { return 0; }
  }
  function clearServerCaches() {
    remove(K.annCache);
  }
  // After a server restart/update, drop stale server-data caches but keep
  // real user prefs (theme, city, master switch). Returns true on change.
  function checkBuildId(buildId) {
    if (!buildId) return false;
    var prev = get(K.buildId, null);
    if (prev === buildId) return false;
    clearServerCaches();
    set(K.buildId, buildId);
    return prev !== null; // false on first-ever visit (nothing stale)
  }

  // Apply ASAP (also called from the sync head snippet to avoid FOUC).
  applyTheme();
  try {
    if (global.matchMedia) {
      var mq = global.matchMedia('(prefers-color-scheme: dark)');
      var onChange = function () { if (get(K.theme, 'system') === 'system') applyTheme(); };
      if (mq.addEventListener) mq.addEventListener('change', onChange);
      else if (mq.addListener) mq.addListener(onChange);
    }
  } catch (e) {}

  global.LigtasPrefs = {
    KEYS: K, get: get, set: set, remove: remove,
    effectiveTheme: effectiveTheme, applyTheme: applyTheme, setTheme: setTheme,
    announcementsEnabled: announcementsEnabled,
    setAnnouncementsEnabled: setAnnouncementsEnabled,
    resetAcknowledged: resetAcknowledged,
    clearServerCaches: clearServerCaches,
    checkBuildId: checkBuildId
  };
})(window);
