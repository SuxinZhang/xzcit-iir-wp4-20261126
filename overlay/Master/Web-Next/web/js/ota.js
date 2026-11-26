/* =====================================================================
 * C50C ota.js - WP6 management UI for offline OTA packages and rollback.
 * C50C ota.js - WP6 离线上传升级包与回滚管理界面逻辑。
 * ===================================================================== */
(function () {
  'use strict';
  var C = (window.C50C = window.C50C || {});
  var state = { active: false, ws: null, timer: 0, packageId: '', busy: false };

  function $(id) { return document.getElementById(id); }
  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (ch) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch];
    });
  }
  function setText(id, value) { var el = $(id); if (el) el.textContent = value; }
  function percentText(value) { return String(Math.max(0, Math.min(100, Number(value) || 0))) + '%'; }

  function renderStatus(data) {
    var versions = data.versions || {};
    setText('ota-fw-version', versions.firmware || '—');
    setText('ota-master-version', versions.master || '—');
    setText('ota-model-version', versions.model || '—');
    var list = $('ota-interlocks');
    if (list) {
      list.innerHTML = (data.interlocks || []).map(function (item) {
        return '<li class="' + (item.passed ? 'ok' : 'bad') + '"><b>' + esc(item.lock_id) +
          ' ' + esc(item.name) + '</b><span>' + esc(item.detail) + '</span></li>';
      }).join('');
    }
    var allGreen = (data.interlocks || []).length === 5 && data.interlocks.every(function (i) { return i.passed; });
    var apply = $('ota-apply-btn');
    if (apply) { apply.disabled = !allGreen || state.busy || !state.packageId; }
    setText('ota-busy', data.busy ? '升级进行中' : '空闲');
  }

  function refresh() {
    fetch('/api/ota/status').then(function (r) { return r.ok ? r.json() : {}; })
      .then(renderStatus).catch(function () { setText('ota-busy', 'OTA 代理离线'); });
  }

  function upload(file) {
    if (!file || !/\.tar\.gz$/i.test(file.name)) { setText('ota-upload-result', '请选择 .tar.gz 离线包'); return; }
    var form = new FormData(); form.append('file', file);
    setText('ota-upload-result', '正在预检…');
    fetch('/api/ota/upload', { method: 'POST', body: form })
      .then(function (r) { return r.json().then(function (b) { if (!r.ok) throw new Error(b.detail || r.status); return b; }); })
      .then(function (preview) {
        state.packageId = preview.package_id;
        setText('ota-upload-result', '预检通过：' + preview.release_version + ' / ' + Object.keys(preview.artifacts || {}).join(', '));
        refresh();
      }).catch(function (error) { setText('ota-upload-result', '预检失败：' + error.message); });
  }

  function apply() {
    if (!state.packageId || state.busy) return;
    if (!window.confirm('确认开始 OTA 升级？升级期间请勿断电。')) return;
    state.busy = true;
    fetch('/api/ota/apply', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ package_id: state.packageId, scope: 'all' }) })
      .then(function (r) { return r.json().then(function (b) { if (!r.ok) throw new Error(b.detail && b.detail.message ? b.detail.message : (b.detail || r.status)); return b; }); })
      .then(function (job) { setText('ota-log', JSON.stringify(job, null, 2)); state.busy = false; refresh(); })
      .catch(function (error) { setText('ota-log', '升级失败：' + error.message); state.busy = false; refresh(); });
  }

  function rollback() {
    if (!window.confirm('确认回滚到上一版本？')) return;
    fetch('/api/ota/rollback', { method: 'POST' }).then(function (r) { return r.json(); })
      .then(function (job) { setText('ota-log', JSON.stringify(job, null, 2)); refresh(); })
      .catch(function (error) { setText('ota-log', '回滚失败：' + error.message); });
  }

  function connectWs() {
    if (state.ws) return;
    var socket;
    try { socket = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws/ota/progress'); } catch (e) { return; }
    state.ws = socket;
    socket.onmessage = function (event) {
      var message; try { message = JSON.parse(event.data); } catch (e) { return; }
      if (message.t === 'ota_progress' || message.t === 'ota_status') {
        setText('ota-progress', percentText(message.percent));
        setText('ota-stage', message.stage || '—');
        var bar = $('ota-progress-bar'); if (bar) bar.style.width = percentText(message.percent);
        if (message.job) setText('ota-log', JSON.stringify(message.job, null, 2));
      }
    };
    socket.onclose = function () { state.ws = null; if (state.active) setTimeout(connectWs, 2000); };
    socket.onerror = function () { try { socket.close(); } catch (e) { /* ignore */ } };
  }

  function bind() {
    var input = $('ota-file'); if (input) input.addEventListener('change', function () { upload(input.files[0]); });
    var applyBtn = $('ota-apply-btn'); if (applyBtn) applyBtn.addEventListener('click', apply);
    var rollbackBtn = $('ota-rollback-btn'); if (rollbackBtn) rollbackBtn.addEventListener('click', rollback);
    var drop = $('ota-drop'); if (drop) {
      drop.addEventListener('dragover', function (e) { e.preventDefault(); });
      drop.addEventListener('drop', function (e) { e.preventDefault(); if (e.dataTransfer.files.length) upload(e.dataTransfer.files[0]); });
    }
  }

  function setPage(page) {
    var active = page === 'ota';
    if (active === state.active) return;
    state.active = active;
    if (active) { refresh(); connectWs(); state.timer = setInterval(refresh, 5000); }
    else { clearInterval(state.timer); state.timer = 0; if (state.ws) { try { state.ws.close(); } catch (e) {} state.ws = null; } }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bind); else bind();
  C.OTA = { setPage: setPage, refresh: refresh, upload: upload, apply: apply, rollback: rollback };
})();
