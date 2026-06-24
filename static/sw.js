// Service Worker - 網路優先策略（v1.3.2）
const CACHE_NAME = 'stock-app-v1.3.2';
const urlsToCache = [
  '/',
  '/manifest.json',
  'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js'
];

// 安裝事件 - 立即接管
self.addEventListener('install', event => {
  self.skipWaiting();  // 強制立即啟用新版 SW
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

// 啟用事件 - 清理所有舊快取
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())  // 立即接管所有頁面
  );
});

// 擷取事件 - 網路優先，失敗才用快取
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  
  // API 請求絕對不快取
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(fetch(event.request));
    return;
  }
  
  // HTML/CSS/JS：網路優先
  event.respondWith(
    fetch(event.request)
      .then(response => {
        // 成功拿到新版，更新快取
        if (response && response.status === 200) {
          const responseToCache = response.clone();
          caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, responseToCache);
          });
        }
        return response;
      })
      .catch(() => {
        // 網路失敗才回退到快取
        return caches.match(event.request);
      })
  );
});
