/* =====================================================================
 * C50C inspection.js - WP4 inspection centre: capture, defects, history.
 * C50C inspection.js - WP4 巡检中心：抓拍、缺陷研判与历史回看。
 * The module is independent from the chassis control loop; it only talks
 * to the standalone inspection gateway on port 8089.
 * 本模块独立于底盘控制链路，仅访问 8089 端口上的独立巡检业务网关。
 * ===================================================================== */
(function () {
  'use strict';
  var C = (window.C50C = window.C50C || {});
  var state = { active: false, ws: null, timer: 0, busy: false, history: [] };

  function $(id) { return document.getElementById(id); }

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (ch) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch];
    });
  }

  /** Resolve the gateway origin while keeping deployment override options.
   *  解析网关来源地址，同时保留部署时的覆盖选项。 */
  function gatewayBase() {
    var param = null;
    try { param = new URLSearchParams(location.search).get('gateway'); } catch (e) { /* ignore */ }
    if (param) return param.replace(/\/+$/, '');
    try {
      var saved = localStorage.getItem('iir-gateway');
      if (saved) return saved.replace(/\/+$/, '');
    } catch (e) { /* storage disabled */ }
    return location.protocol + '//' + location.hostname + ':8089';
  }

  function wsBase() { return gatewayBase().replace(/^http/, 'ws'); }

  function severityText(value) {
    return { none: '正常', low: '低', medium: '中', high: '高' }[value] || value || '—';
  }

  function fmtTime(value) {
    if (!value) return '—';
    var moment = new Date(value);
    return isNaN(moment.getTime()) ? String(value) : moment.toLocaleString();
  }

  function setStatus(text, kind) {
    var el = $('ins-status');
    if (!el) return;
    el.textContent = text;
    el.className = 'st' + (kind === 'ok' ? ' ok-t' : kind === 'bad' ? ' bad-t'
      : kind === 'warn' ? ' warn-t' : '');
  }

  function setText(id, text) { var el = $(id); if (el) el.textContent = text; }

  function renderDefects(defects) {
    var list = $('ins-defects');
    if (!list) return;
    if (!defects || !defects.length) {
      list.innerHTML = '<li class="st">未发现缺陷</li>';
      setText('ins-count', '0 项');
      return;
    }
    list.innerHTML = defects.map(function (item) {
      var name = item.display_name || item.label || '缺陷';
      var confidence = typeof item.confidence === 'number'
        ? (item.confidence * 100).toFixed(1) + '%' : '—';
      return '<li><b>' + esc(name) + '</b><span class="mono">' + confidence
        + '</span><span class="chip">' + esc(item.label || '') + '</span></li>';
    }).join('');
    setText('ins-count', defects.length + ' 项');
  }

  function renderRecord(record) {
    if (!record || !record.capture_id) return;
    var image = $('ins-image');
    var empty = $('ins-empty');
    var meta = $('ins-meta');
    var url = record.annotated_url || record.image_url;
    if (image && url) {
      image.src = gatewayBase() + url;
      image.hidden = false;
      if (empty) empty.hidden = true;
    }
    if (meta) {
      meta.hidden = false;
      meta.textContent = fmtTime(record.created_at) + ' · '
        + (record.inspection_point || '未指定点位') + ' · ' + severityText(record.severity);
    }
    renderDefects(record.defects || []);
  }

  function renderHistory(items) {
    state.history = items || [];
    var list = $('ins-history');
    if (!list) return;
    if (!state.history.length) {
      list.innerHTML = '<li class="st">暂无记录</li>';
      return;
    }
    list.innerHTML = state.history.map(function (item) {
      return '<li data-id="' + esc(item.capture_id) + '">'
        + '<b class="mono">' + esc(fmtTime(item.created_at)) + '</b>'
        + '<span>' + esc(item.inspection_point || '未指定点位') + '</span>'
        + '<span class="st">' + (item.defect_count || 0) + ' 项 · '
        + esc(severityText(item.severity)) + '</span></li>';
    }).join('');
  }

  function refreshHistory() {
    return fetch(gatewayBase() + '/api/inspection/history?limit=20')
      .then(function (response) { return response.ok ? response.json() : { items: [] }; })
      .then(function (data) { renderHistory((data && data.items) || []); })
      .catch(function () { /* keep the previous history on transient errors */ });
  }

  function refreshHealth() {
    return fetch(gatewayBase() + '/healthz')
      .then(function (response) { return response.ok ? response.json() : {}; })
      .then(function (data) {
        var backend = (data && data.backend) || {};
        setText('ins-health', '网关 ' + (backend.ready ? '在线' : '离线')
          + ' · ' + (backend.backend || '—'));
      })
      .catch(function () { setText('ins-health', '网关离线'); });
  }

  function refresh() {
    fetch(gatewayBase() + '/api/inspection/latest')
      .then(function (response) { return response.ok ? response.json() : {}; })
      .then(function (data) { if (data && data.capture_id) renderRecord(data); })
      .catch(function () { /* keep the last card while offline */ });
    refreshHistory();
    refreshHealth();
  }

  function capture() {
    if (state.busy) return;
    var button = $('ins-capture-btn');
    var point = $('ins-point');
    state.busy = true;
    if (button) button.disabled = true;
    setStatus('抓拍中…', 'warn');
    fetch(gatewayBase() + '/api/inspection/capture', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        inspection_point: point ? point.value.trim() : '',
        source: 'manual',
        archive: true,
      }),
    }).then(function (response) {
      return response.json().then(function (body) {
        if (!response.ok) throw new Error((body && body.detail) || ('HTTP ' + response.status));
        return body;
      });
    }).then(function (record) {
      renderRecord(record);
      setStatus('抓拍完成', 'ok');
      refreshHistory();
    }).catch(function (error) {
      setStatus('抓拍失败：' + error.message, 'bad');
    }).then(function () {
      state.busy = false;
      if (button) button.disabled = false;
    });
  }

  function connectWs() {
    if (state.ws) return;
    var socket;
    try { socket = new WebSocket(wsBase() + '/ws/inspection'); } catch (e) { return; }
    state.ws = socket;
    socket.onmessage = function (event) {
      var message;
      try { message = JSON.parse(event.data); } catch (e) { return; }
      if (message.t === 'inspection_snapshot') {
        if (message.items && message.items[0]) renderRecord(message.items[0]);
      } else if (message.t === 'inspection_alert') {
        renderRecord(message.record);
        refreshHistory();
      }
    };
    socket.onclose = function () {
      state.ws = null;
      if (state.active) setTimeout(connectWs, 2000);
    };
    socket.onerror = function () { try { socket.close(); } catch (e) { /* ignore */ } };
  }

  function closeWs() {
    if (state.ws) {
      try { state.ws.close(); } catch (e) { /* ignore */ }
      state.ws = null;
    }
  }

  function setPage(page) {
    var active = page === 'inspection';
    if (active === state.active) return;
    state.active = active;
    if (active) {
      refresh();
      connectWs();
      state.timer = setInterval(refresh, 5000);
    } else {
      clearInterval(state.timer);
      state.timer = 0;
      closeWs();
    }
  }

  function bind() {
    var button = $('ins-capture-btn');
    if (button) button.addEventListener('click', capture);
    var point = $('ins-point');
    if (point) point.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') { event.preventDefault(); capture(); }
    });
    var history = $('ins-history');
    if (history) history.addEventListener('click', function (event) {
      var target = event.target.closest('li[data-id]');
      if (!target) return;
      var id = target.getAttribute('data-id');
      fetch(gatewayBase() + '/api/inspection/' + encodeURIComponent(id))
        .then(function (response) { return response.ok ? response.json() : null; })
        .then(function (record) { if (record) renderRecord(record); })
        .catch(function () { /* ignore one failed detail request */ });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }

  C.Inspection = { setPage: setPage, refresh: refresh, capture: capture };
})();
