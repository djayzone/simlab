'use strict';

(() => {
  const viewport=document.querySelector('meta[name="viewport"]');
  if(viewport) viewport.setAttribute('content','width=device-width,initial-scale=1,viewport-fit=cover');
  const capable=document.createElement('meta');capable.name='apple-mobile-web-app-capable';capable.content='yes';document.head.appendChild(capable);
  const status=document.createElement('meta');status.name='apple-mobile-web-app-status-bar-style';status.content='black-translucent';document.head.appendChild(status);

  const isIOS=/iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform==='MacIntel' && navigator.maxTouchPoints>1);
  if(isIOS) document.documentElement.classList.add('ios');

  const engineState=document.createElement('div');
  engineState.className='mobile-engine-state';
  engineState.setAttribute('role','status');
  engineState.textContent='Moteur en resynchronisation · le monde reste visible';
  document.body.appendChild(engineState);

  const originalFetch=window.fetch.bind(window);
  window.fetch=async(...args)=>{
    const response=await originalFetch(...args);
    const url=String(args[0]||'');
    if(url.includes('/api/') && response.status===503) engineState.classList.add('visible');
    else if(url.includes('/api/') && response.ok) engineState.classList.remove('visible');
    return response;
  };
})();
