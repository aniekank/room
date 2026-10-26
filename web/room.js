/* Shared TV-side helpers. Written for the 2018-19 Samsung Tizen browser (Chromium ~56-63):
   ES2015 only - no optional chaining, no ?? , no CSS grid or flex gap. */
var Room = (function () {
  var KEYS = { 37: 'left', 38: 'up', 39: 'right', 40: 'down', 13: 'enter', 10009: 'back', 8: 'back', 27: 'back',
    415: 'play', 19: 'pause', 10252: 'playpause', 417: 'ff', 412: 'rw', 413: 'stop',
    403: 'red', 404: 'green', 405: 'yellow', 406: 'blue', 32: 'enter',
    48: '0', 49: '1', 50: '2', 51: '3', 52: '4', 53: '5', 54: '6', 55: '7', 56: '8', 57: '9' };

  function post(url, body) {
    return fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) })
      .then(function (r) { return r.json(); })
      .catch(function () { return null; });
  }

  function get(url) {
    return fetch(url).then(function (r) { return r.json(); });
  }

  // Phone remote -> server queue -> here. A {go: '/dig'} command switches channel.
  function poll(onCmd) {
    function tick() {
      get('/api/poll').then(function (res) {
        (res.cmds || []).forEach(function (c) {
          if (c.go) { location.href = c.go; return; }
          onCmd(c);
        });
      }).catch(function () {}).then(function () { setTimeout(tick, 900); });
    }
    tick();
  }

  function report(fn) {
    function tick() { post('/api/tv', fn()); }
    tick();
    return setInterval(tick, 2000);
  }

  // Remote buttons. Number keys jump channels from anywhere.
  function keys(handler) {
    document.addEventListener('keydown', function (e) {
      var k = KEYS[e.keyCode];
      if (!k) return;
      if (k === '1') { location.href = '/nag'; return; }
      if (k === '2') { location.href = '/dig'; return; }
      if (k === '3') { location.href = '/window'; return; }
      if (k === '5') { location.href = '/station'; return; }
      if (k === '4') { location.href = '/movies'; return; }
      if (k === '0') { location.href = '/'; return; }
      if (handler(k) !== false) e.preventDefault();
    });
  }

  function pad(n) { return (n < 10 ? '0' : '') + n; }

  function toast(text, ms) {
    var el = document.getElementById('toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'toast';
      el.className = 'toast';
      document.body.appendChild(el);
    }
    el.textContent = text;
    el.className = 'toast show';
    clearTimeout(el._t);
    el._t = setTimeout(function () { el.className = 'toast'; }, ms || 2600);
  }

  // English subtitles drawn over a <video> from cues the Mac parsed (the TV's own track support is too old to trust).
  // Returns {toggle, off}; toggle() finds them the first time.
  function subs(video, id, box) {
    var cues = [], on = false, last = -1;
    box.className = 'subs';
    function draw() {
      if (!on || !cues.length) { box.innerHTML = ''; return; }
      var t = video.currentTime, i = -1, lo = 0, hi = cues.length - 1;
      while (lo <= hi) { var mid = (lo + hi) >> 1; if (cues[mid][0] <= t) { i = mid; lo = mid + 1; } else hi = mid - 1; }
      var c = i >= 0 && t <= cues[i][1] ? i : -1;
      if (c === last) return;
      last = c;
      box.innerHTML = c < 0 ? '' : '<span>' + String(cues[c][2]).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/\n/g, '<br>') + '</span>';
    }
    function set(r) { cues = r.cues || []; on = !!r.on && cues.length > 0; last = -1; draw(); }
    get('/api/subs?id=' + encodeURIComponent(id)).then(set);
    video.addEventListener('timeupdate', draw);
    return {
      toggle: function () {
        toast(on ? 'Subtitles off' : 'Subtitles…', 2500);
        return post('/api/subs', { id: id, on: !on }).then(function (r) { set(r); if (r.msg) toast(r.msg, 4500); return r; });
      },
      off: function () { video.removeEventListener('timeupdate', draw); box.innerHTML = ''; }
    };
  }

  // Loads the YouTube IFrame API once and hands back a ready player.
  function youtube(elId, opts, onReady, onState, onError) {
    window.onYouTubeIframeAPIReady = function () {
      var player = new YT.Player(elId, {
        width: '100%', height: '100%',
        playerVars: { autoplay: 1, controls: 0, disablekb: 1, modestbranding: 1, rel: 0, iv_load_policy: 3, playsinline: 1, fs: 0, cc_load_policy: 0 },
        events: {
          onReady: function () { onReady(player); },
          onStateChange: function (e) { if (onState) onState(e.data, player); },
          onError: function (e) { if (onError) onError(e.data, player); }
        }
      });
    };
    var s = document.createElement('script');
    s.src = 'https://www.youtube.com/iframe_api';
    document.head.appendChild(s);
  }

  return { post: post, get: get, poll: poll, report: report, keys: keys, pad: pad, toast: toast, youtube: youtube, subs: subs };
})();
