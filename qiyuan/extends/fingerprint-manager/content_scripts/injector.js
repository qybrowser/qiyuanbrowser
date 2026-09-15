// 桥接页面与 background：页面通过 CustomEvent 发起请求，background 代理访问 localhost:9003
window.addEventListener('qiyuan:request', function (e) {
  const detail = e.detail;

  function replyError(msg) {
    window.dispatchEvent(new CustomEvent('qiyuan:response:' + detail.id, {
      detail: { success: false, error: msg }
    }));
  }

  // 检查扩展上下文是否有效（代理模式下 Chromium 可能重置扩展运行时导致 context 失效）
  if (!chrome.runtime?.id) {
    replyError('扩展上下文已失效，请刷新页面重试');
    return;
  }

  try {
    chrome.runtime.sendMessage(
      { type: 'QIYUAN_ELECTRON_REQUEST', path: detail.path, method: detail.method, body: detail.body },
      function (response) {
        if (chrome.runtime.lastError) {
          replyError(chrome.runtime.lastError.message || '扩展通信失败');
          return;
        }
        window.dispatchEvent(new CustomEvent('qiyuan:response:' + detail.id, {
          detail: response || { success: false, error: '无响应' }
        }));
      }
    );
  } catch (e) {
    replyError('扩展上下文已失效，请刷新页面重试');
  }
});
