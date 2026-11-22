#!/bin/bash
# fnOS CGI entry for Fast Note Sync.
#
# Opened from the desktop icon at /cgi/ThirdParty/fastnotesync/index.cgi/ .
# fnOS serves app/ui/index.cgi on its own web port, so this page always runs
# on the exact origin the user is browsing - which is what it inspects.
#
# The page does one thing: look at its own origin, decide whether that
# address is usable for Obsidian sync, say so in one sentence, and show the
# panel. Everything is inlined: no external files, no shell input.
set -u

echo "Content-Type: text/html; charset=utf-8"
echo "Cache-Control: no-store"
echo ""

cat <<'HTML'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fast Note Sync</title>
<style>
  *{box-sizing:border-box}
  [hidden]{display:none!important}
  html,body{height:100%;margin:0}
  body{display:flex;flex-direction:column;background:#f5f6f8;color:#1f2328;
    font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
  .bar{display:flex;gap:10px;align-items:flex-start;padding:12px 16px;border-bottom:1px solid rgba(0,0,0,.08)}
  .bar .dot{flex:0 0 20px;height:20px;margin-top:2px;border-radius:50%;display:grid;place-items:center;
    color:#fff;font-size:12px;font-weight:700}
  .bar .txt{min-width:0}
  .bar .title{font-size:14px;font-weight:600;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
  .bar .desc{font-size:13px;color:#4a5158;overflow-wrap:anywhere}
  .tag{font-size:11px;font-weight:600;padding:1px 8px;border-radius:999px;line-height:1.8;white-space:nowrap}
  .lan{background:#fffaf0;border-bottom-color:#f0e0ba}
  .lan .dot{background:#d99509}.lan .tag{background:#fdeecb;color:#8a5a00}
  .fnos{background:#fff5f4;border-bottom-color:#f3d3cf}
  .fnos .dot{background:#d33a2c}.fnos .tag{background:#ffe3df;color:#9d1f13}
  .wan{background:#f2fbf4;border-bottom-color:#cde8d5}
  .wan .dot{background:#1a7f37}.wan .tag{background:#dcf3e2;color:#14682c}
  .addr{padding:6px 16px;font-size:12px;color:#6b7280;background:#fff;border-bottom:1px solid #e8eaed;
    overflow-wrap:anywhere}
  .addr code{background:#f1f3f5;padding:1px 6px;border-radius:4px;color:#374151;word-break:break-all}
  .stage{flex:1;min-height:0;display:flex;flex-direction:column}
  iframe{flex:1;width:100%;border:0;background:#fff}
  .card{flex:1;display:grid;place-items:center;padding:20px;overflow:auto}
  .inner{width:100%;max-width:540px;background:#fff;border:1px solid #e8eaed;border-radius:12px;padding:20px 22px}
  .inner h2{margin:0 0 8px;font-size:15px}
  .inner p{margin:0 0 8px;font-size:13px;color:#4a5158;overflow-wrap:anywhere}
  .inner ol{margin:0;padding-left:20px;font-size:13px;color:#4a5158;overflow-wrap:anywhere}
  .inner li{margin:4px 0}
  .inner code{background:#f1f3f5;padding:1px 5px;border-radius:4px;word-break:break-all}
  .btn{display:inline-block;margin-top:14px;padding:8px 16px;border-radius:8px;background:#1f2328;color:#fff;
    text-decoration:none;font-size:13px;font-weight:500}
  .btn:hover{background:#3a4149}
</style>
</head>
<body>

<div class="bar" id="bar">
  <div class="dot" id="dot">!</div>
  <div class="txt">
    <div class="title"><span id="title"></span><span class="tag" id="tag"></span></div>
    <div class="desc" id="desc"></div>
  </div>
</div>

<div class="addr">你当前通过 <code id="origin"></code> 打开本页</div>

<div class="stage">
  <iframe id="frame" hidden title="Fast Note Sync 管理面板"></iframe>
  <div class="card" id="card" hidden>
    <div class="inner">
      <h2 id="cardTitle"></h2>
      <div id="cardBody"></div>
      <a class="btn" id="open" href="#">打开管理面板</a>
    </div>
  </div>
</div>

<script>
(function () {
  var host = location.hostname;
  var secure = location.protocol === 'https:';
  var panel = 'http://' + host + ':9000/';   // 服务固定监听 9000，且是明文 HTTP

  // 内网：私有网段 / 链路本地 / 本机名 / .local / 单段主机名 http://fnos/ / IPv6 字面量
  function isLan(h) {
    return /^(localhost|127\.|10\.|192\.168\.|169\.254\.)/.test(h)
      || /^172\.(1[6-9]|2\d|3[01])\./.test(h)
      || h === '[::1]'
      || h.indexOf('.local') !== -1
      || h.indexOf('.') === -1
      || h.charAt(0) === '[';
  }

  // 飞牛远程访问（FN Connect）的域名，只转发网页，不转发 9000 端口
  var mode = /\.(fnos\.net|5ddd\.com)$/i.test(host) ? 'fnos'
           : isLan(host) ? 'lan'
           : 'wan';

  var $ = function (id) { return document.getElementById(id); };
  $('origin').textContent = location.origin;

  function bar(kind, sign, kindText, title, desc) {
    $('bar').className = 'bar ' + kind;
    $('dot').textContent = sign;
    $('title').textContent = title;
    $('tag').textContent = kindText;
    $('desc').innerHTML = desc;
  }

  function embed() {
    $('frame').hidden = false;
    $('frame').src = panel;
  }

  function card(title, body, href) {
    $('card').hidden = false;
    $('cardTitle').textContent = title;
    $('cardBody').innerHTML = body;
    if (href) { $('open').href = href; } else { $('open').hidden = true; }
  }

  // HTTPS 页面里嵌不了 HTTP 面板，浏览器会拦掉，只能另开窗口
  function mixed(title, extra) {
    card(title,
      '<p>本页是 HTTPS，而面板是 HTTP 的 <code>' + host + ':9000</code>，' +
      '浏览器不允许「HTTPS 页面里加载 HTTP 内容」，所以只能在新窗口打开。</p>' +
      (extra || ''),
      panel);
  }

  if (mode === 'lan') {
    bar('lan', '!', '只在家能用', '内网地址',
      '你现在用的是内网地址，只有连在同一个路由器下的设备才能访问。' +
      '手机用流量、或在外面的 Wi-Fi 下，都连不上。');
    if (secure) { mixed('在本窗口打不开面板'); } else { embed(); }

  } else if (mode === 'fnos') {
    bar('fnos', '×', '不能用于同步', '飞牛远程访问地址',
      '这是飞牛「远程访问」的中转地址，只能在网页里看看面板，' +
      '没有留给 Obsidian 这类第三方客户端的通道，同步会一直连接失败。');
    card('换一个地址打开本应用，才能同步',
      '<p>同步需要一个能直接连到本服务的地址，三选一：</p><ol>' +
      '<li><b>在家</b>：用内网地址打开 <code>http://NAS的IP:9000</code>，授权页给出的地址直接可用。</li>' +
      '<li><b>在外（推荐）</b>：飞牛「设置 → 远程访问 → DDNS」配一个域名（有 IPv6 就够），' +
      '之后用这个域名打开本应用，授权页给出的就是域名地址。</li>' +
      '<li><b>在外（备选）</b>：用 Lucky / frp / Cloudflare Tunnel 做内网穿透，记得开启 WebSocket。</li></ol>',
      null);

  } else {
    bar('wan', '✓', '到哪都能用', '外网地址',
      '你现在用的是外网地址，授权页给出的地址在任何网络下都能用，Obsidian 直接填就行。' +
      (secure ? '' : ' 目前是 HTTP 明文传输，公网使用建议前面套一层 HTTPS。'));
    if (secure) {
      mixed('在本窗口打不开面板',
        '<p>在外网建议把 <code>' + host + '</code> 的 HTTPS 反向代理到 9000 端口（要开启 WebSocket），' +
        '然后用 <code>https://' + host + '/</code> 直接访问。</p>');
    } else {
      embed();
    }
  }
})();
</script>
</body>
</html>
HTML

exit 0
