// Service Worker - 離線快取靜態資源
const CACHE_NAME = 'stock-app-v1';
const urlsToCache = [
  '/',
  '/index.html',
  '/style.css',
  '/app.js',
  '/manifest.json',
  'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js'
];

// 安裝事件 - 快取靜態資源
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
  );
});

// 擷取事件 - 回傳快取資源
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // 快取命中，回傳快取資源
        if (response) {
          return response;
        }
        
        // 快取未命中，從網路擷取
        return fetch(event.request).then(response => {
          // 檢查是否傳回有效回應
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }
          
          // 複製回應
          const responseToCache = response.clone();
          
          caches.open(CACHE_NAME)
            .then(cache => {
              cache.put(event.request, responseToCache);
            });
          
          return response;
        });
      })
  );
});

// 啟用事件 - 清理舊快取
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
    })
  );
});
