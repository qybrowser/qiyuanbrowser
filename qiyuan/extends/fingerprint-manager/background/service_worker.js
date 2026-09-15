// 代理页面对 localhost:9003 的请求（绕过 PNA/Mixed-Content 限制）
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type !== 'QIYUAN_ELECTRON_REQUEST') return;
  const { path, method, body } = message;
  const opts = { method: method || 'GET', headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  fetch('http://localhost:9003' + path, opts)
    .then(r => r.json())
    .then(data => sendResponse(data))
    .catch(err => sendResponse({ success: false, error: err.message }));
  return true; // 异步响应
});
