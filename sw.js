// 診療放射線技師ニュース: オフラインでも前回の内容を表示するためのキャッシュ
const VERSION = 'rtn-v25';
const SHELL = ['./', 'index.html', 'manifest.webmanifest', 'icon-192.png', 'icon-512.png', 'apple-touch-icon.png', 'favicon-32.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET') return;
  const sameOrigin = url.origin === self.location.origin;
  const isData = sameOrigin && /(news\.json|news_meta\.json|seminars\.json|supply\.json|papers\.json|kagawa\.json|\/archive\/)/.test(url.pathname);
  const isPage = e.request.mode === 'navigate' || (sameOrigin && /index\.html$/.test(url.pathname));
  const isFont = /fonts\.(googleapis|gstatic)\.com$/.test(url.hostname);
  if (isData || isPage) {
    // 新しい内容を優先し、通信できないときは前回の内容を使う(?付きのURLも同じ扱い)
    const key = url.origin + url.pathname;
    e.respondWith(
      fetch(e.request).then(res => {
        if (res.ok) { const copy = res.clone(); caches.open(VERSION).then(c => c.put(key, copy)); }
        return res;
      }).catch(() => caches.match(key).then(r => r || caches.match('index.html')))
    );
  } else if (isFont || (sameOrigin && SHELL.some(s => url.pathname.endsWith(s.replace('./', ''))))) {
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request).then(res => {
      if (res.ok || res.type === 'opaque') { const copy = res.clone(); caches.open(VERSION).then(c => c.put(e.request, copy)); }
      return res;
    })));
  }
});
