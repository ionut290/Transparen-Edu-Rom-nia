const CACHE='transparenta-edu-v4';
const HOME='./role-demo.html';
const ASSETS=['./manifest.json','./role-demo.html','./community.html','./data/access-workflow.json','./data/class-model.json','./data/class-profile-model.json'];
self.addEventListener('install',event=>{
  event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS)).then(()=>self.skipWaiting()));
});
self.addEventListener('activate',event=>{
  event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim()));
});
self.addEventListener('fetch',event=>{
  if(event.request.method!=='GET')return;
  const request=event.request;
  event.respondWith(fetch(request).then(response=>{
    if(response&&response.ok){const copy=response.clone();caches.open(CACHE).then(cache=>cache.put(request,copy));}
    return response;
  }).catch(()=>caches.match(request).then(cached=>cached||((request.mode==='navigate')?caches.match(HOME):undefined))));
});
