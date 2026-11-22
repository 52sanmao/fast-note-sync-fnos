#!/bin/bash
# fnOS CGI entry for Fast Note Sync.
#
# Serves a single self-contained page that tells the user whether the
# address they are currently using can actually be used by Obsidian, and
# embeds the upstream admin panel when that is safe to do.
#
# Notes:
# - fnOS ignores `protocol` and `port` for CGI entries; the request keeps
#   whatever host the user is browsing, so the page can branch on
#   location.hostname to tell LAN / FN Connect relay / public apart.
# - Everything is inlined: no external CSS/JS, no path handling, so there
#   is no user input reaching the shell.
set -u

echo "Content-Type: text/html; charset=utf-8"
echo ""

cat <<'HTML'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fast Note Sync · 访问方式提示</title>
<style>
  *{box-sizing:border-box}
  /* Author display rules below would otherwise beat the UA [hidden] rule. */
  [hidden]{display:none!important}
  html,body{height:100%;margin:0}
  body{
    display:flex;flex-direction:column;background:#f4f5f7;color:#1f2328;
    font:14px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
    -webkit-font-smoothing:antialiased;
  }
  .banner{display:flex;gap:12px;align-items:flex-start;padding:14px 18px;border-bottom:1px solid rgba(0,0,0,.07)}
  .banner .ico{flex:0 0 22px;height:22px;border-radius:50%;display:grid;place-items:center;font-size:13px;font-weight:700;color:#fff;margin-top:2px}
  .banner .body{min-width:0}
  .banner h1{margin:0 0 3px;font-size:15px;font-weight:600;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  .banner p{margin:0;font-size:13px;color:#454c55;overflow-wrap:anywhere}
  .banner ol{margin:6px 0 0;padding-left:18px;font-size:13px;color:#454c55;overflow-wrap:anywhere}
  .banner li{margin:2px 0}
  .tag{font-size:11px;font-weight:600;padding:1px 8px;border-radius:999px;line-height:1.75;white-space:nowrap}
  .warn{background:#fffaf0;border-bottom-color:#f2e2bd}
  .warn .ico{background:#d99509}
  .warn .tag{background:#fdeecb;color:#8a5a00}
  .bad{background:#fff5f4;border-bottom-color:#f4d4d1}
  .bad .ico{background:#d33a2c}
  .bad .tag{background:#ffe3df;color:#9d1f13}
  .good{background:#f2fbf4;border-bottom-color:#cfe9d6}
  .good .ico{background:#1a7f37}
  .good .tag{background:#dcf3e2;color:#14682c}
  .where{padding:6px 18px;font-size:12px;color:#6b7280;background:#fff;border-bottom:1px solid #e8eaed;overflow-wrap:anywhere}
  .where code{background:#f1f3f5;padding:1px 6px;border-radius:4px;font-size:12px;color:#374151;word-break:break-all}
  .stage{position:relative;flex:1;min-height:0;min-width:0;display:flex;flex-direction:column}
  iframe{flex:1;width:100%;border:0;background:#fff}
  .loading{padding:12px 18px;font-size:12px;color:#6b7280}
  .fallback{flex:1;min-width:0;display:grid;place-items:center;padding:24px;overflow:auto}
  .card{width:100%;max-width:560px;min-width:0;background:#fff;border:1px solid #e8eaed;border-radius:12px;padding:22px 24px;box-shadow:0 1px 2px rgba(0,0,0,.04)}
  .card h2{margin:0 0 8px;font-size:15px;font-weight:600}
  .card p{margin:0 0 8px;font-size:13px;color:#454c55;overflow-wrap:anywhere}
  .card ol{margin:4px 0 0;padding-left:20px;font-size:13px;color:#454c55;overflow-wrap:anywhere}
  .card li{margin:5px 0}
  .card code{background:#f1f3f5;padding:1px 5px;border-radius:4px;font-size:12px;word-break:break-all}
  .btn{display:inline-block;margin-top:14px;padding:9px 16px;border-radius:8px;background:#1f2328;color:#fff;text-decoration:none;font-size:13px;font-weight:500;border:0;cursor:pointer;font-family:inherit}
  .btn:hover{background:#3a4149}
  .tip{margin-top:14px;padding-top:12px;border-top:1px dashed #e8eaed;font-size:12px;color:#6b7280}
</style>
</head>
<body>

<div class="banner" id="banner" hidden>
  <div class="ico" id="ico">!</div>
  <div class="body">
    <h1><span id="title"></span><span class="tag" id="tag"></span></h1>
    <div id="desc"></div>
  </div>
</div>

<div class="where">你当前通过 <code id="where"></code> 打开本页，下面的提示依据这个地址判断。</div>

<div class="stage">
  <div class="loading" id="loading">正在加载管理面板…</div>
  <iframe id="frame" hidden title="Fast Note Sync 管理面板"></iframe>
  <div class="fallback" id="fallback" hidden>
    <div class="card">
      <h2 id="fbTitle"></h2>
      <div id="fbBody"></div>
      <a class="btn" id="fbBtn" hidden href="#">打开管理面板</a>
      <div class="tip" id="fbTip"></div>
    </div>
  </div>
</div>

<script>
(function () {
  var host = location.hostname || '';
  var proto = location.protocol;
  var port = location.port;

  // Private / link-local / loopback -> only reachable inside the LAN.
  function isLan(h) {
    if (/^(localhost|127\.|10\.|192\.168\.|169\.254\.)/.test(h)) return true;
    if (/^172\.(1[6-9]|2\d|3[01])\./.test(h)) return true;
    if (h === '[::1]') return true;
    if (h.indexOf('.local') !== -1) return true;
    // Bare hostname (no dot) is a LAN name: http://fnos/
    if (h.indexOf('.') === -1 && h.indexOf(':') === -1) return true;
    // IPv6 literal, e.g. [2409:8a62:...]
    if (h.charAt(0) === '[') return true;
    return false;
  }

  var relay = /\.fnos\.net$/i.test(host);      // FN Connect browser relay
  var mode = relay ? 'relay' : (isLan(host) ? 'lan' : 'wan');

  var el = function (id) { return document.getElementById(id); };
  el('where').textContent = proto + '//' + location.host;

  function banner(kind, icon, title, tag, html) {
    var b = el('banner');
    b.className = 'banner ' + kind;
    b.hidden = false;
    el('ico').textContent = icon;
    el('title').textContent = title;
    el('tag').textContent = tag;
    el('desc').innerHTML = html;
  }

  function fallback(title, bodyHtml, btnHref, tip) {
    el('loading').hidden = true;
    el('frame').hidden = true;
    el('fallback').hidden = false;
    el('fbTitle').textContent = title;
    el('fbBody').innerHTML = bodyHtml;
    var btn = el('fbBtn');
    if (btnHref) { btn.href = btnHref; btn.hidden = false; } else { btn.hidden = true; }
    el('fbTip').innerHTML = tip || '';
  }

  function panel() {
    el('fallback').hidden = true;
    el('loading').hidden = false;
    var f = el('frame');
    f.hidden = false;
    f.onload = function () { el('loading').hidden = true; };
    f.src = 'http://' + host + ':9000/';
  }

  if (mode === 'lan') {
    banner('warn', '!', '内网访问',
      '仅限内网',
      '授权页给出的地址是<b>内网地址</b>，只有连在同一台路由器下的设备能用。' +
      '手机切到移动网络、或者在外面的 Wi-Fi 下，都会连不上。');

    if (proto === 'http:') {
      panel();
    } else {
      // Page is HTTPS but the service is plain HTTP: browsers block the mix.
      fallback(
        '这个页面是 HTTPS，无法内嵌 HTTP 面板',
        '<p>浏览器会拦截「HTTPS 页面里加载 HTTP 内容」。请在新窗口直接打开：</p>' +
        '<p><code>http://' + host + ':9000</code></p>',
        'http://' + host + ':9000/',
        '打开后就是授权页，里面的地址可以在内网直接用于 Obsidian 同步。'
      );
    }

  } else if (mode === 'relay') {
    banner('bad', '×', '飞牛远程访问入口',
      '不能用于同步',
      '这是飞牛给<b>浏览器看面板</b>用的中转地址。飞牛不向第三方应用开放穿透通道，' +
      'Obsidian 用这个地址会一直显示「连接已断开」。');

    fallback(
      '这个入口不能用于 Obsidian 同步',
      '<p>飞牛远程访问只把面板转发给浏览器，第三方客户端拿到的不是能直连服务的通道，所以同步永远连不上。</p>' +
      '<p>请改用下面任意一种方式访问：</p>' +
      '<ol>' +
      '<li><b>局域网内</b>：用 <code>http://NAS内网IP:9000</code> 打开本服务，授权页地址可直接使用。</li>' +
      '<li><b>外网</b>：配置 DDNS 域名（飞牛「设置 → 远程访问 → DDNS」，用 IPv6 即可），之后用你的域名访问本服务。</li>' +
      '<li><b>外网备选</b>：内网穿透（Lucky / frp / Cloudflare Tunnel），注意穿透工具要支持 WebSocket。</li>' +
      '</ol>',
      null,
      '授权地址是跟着你打开的入口走的：从哪个地址进来，授权页就给哪个地址。所以用对入口，地址自然就对了。'
    );

  } else {
    banner('good', '✓', '外网访问',
      '可以同步',
      '当前是<b>外网域名</b>访问，授权页给出的地址可以在任何网络下使用，Obsidian 直接填即可。');

    fallback(
      '进入管理面板完成授权',
      '<p>你正在通过外网域名 <code>' + location.host + '</code> 访问。' +
      '点下面的按钮进入面板，在「授权 Obsidian」里生成同步地址。</p>',
      proto + '//' + location.host + '/',
      '当前是 HTTP 明文传输，公网使用时建议在前面套一层 HTTPS（反向代理需开启 WebSocket）。'
    );
  }
})();
</script>
</body>
</html>
HTML

exit 0
