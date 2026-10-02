'use strict';

(() => {
  const style=document.createElement('style');
  style.textContent=`
    .world-card{position:relative}
    #weather-hud{position:absolute;left:14px;top:14px;z-index:8;background:rgba(3,12,20,.84);border:1px solid rgba(150,210,235,.24);border-radius:10px;padding:8px 11px;color:#e6f5ff;font:12px ui-monospace,monospace;backdrop-filter:blur(5px);box-shadow:0 8px 20px rgba(0,0,0,.18);min-width:245px}
    #weather-hud b{display:block;font-size:13px;margin-bottom:3px}.weather-dry{color:#ffd166}.weather-wet{color:#72d6ff}.weather-cold{color:#b8dcff}.weather-hot{color:#ffb07a}
    #weather-grid{position:absolute;inset:0;display:grid;grid-template-columns:repeat(6,1fr);grid-template-rows:repeat(4,1fr);z-index:4;pointer-events:none;overflow:hidden;border-radius:inherit}
    #weather-grid i{display:block;transition:background .7s ease}
    #weather-controls{margin-top:8px;padding-top:7px;border-top:1px solid rgba(255,255,255,.12);pointer-events:auto;color:#dcebf3}
    #weather-controls summary{cursor:pointer;user-select:none;font-weight:700}
    #weather-controls .wc-row{display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-top:6px}
    #weather-controls button,#weather-controls select,#weather-controls input{font:11px ui-monospace,monospace;border-radius:6px;border:1px solid rgba(255,255,255,.18);background:#0b1a25;color:#ecf8ff;padding:5px;min-width:0}
    #weather-controls button{cursor:pointer}#weather-controls button:hover{background:#143247}
    #weather-controls label{display:grid;grid-template-columns:72px 1fr 34px;align-items:center;gap:5px;margin-top:5px;font-size:10px}
    #weather-controls input[type=range]{padding:0;width:100%}
    #weather-mode{opacity:.8;margin-left:6px;font-weight:400}
  `;
  document.head.appendChild(style);

  const card=document.querySelector('.world-stage')||document.querySelector('.world-card');
  if(!card)return;
  const hud=document.createElement('div'); hud.id='weather-hud';
  const grid=document.createElement('div'); grid.id='weather-grid';
  for(let i=0;i<24;i++)grid.appendChild(document.createElement('i'));
  hud.innerHTML=`<b>Environnement <span id="weather-mode"></span></b><div id="weather-readout">initialisation…</div>
  <details id="weather-controls"><summary>Contrôle météo live</summary>
    <div class="wc-row">
      <button data-preset="clear">☀ Clair</button><button data-preset="rain">☂ Pluie</button>
      <button data-preset="storm">⚡ Orage</button><button data-preset="drought">Sec</button>
      <button data-preset="heatwave">Canicule</button><button data-preset="cold_snap">Froid</button>
    </div>
    <div class="wc-row"><select id="wc-season"><option value="">Saison naturelle</option><option>printemps</option><option>été</option><option>automne</option><option>hiver</option></select><button id="wc-auto">↺ Auto</button></div>
    <label>Temp. <input id="wc-temp" type="range" min="-20" max="45" step="1"><span id="wc-temp-v"></span></label>
    <label>Pluie <input id="wc-rain" type="range" min="0" max="100" step="1"><span id="wc-rain-v"></span></label>
    <label>Vent <input id="wc-wind" type="range" min="0" max="100" step="1"><span id="wc-wind-v"></span></label>
    <label>Sécher. <input id="wc-dry" type="range" min="0" max="100" step="1"><span id="wc-dry-v"></span></label>
  </details>`;
  card.appendChild(grid); card.appendChild(hud);

  const readout=hud.querySelector('#weather-readout'),modeEl=hud.querySelector('#weather-mode');
  const seasonEl=hud.querySelector('#wc-season'),tempEl=hud.querySelector('#wc-temp'),rainEl=hud.querySelector('#wc-rain'),windEl=hud.querySelector('#wc-wind'),dryEl=hud.querySelector('#wc-dry');
  let updatingControls=false,sendTimer=null;
  const pct=v=>Math.round((Number(v)||0)*100);
  function tint(cell){const rain=Number(cell.precipitation)||0,cloud=Number(cell.cloud)||0,drought=Number(cell.drought)||0,temp=Number(cell.temperature)||0;if(rain>.55)return`rgba(70,145,200,${Math.min(.20,rain*.18)})`;if(drought>.65)return`rgba(210,155,70,${Math.min(.16,drought*.14)})`;if(temp<2)return`rgba(185,220,245,.10)`;return`rgba(120,150,170,${cloud*.05})`;}
  function weatherClass(w){if(w.drought>.65)return'weather-dry';if(w.precipitation>.5)return'weather-wet';if(w.temperature<3)return'weather-cold';if(w.temperature>31)return'weather-hot';return'';}
  async function control(payload){
    try{await fetch('/api/weather/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});await update();}catch(_err){}
  }
  function syncControls(w){
    updatingControls=true;
    const c=w.control||{};
    modeEl.textContent=c.mode==='manual'?'MANUEL':'AUTO';
    seasonEl.value=c.season||'';
    tempEl.value=Math.round(w.temperature);rainEl.value=pct(w.precipitation);windEl.value=pct(w.wind);dryEl.value=pct(w.drought);
    hud.querySelector('#wc-temp-v').textContent=`${tempEl.value}°`;
    hud.querySelector('#wc-rain-v').textContent=`${rainEl.value}%`;
    hud.querySelector('#wc-wind-v').textContent=`${windEl.value}%`;
    hud.querySelector('#wc-dry-v').textContent=`${dryEl.value}%`;
    updatingControls=false;
  }
  async function update(){
    try{
      const res=await fetch('/api/world',{cache:'no-store'});if(!res.ok)return;
      const data=await res.json(),w=data.weather;if(!w)return;
      hud.className=weatherClass(w);
      readout.textContent=`${w.season} · ${Number(w.temperature).toFixed(1)}°C · pluie ${pct(w.precipitation)}% · vent ${pct(w.wind)}% · sécheresse ${pct(w.drought)}%`;
      for(const cell of w.cells||[]){const idx=cell.y*6+cell.x;if(grid.children[idx])grid.children[idx].style.background=tint(cell);}
      if(!hud.querySelector('#weather-controls').open)syncControls(w);
    }catch(_err){}
  }
  hud.querySelectorAll('[data-preset]').forEach(btn=>btn.addEventListener('click',()=>control({preset:btn.dataset.preset,season:seasonEl.value})));
  hud.querySelector('#wc-auto').addEventListener('click',()=>control({action:'auto'}));
  seasonEl.addEventListener('change',()=>control({season:seasonEl.value}));
  function scheduleManual(){
    if(updatingControls)return;
    hud.querySelector('#wc-temp-v').textContent=`${tempEl.value}°`;hud.querySelector('#wc-rain-v').textContent=`${rainEl.value}%`;hud.querySelector('#wc-wind-v').textContent=`${windEl.value}%`;hud.querySelector('#wc-dry-v').textContent=`${dryEl.value}%`;
    clearTimeout(sendTimer);sendTimer=setTimeout(()=>control({season:seasonEl.value,temperature:Number(tempEl.value),precipitation:Number(rainEl.value)/100,wind:Number(windEl.value)/100,drought:Number(dryEl.value)/100}),220);
  }
  [tempEl,rainEl,windEl,dryEl].forEach(el=>el.addEventListener('input',scheduleManual));
  update();setInterval(update,1200);
})();
