(function () {
  var md5 = new URLSearchParams(location.search).get('md5') || '';

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

  var COUNTRY_CN = {
    'US':'美国','CN':'中国','JP':'日本','KR':'韩国','SG':'新加坡',
    'HK':'香港','TW':'台湾','DE':'德国','GB':'英国','FR':'法国',
    'RU':'俄罗斯','AU':'澳大利亚','CA':'加拿大','BR':'巴西',
    'IN':'印度','TH':'泰国','MY':'马来西亚','ID':'印度尼西亚',
    'VN':'越南','PH':'菲律宾','NL':'荷兰','IT':'意大利',
    'ES':'西班牙','SE':'瑞典','CH':'瑞士','TR':'土耳其',
  };
  var CITY_CN = {
    'Beijing':'北京','Shanghai':'上海','Guangzhou':'广州','Shenzhen':'深圳',
    'Singapore':'新加坡','Tokyo':'东京','Seoul':'首尔','Hong Kong':'香港',
    'New York':'纽约','Los Angeles':'洛杉矶','London':'伦敦','Paris':'巴黎',
  };

  function flagEmoji(code) {
    if (!code || code.length !== 2) return '';
    var c = code.toUpperCase();
    return String.fromCodePoint(0x1F1E6 + c.charCodeAt(0) - 65, 0x1F1E6 + c.charCodeAt(1) - 65);
  }

  function renderIpSuccess(r, proxyData) {
    var sec = document.getElementById('ip-section');
    var countryCn = COUNTRY_CN[r.country_code] || r.country || '-';
    var cityCn = CITY_CN[r.city] || r.city || '-';
    // 兼容嵌套(qiyuan/ipwho.is)与旧扁平结构
    var flagImg = (r.flag && r.flag.img) || r.flag_img || '';
    var tzId = (r.timezone && r.timezone.id) || r.timezone_id || '';
    var tzUtc = (r.timezone && r.timezone.utc) || r.timezone_utc || '';
    var flag = flagImg
      ? '<img src="' + flagImg + '" style="height:22px;vertical-align:middle;margin-right:6px;border-radius:2px">'
      : '<span style="font-size:22px;margin-right:6px">' + flagEmoji(r.country_code) + '</span>';
    var tzSuffix = (tzUtc || '') + (tzId ? ('，' + tzId) : '');
    sec.innerHTML =
      '<div style="display:flex;flex-direction:column;align-items:center;gap:8px">' +
        '<div style="display:flex;align-items:center;gap:10px">' + flag +
          '<span style="font-size:28px;font-weight:700;letter-spacing:1px;font-family:monospace">' + r.ip + '</span>' +
          '<button id="qy-copy-btn" style="background:rgba(255,255,255,.2);border:none;border-radius:6px;padding:4px 8px;cursor:pointer;color:#fff;font-size:13px">复制</button>' +
        '</div>' +
        '<div style="font-size:15px;opacity:.85">' + countryCn + ' / ' + (r.region || '') + ' / ' + cityCn + '</div>' +
        '<div style="font-size:13px;opacity:.65;display:flex;gap:16px"><span id="qy-clock"></span></div>' +
      '</div>';
    var btn = document.getElementById('qy-copy-btn');
    if (btn) btn.addEventListener('click', function () {
      navigator.clipboard.writeText(r.ip).then(function () {
        btn.textContent = '✓ 已复制'; btn.style.background = 'rgba(103,194,58,.7)';
        setTimeout(function () { btn.textContent = '复制'; btn.style.background = 'rgba(255,255,255,.2)'; }, 1500);
      });
    });
    if (tzId) {
      var fmt = new Intl.DateTimeFormat('zh-CN', {
        timeZone: tzId, year:'numeric', month:'long', day:'numeric',
        hour:'2-digit', minute:'2-digit', second:'2-digit', hour12: false
      });
      var tick = function () {
        var el = document.getElementById('qy-clock');
        if (el) el.textContent = fmt.format(new Date()) + (tzSuffix ? '（' + tzSuffix + '）' : '');
      };
      tick(); setInterval(tick, 1000);
    }
    if (proxyData && proxyData.proxy_mode === 'no_proxy' && proxyData.md5) {
      callElectron('/api/update-proxy-ip', 'POST', { md5: proxyData.md5, ip: r.ip, country: r.country, city: r.city }).catch(function(){});
    }
  }

  function renderIpError(error, addr, retryCount, MAX_RETRY, onRetry) {
    var retryHint = retryCount > 0 ? '<div style="font-size:12px;opacity:.5;margin-top:2px">第 ' + retryCount + ' 次重试仍失败</div>' : '';
    var btnHtml = retryCount >= MAX_RETRY
      ? '<button disabled style="margin-top:10px;padding:6px 20px;border:none;border-radius:6px;background:rgba(255,255,255,.15);color:rgba(255,255,255,.4);font-size:13px;cursor:not-allowed">已达最大重试次数</button>'
      : '<button id="qy-retry-btn" style="margin-top:10px;padding:6px 20px;border:none;border-radius:6px;background:rgba(255,255,255,.25);color:#fff;font-size:13px;cursor:pointer">重新检测</button>';
    document.getElementById('ip-section').innerHTML =
      '<div style="display:flex;flex-direction:column;align-items:center;gap:4px">' +
        '<div style="font-size:22px">⚠️</div>' +
        '<div style="font-size:15px;font-weight:600">IP 检测失败' + (addr ? '（' + addr + '）' : '') + '</div>' +
        '<div style="font-size:13px;opacity:.75">' + error + '</div>' +
        '<div style="font-size:12px;opacity:.6">请核实代理设置是否正确</div>' +
        retryHint + btnHtml +
      '</div>';
    var btn = document.getElementById('qy-retry-btn');
    if (btn) btn.addEventListener('click', onRetry);
  }

  function renderIpChecking() {
    document.getElementById('ip-section').innerHTML =
      '<div style="display:flex;flex-direction:column;align-items:center;gap:8px">' +
        '<div style="width:28px;height:28px;border:3px solid rgba(255,255,255,.3);border-top-color:#fff;border-radius:50%;animation:qy-spin .8s linear infinite"></div>' +
        '<div style="font-size:14px;opacity:.8">正在检测 IP…</div>' +
      '</div>';
    if (!document.getElementById('qy-spin-style')) {
      var s = document.createElement('style');
      s.id = 'qy-spin-style';
      s.textContent = '@keyframes qy-spin{to{transform:rotate(360deg)}}';
      document.head.appendChild(s);
    }
  }

  function checkIp(proxyData, retryCount, MAX_RETRY) {
    var mode = proxyData ? proxyData.proxy_mode : 'existing';
    if (mode === 'buy') {
      document.getElementById('ip-section').innerHTML = '<div style="font-size:15px;opacity:.7">-- 无代理信息，跳过检测 --</div>';
      return;
    }
    renderIpChecking();
    var addr = proxyData && proxyData.proxy_addr && proxyData.proxy_port ? proxyData.proxy_addr + ':' + proxyData.proxy_port : '';
    var promise = mode === 'no_proxy'
      ? callElectron('/api/check-network', 'GET')
      : callElectron('/api/check-proxy', 'POST', {
          proxy_type: proxyData.proxy_type || 'http',
          proxy_addr: proxyData.proxy_addr || '',
          proxy_port: Number(proxyData.proxy_port) || 0,
          username: proxyData.proxy_username || '',
          password: proxyData.proxy_password || '',
        });
    promise.then(function (res) {
      if (res.success) renderIpSuccess(res, proxyData);
      else renderIpError(res.error || '未知错误', addr, retryCount, MAX_RETRY, function () {
        if (retryCount < MAX_RETRY) checkIp(proxyData, retryCount + 1, MAX_RETRY);
      });
    }).catch(function (e) {
      renderIpError('无法连接IP检测服务（' + e.message + '）', addr, retryCount, MAX_RETRY, function () {
        if (retryCount < MAX_RETRY) checkIp(proxyData, retryCount + 1, MAX_RETRY);
      });
    });
  }

  function row(label, value, full) {
    return '<div class="info-item' + (full ? ' full' : '') + '">' +
      '<span class="info-label">' + label + '</span>' +
      '<span class="info-value' + (full && value.length > 60 ? ' ua' : '') + '">' + value + '</span>' +
    '</div>';
  }

  function renderMain(data) {
    var b = data.browser || {};
    var fp = data.fingerprint || {};
    var mainEl = document.getElementById('main-content');
    mainEl.style.display = '';
    document.title = b.name || '浏览器起始页';

    var envRows = [
      row('环境名称', b.name || '-'),
      row('代理方式', b.proxy_mode_cn || '-'),
      row('同步用户信息', b.sync_user || '-'),
      row('标签', b.tags || '-'),
    ];
    if (b.launch_args && b.launch_args !== '-') envRows.push(row('启动参数', b.launch_args, true));
    if (b.remark && b.remark !== '-') envRows.push(row('备注', b.remark, true));

    var fpRows = [
      row('平台', fp.platform || '-'),
      row('版本', fp.browser_version || '-'),
      row('WebRTC', fp.webrtc || '-'),
      row('WebGL', fp.webgl || '-'),
      row('WebGPU', fp.webgpu || '-'),
      row('时区', fp.timezone || '-'),
      row('地理位置', fp.geo || '-'),
      row('语言', fp.language || '-'),
      row('界面语言', fp.ui_language || '-'),
      row('屏幕分辨率', fp.screen || '-'),
      row('字体偏移', fp.font || '-'),
      row('Canvas 噪声', fp.canvas || '-'),
      row('音频偏移', fp.audio || '-'),
      row('ClientRects', fp.client_rects || '-'),
      row('Speech Voices', fp.speech_voices || '-'),
      row('媒体设备', fp.media_devices || '-'),
      row('CPU 核心数', fp.cpu_cores || '-'),
      row('内存', fp.memory_gb || '-'),
      row('禁用TLS特性', fp.tls || '-'),
    ];

    mainEl.innerHTML =
      '<div class="card"><div class="card-title">🖥 环境信息</div><div class="info-grid">' + envRows.join('') + '</div></div>' +
      '<div class="card"><div class="card-title">🔏 指纹信息</div>' +
        '<div class="info-grid">' + fpRows.join('') + '</div>' +
        '<div class="info-grid" style="margin-top:8px">' + row('User Agent', '<span class="ua">' + (fp.user_agent || '-') + '</span>', true) + '</div>' +
      '</div>';
  }

  callElectron('/api/browser-home-data?md5=' + encodeURIComponent(md5), 'GET')
    .then(function (resp) {
      if (resp && resp.code === 200 && resp.data) {
        renderMain(resp.data);
        checkIp(resp.data.proxy || null, 0, 3);
      } else {
        document.getElementById('ip-section').innerHTML = '<div id="err-tip">数据加载失败：' + (resp && resp.message ? resp.message : '未知错误') + '</div>';
      }
    })
    .catch(function (e) {
      document.getElementById('ip-section').innerHTML = '<div id="err-tip">无法连接客户端服务：' + e.message + '</div>';
    });
})();
