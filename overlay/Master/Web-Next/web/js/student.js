/* =====================================================================
 * C50C student.js - read-only student H5 client for inspection results.
 * C50C student.js - 面向学生的只读巡检结果 H5 客户端。
 * It consumes the standalone inspection gateway and never touches chassis
 * control topics.
 * 它仅访问独立巡检业务网关，绝不接触底盘控制话题。
 * ===================================================================== */
(function () {
  'use strict';

  var state = { ws: null, timer: 0 };

  function $(id) { return document.getElementById(id); }

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (ch) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch];
    });
  }

  /** Resolve the inspection gateway origin for the H5 client.
   *  为学生端 H5 客户端解析巡检业务网关来源地址。 */
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
    var el = $('student-status');
    if (!el) return;
    el.textContent = text;
    el.className = 'chip' + (kind === 'ok' ? ' ok' : kind === 'bad' ? ' bad' : '');
  }

  function renderRecord(record) {
    if (!record || !record.capture_id) return;
    var image = $('student-image');
    var empty = $('student-empty');
    var meta = $('student-meta');
    var url = record.annotated_url || record.image_url;
    if (image && url) {
      image.src = gatewayBase() + url;
      image.hidden = false;
      if (empty) empty.hidden = true;
    }
    if (meta) {
      meta.hidden = false;
      meta.textContent = fmtTime(record.created_at) + ' · '
        + (record.inspection_point || '未指定点位') + ' · '
        + '严重程度：' + severityText(record.severity);
    }
    var list = $('student-defects');
    if (!list) return;
    var defects = record.defects || [];
    if (!defects.length) {
      list.innerHTML = '<li class="st">本次巡检未发现缺陷</li>';
      return;
    }
    list.innerHTML = defects.map(function (item) {
      var name = item.display_name || item.label || '缺陷';
      var confidence = typeof item.confidence === 'number'
        ? (item.confidence * 100).toFixed(1) + '%' : '—';
      return '<li><b>' + esc(name) + '</b><span class="mono">' + confidence
        + '</span><span class="chip">' + esc(item.label || '') + '</span></li>';
    }).join('');
  }

  function renderHistory(items) {
    var list = $('student-history');
    if (!list) return;
    if (!items || !items.length) {
      list.innerHTML = '<li class="st">暂无历史记录</li>';
      return;
    }
    list.innerHTML = items.map(function (item) {
      return '<li data-id="' + esc(item.capture_id) + '">'
        + '<b class="mono">' + esc(fmtTime(item.created_at)) + '</b>'
        + '<span>' + esc(item.inspection_point || '未指定点位') + '</span>'
        + '<span class="st">' + (item.defect_count || 0) + ' 项 · '
        + esc(severityText(item.severity)) + '</span></li>';
    }).join('');
  }

  function refresh() {
    fetch(gatewayBase() + '/api/inspection/latest')
      .then(function (response) { return response.ok ? response.json() : {}; })
      .then(function (data) {
        if (data && data.capture_id) {
          renderRecord(data);
          setStatus('实时在线', 'ok');
        } else {
          setStatus('暂无抓拍', '');
        }
      })
      .catch(function () { setStatus('网关离线', 'bad'); });
    fetch(gatewayBase() + '/api/inspection/history?limit=20')
      .then(function (response) { return response.ok ? response.json() : { items: [] }; })
      .then(function (data) { renderHistory((data && data.items) || []); })
      .catch(function () { /* keep the previous history */ });
  }

  function connectWs() {
    if (state.ws) return;
    var socket;
    try { socket = new WebSocket(wsBase() + '/ws/inspection'); } catch (e) { return; }
    state.ws = socket;
    socket.onmessage = function (event) {
      var message;
      try { message = JSON.parse(event.data); } catch (e) { return; }
      if (message.t === 'inspection_snapshot' && message.items && message.items[0]) {
        renderRecord(message.items[0]);
      } else if (message.t === 'inspection_alert') {
        renderRecord(message.record);
        refresh();
      }
    };
    socket.onclose = function () {
      state.ws = null;
      setTimeout(connectWs, 2500);
    };
    socket.onerror = function () { try { socket.close(); } catch (e) { /* ignore */ } };
  }

  function bindHistory() {
    var history = $('student-history');
    if (!history) return;
    history.addEventListener('click', function (event) {
      var target = event.target.closest('li[data-id]');
      if (!target) return;
      var id = target.getAttribute('data-id');
      fetch(gatewayBase() + '/api/inspection/' + encodeURIComponent(id))
        .then(function (response) { return response.ok ? response.json() : null; })
        .then(function (record) { if (record) renderRecord(record); })
        .catch(function () { /* ignore one failed detail request */ });
    });
  }

  function boot() {
    bindHistory();
    refresh();
    connectWs();
    state.timer = setInterval(refresh, 5000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
