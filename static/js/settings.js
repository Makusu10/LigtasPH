/* Settings page controller — all prefs stay on-device (see prefs.js). */
(function () {
  'use strict';

  function P() { return window.LigtasPrefs; }
  function el(id) { return document.getElementById(id); }
  function msg(id, text) { var m = el(id); if (m) m.textContent = text || ''; }

  /* ---- Appearance ---- */
  function paintThemeSeg() {
    var cur = 'system';
    try { cur = localStorage.getItem('ligtasph_theme') || 'system'; } catch (e) {}
    Array.prototype.forEach.call(document.querySelectorAll('#themeSeg [data-theme-opt]'), function (b) {
      var on = b.getAttribute('data-theme-opt') === cur;
      b.classList.toggle('btn-primary', on);
      b.classList.toggle('btn-secondary', !on);
      b.setAttribute('aria-checked', on ? 'true' : 'false');
    });
  }

  /* ---- Location ---- */
  function savedPosText() {
    try {
      var raw = localStorage.getItem('ligtasph_ann_pos_v1');
      if (!raw) return 'none';
      var p = JSON.parse(raw);
      return Number(p.lat).toFixed(4) + ', ' + Number(p.lon).toFixed(4);
    } catch (e) { return 'none'; }
  }
  function refreshGeoUI() {
    el('savedPos').textContent = savedPosText();
    var st = el('geoState');
    try {
      if (navigator.permissions && navigator.permissions.query) {
        navigator.permissions.query({ name: 'geolocation' }).then(function (r) {
          st.textContent = r.state;
          if (r.onchange !== undefined) r.onchange = refreshGeoUI;
        }, function () { st.textContent = 'unknown'; });
      } else st.textContent = 'unknown (browser has no permission API)';
    } catch (e) { st.textContent = 'unknown'; }
  }

  /* ---- Providers / build id ---- */
  function loadStatus() {
    fetch('/api/status', { headers: { Accept: 'application/json' } }).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    }).then(function (s) {
      var row = el('provRow');
      row.innerHTML = '';
      var items = [
        ['OpenWeather', s.providers && s.providers.openweather],
        ['Open-Meteo fallback', s.providers && s.providers.open_meteo],
        ['Mapbox maps', s.providers && s.providers.mapbox],
        ['FIRMS fires', s.providers && s.providers.firms]
      ];
      items.forEach(function (it) {
        var b = document.createElement('span');
        b.className = 'badge ' + (it[1] ? 'badge-available' : 'badge-unknown');
        b.textContent = (it[1] ? '● ' : '○ ') + it[0];
        row.appendChild(b);
      });
      if (s.build_id) {
        el('buildId').textContent = String(s.build_id).replace('T', ' ').slice(0, 16) + ' UTC';
        if (P()) P().checkBuildId(s.build_id);
      }
    }, function () {
      el('provRow').innerHTML = '<span class="badge badge-unknown">offline — cannot reach server</span>';
    });
  }

  /* ---- City options (same source as directory) ---- */
  function loadCities() {
    var sel = el('setCity');
    var cur = '';
    try { cur = localStorage.getItem('ligtasph_ann_city_v1') || ''; } catch (e) {}
    fetch('/api/centers?sort=name&limit=1000', { headers: { Accept: 'application/json' } }).then(function (r) {
      return r.ok ? r.json() : [];
    }).then(function (centers) {
      var cities = [];
      (centers || []).forEach(function (c) { if (c.city && cities.indexOf(c.city) < 0) cities.push(c.city); });
      cities.sort();
      cities.forEach(function (ci) {
        var o = document.createElement('option');
        o.value = ci; o.textContent = ci;
        if (ci === cur) o.selected = true;
        sel.appendChild(o);
      });
    }, function () {});
    sel.addEventListener('change', function () {
      try { localStorage.setItem('ligtasph_ann_city_v1', sel.value || ''); } catch (e) {}
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (!P()) return;
    paintThemeSeg();
    Array.prototype.forEach.call(document.querySelectorAll('#themeSeg [data-theme-opt]'), function (b) {
      b.addEventListener('click', function () { P().setTheme(b.getAttribute('data-theme-opt')); paintThemeSeg(); });
    });

    el('geoUse').addEventListener('click', function () {
      msg('geoMsg', '');
      if (!('geolocation' in navigator)) { msg('geoMsg', 'Geolocation not supported — type a start point on the map instead.'); return; }
      msg('geoMsg', 'Locating…');
      navigator.geolocation.getCurrentPosition(function (pos) {
        try {
          localStorage.setItem('ligtasph_ann_pos_v1', JSON.stringify({
            lat: pos.coords.latitude, lon: pos.coords.longitude, at: new Date().toISOString()
          }));
        } catch (e) {}
        msg('geoMsg', 'Saved.');
        refreshGeoUI();
      }, function (err) {
        msg('geoMsg', err && err.code === 1
          ? 'Blocked — allow location in the browser site settings (lock icon in the address bar), then try again.'
          : 'Could not get a fix. Try again outdoors or enter manually.');
        refreshGeoUI();
      }, { maximumAge: 60000, timeout: 10000 });
    });
    el('geoClear').addEventListener('click', function () {
      try { localStorage.removeItem('ligtasph_ann_pos_v1'); } catch (e) {}
      msg('geoMsg', 'Saved location cleared. Radius-targeted alerts are off until you set one.');
      refreshGeoUI();
    });
    refreshGeoUI();

    var tgl = el('annToggle');
    function paintAnn() {
      var on = P().announcementsEnabled();
      tgl.textContent = 'Popups: ' + (on ? 'On' : 'Off');
      tgl.classList.toggle('btn-primary', on);
      tgl.classList.toggle('btn-secondary', !on);
      tgl.setAttribute('aria-pressed', on ? 'true' : 'false');
    }
    tgl.addEventListener('click', function () {
      P().setAnnouncementsEnabled(!P().announcementsEnabled());
      paintAnn();
    });
    paintAnn();
    el('annReshow').addEventListener('click', function () {
      var n = P().resetAcknowledged();
      msg('wipeMsg', '');
      alert(n ? n + ' dismissed banner(s) will show again.' : 'Nothing dismissed — no banners to re-show.');
    });

    el('wipeCache').addEventListener('click', function () {
      P().clearServerCaches();
      try { localStorage.removeItem('ligtasph_build_id_v1'); } catch (e) {}
      msg('wipeMsg', 'Cached feeds cleared. They reload on next visit.');
    });

    loadCities();
    loadStatus();

    // Staff entry: tap the about line 5 times within 3s to reveal sign-in.
    // (Admin Login was removed from the public nav on purpose.)
    (function () {
      var taps = 0, timer = null;
      var line = document.getElementById('aboutTap');
      var btn = document.getElementById('staffBtn');
      if (!line || !btn) return;
      line.addEventListener('click', function () {
        taps++;
        if (timer) clearTimeout(timer);
        if (taps >= 5) {
          taps = 0;
          btn.hidden = false;
          btn.style.display = '';
          return;
        }
        timer = setTimeout(function () { taps = 0; }, 3000);
      });
    })();
  });
})();
