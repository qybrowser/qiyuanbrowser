(function () {
  var code = new URLSearchParams(location.search).get('code') || '';

  function callElectron(path, method, body) {
    return new Promise(function (resolve, reject) {
      chrome.runtime.sendMessage(
        { type: 'QIYUAN_ELECTRON_REQUEST', path: path, method: method || 'GET', body: body || null },
        function (resp) {
          if (chrome.runtime.lastError) { reject(new Error(chrome.runtime.lastError.message)); return; }
          resolve(resp);
        }
      );
    });
  }

  function render(data) {
    var timeBlock = data.error_time
      ? '<div class="info-block"><div class="info-label">记录时间</div><div class="info-value">' + data.error_time + '</div></div>'
      : '';
    document.getElementById('card').innerHTML =
      '<div class="error-icon">&#9888;&#65039;</div>' +
      '<div class="error-title">' + (data.title || '未知错误') + '</div>' +
      '<div class="info-block"><div class="info-label">错误编号</div><div class="info-value code-value">' + (data.code || code) + '</div></div>' +
      timeBlock +
      '<div class="tips"><div class="tips-title">遇到问题？</div><ul>' +
        '<li>请将错误编号提供给技术支持以便快速定位</li>' +
        '<li>确认后端服务是否已启动并正常运行</li>' +
        '<li>检查网络连接和代理配置是否正确</li>' +
        '<li>尝试重新启动浏览器</li>' +
      '</ul></div>';
  }

  function renderFallback(msg) {
    document.getElementById('card').innerHTML =
      '<div class="error-icon">&#9888;&#65039;</div>' +
      '<div class="error-title">启动异常</div>' +
      '<div class="info-block"><div class="info-label">错误编号</div><div class="info-value code-value">' + code + '</div></div>' +
      '<div class="tips"><div class="tips-title">提示</div><ul><li>' + msg + '</li><li>请联系技术支持</li></ul></div>';
  }

  if (!code) { renderFallback('缺少错误编号'); return; }

  callElectron('/api/browser-error-data?code=' + encodeURIComponent(code), 'GET')
    .then(function (resp) {
      if (resp && resp.code === 200 && resp.data) render(resp.data);
      else renderFallback('数据加载失败');
    })
    .catch(function (e) {
      renderFallback('无法连接客户端服务：' + e.message);
    });
})();
