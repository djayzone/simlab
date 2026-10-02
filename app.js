'use strict';

const ARTIFACTS={
  stick:{label:'Bâton',glyph:'│'},
  stone:{label:'Pierre',glyph:'◆'},
  ember:{label:'Braise',glyph:'✦'},
  seed:{label:'Graine',glyph:'●'},
  wheel:{label:'Roue',glyph:'◉'},
  herb:{label:'Plante',glyph:'✤'}
};
const TRAITS=['curiosity','sociability','aggression','empathy','risk','conformity','creativity','trust'];
const DEV_LABELS={perception:'perception',locomotion:'motricité',manipulation:'manipulation',communication:'communication',imitation:'imitation',reasoning:'raisonnement',autonomy:'autonomie'};

const canvas=document.getElementById('world');
const ctx=canvas.getContext('2d');
let world=null,selectedId=null,selectedAgent=null,pollBusy=false,settingTimer=null;
let agentTab='overview';

function artifactMeta(key){
  const remote=world?.artifactCatalog?.[key]||{};
  const local=ARTIFACTS[key]||{};
  return {
    label:remote.label||local.label||key,
    glyph:local.glyph||'◇',
    discovery:remote.discovery||'',
    bonus:remote.bonus||'',
    mechanic:remote.mechanic||null,
    retired:Boolean(remote.retired),
  };
}

function communityColor(id,alpha=1){
  const hue=((Number(id)||0)*137.508)%360;
  return `hsla(${hue},72%,62%,${alpha})`;
}

function diplomacyLabel(state){
  return ({
    allied:'alliance',
    cooperative:'coopération',
    neutral:'neutre',
    rival:'rivalité',
    hostile:'hostilité'
  })[state]||state||'neutre';
}

function diplomacyColor(state,alpha=.7){
  const colors={
    allied:`rgba(104,224,172,${alpha})`,
    cooperative:`rgba(112,193,235,${alpha})`,
    rival:`rgba(255,190,92,${alpha})`,
    hostile:`rgba(255,104,124,${alpha})`
  };
  return colors[state]||`rgba(130,153,164,${alpha})`;
}

const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const bar=v=>`<span class="bar"><i style="width:${clamp(Number(v)||0,0,1)*100}%"></i></span>`;
const pct=v=>`${Math.round((Number(v)||0)*100)}%`;
const esc=value=>String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));

async function api(path,options={}){
  const res=await fetch(path,{cache:'no-store',...options,headers:{'Content-Type':'application/json',...(options.headers||{})}});
  const data=await res.json().catch(()=>({}));
  if(!res.ok) throw new Error(data.detail||data.error||`HTTP ${res.status}`);
  return data;
}

async function refreshWorld(){
  if(pollBusy)return;
  pollBusy=true;
  try{
    world=await api('/api/world');
    syncWorldUI();
    render();
    if(selectedId) await refreshSelected();
    const status=document.getElementById('persistence-status');
    status.textContent='Moteur connecté';
    status.dataset.state='ok';
  }catch(err){
    const status=document.getElementById('persistence-status');
    status.textContent='Moteur indisponible';
    status.dataset.state='error';
    console.error(err);
  }finally{
    pollBusy=false;
  }
}

async function refreshSelected(){
  try{
    selectedAgent=await api(`/api/agents/${selectedId}`);
    renderInspector();
    updateSelectionHud();
  }catch{
    selectedId=null;
    selectedAgent=null;
    renderInspector();
    updateSelectionHud();
  }
}

function syncWorldUI(){
  if(!world)return;
  document.getElementById('stat-pop').textContent=world.population;
  document.getElementById('stat-year').textContent=Number(world.year).toFixed(1);
  document.getElementById('stat-birth').textContent=world.births;
  document.getElementById('stat-death').textContent=world.deaths;
  document.getElementById('stat-age').textContent=Number(world.avgAge).toFixed(1);
  document.getElementById('stat-food').textContent=world.food.length;
  document.getElementById('speed-label').textContent=`×${world.speed}`;

  const toggle=document.getElementById('toggle');
  toggle.querySelector('.play-icon').textContent=world.running?'Ⅱ':'▶';
  toggle.querySelector('.play-label').textContent=world.running?'Pause':'Reprendre';
  document.getElementById('world-state').textContent=world.running?'MONDE ACTIF':'MONDE EN PAUSE';

  document.querySelectorAll('[data-speed]').forEach(button=>{
    button.classList.toggle('active',Number(button.dataset.speed)===Number(world.speed));
  });

  const latest=world.events?.[0];
  document.getElementById('world-pulse').textContent=latest
    ? `An ${Number(latest.year).toFixed(1)} · ${latest.text}`
    : 'Le monde évolue sans événement majeur récent.';
  document.getElementById('ticker-text').textContent=latest
    ? `An ${Number(latest.year).toFixed(1)} · ${latest.text}`
    : 'En attente d’activité…';

  const knowledgeKeys=[...new Set([
    ...Object.keys(ARTIFACTS),
    ...Object.keys(world.knowledge||{}),
    ...Object.keys(world.artifactCatalog||{}),
  ])].filter(key=>!artifactMeta(key).retired).sort((a,b)=>{
    const presentA=world.artifacts.some(item=>item.type===a)?1:0;
    const presentB=world.artifacts.some(item=>item.type===b)?1:0;
    if(presentA!==presentB)return presentB-presentA;
    return (world.knowledge?.[b]?.percent||0)-(world.knowledge?.[a]?.percent||0);
  });
  document.getElementById('knowledge').innerHTML=knowledgeKeys.map(key=>{
    const def=artifactMeta(key);
    const k=world.knowledge?.[key]||{percent:0,hypothesizing:0};
    const present=world.artifacts.some(item=>item.type===key);
    const mechanic=def.mechanic?'<small> · '+esc(def.mechanic)+'</small>':'';
    return `<div class="knowledge-row ${present?'':'muted'}"><span>${def.glyph} ${esc(def.label)}${mechanic}</span><span>${bar(k.percent)} ${Math.round(k.percent*100)}% · ${k.hypothesizing||0} testent</span></div>`;
  }).join('');

  document.getElementById('events').innerHTML=(world.events||[]).slice(0,50).map(e=>
    `<div class="event ${e.kind}"><b>${Number(e.year).toFixed(1)}</b> ${esc(e.text)}</div>`
  ).join('')||'<div class="empty">Aucun événement significatif pour le moment.</div>';

  syncControls();
}

function render(){
  if(!world)return;
  const sx=canvas.width/1200,sy=canvas.height/760;
  ctx.clearRect(0,0,canvas.width,canvas.height);

  const bg=ctx.createLinearGradient(0,0,canvas.width,canvas.height);
  bg.addColorStop(0,'#071622');
  bg.addColorStop(.52,'#09131d');
  bg.addColorStop(1,'#08101a');
  ctx.fillStyle=bg;
  ctx.fillRect(0,0,canvas.width,canvas.height);

  ctx.strokeStyle='rgba(126,196,210,.055)';
  ctx.lineWidth=1;
  for(let x=0;x<1200;x+=60){
    ctx.beginPath();ctx.moveTo(x*sx,0);ctx.lineTo(x*sx,canvas.height);ctx.stroke();
  }
  for(let y=0;y<760;y+=60){
    ctx.beginPath();ctx.moveTo(0,y*sy);ctx.lineTo(canvas.width,y*sy);ctx.stroke();
  }

  for(const water of world.water){
    const glow=ctx.createRadialGradient(water.x*sx,water.y*sy,2,water.x*sx,water.y*sy,(water.r||24)*sx);
    glow.addColorStop(0,'rgba(69,177,231,.46)');
    glow.addColorStop(1,'rgba(42,126,193,.20)');
    ctx.fillStyle=glow;
    ctx.beginPath();ctx.arc(water.x*sx,water.y*sy,(water.r||24)*sx,0,Math.PI*2);ctx.fill();
  }

  ctx.fillStyle='#82d77d';
  for(const food of world.food){
    ctx.beginPath();ctx.arc(food.x*sx,food.y*sy,2.1,0,Math.PI*2);ctx.fill();
  }

  ctx.font='15px ui-monospace,monospace';
  ctx.textAlign='center';
  ctx.textBaseline='middle';
  for(const artifact of world.artifacts){
    ctx.fillStyle='#ffc86b';
    ctx.shadowColor='rgba(255,200,107,.35)';
    ctx.shadowBlur=7;
    ctx.fillText(artifactMeta(artifact.type).glyph,artifact.x*sx,artifact.y*sy);
    ctx.shadowBlur=0;
  }

  const communityById=new Map((world.communities||[]).map(group=>[Number(group.id),group]));
  for(const relation of world.communityRelations||[]){
    if(!relation||relation.state==='neutral')continue;
    const first=communityById.get(Number(relation.communityA));
    const second=communityById.get(Number(relation.communityB));
    if(!first||!second)continue;
    ctx.save();
    ctx.strokeStyle=diplomacyColor(relation.state,.42);
    ctx.lineWidth=relation.state==='hostile'?2:1.2;
    ctx.setLineDash(relation.state==='rival'||relation.state==='hostile'?[7,6]:[]);
    ctx.beginPath();
    ctx.moveTo(first.x*sx,first.y*sy);
    ctx.lineTo(second.x*sx,second.y*sy);
    ctx.stroke();
    ctx.restore();
  }

  for(const agent of world.agents){
    if(agent.communityId!==null&&agent.communityId!==undefined){
      ctx.strokeStyle=communityColor(agent.communityId,.72);
      ctx.lineWidth=1.2;
      ctx.beginPath();
      ctx.arc(agent.x*sx,agent.y*sy,agent.age<3?4.3:agent.age<15?5:6,0,Math.PI*2);
      ctx.stroke();
    }
    ctx.fillStyle=agent.health<35?'#ff7186':agent.sex==='F'?'#ad91ff':'#61e6d1';
    ctx.beginPath();
    ctx.arc(agent.x*sx,agent.y*sy,agent.age<3?2:agent.age<15?2.5:3.2,0,Math.PI*2);
    ctx.fill();

    if(agent.id===selectedId){
      ctx.strokeStyle='#eafcf9';
      ctx.lineWidth=1.7;
      ctx.shadowColor='rgba(99,234,213,.7)';
      ctx.shadowBlur=10;
      ctx.beginPath();ctx.arc(agent.x*sx,agent.y*sy,8,0,Math.PI*2);ctx.stroke();
      ctx.shadowBlur=0;
    }
  }
}

function renderInspector(){
  const root=document.getElementById('inspector');
  const a=selectedAgent;
  if(!a){
    root.innerHTML='<div class="empty">Sélectionne une vie directement sur la carte pour suivre ses besoins, décisions, apprentissages et relations.</div>';
    return;
  }

  const infant=a.age<2,child=a.age<12;
  const stage=infant?'bébé':child?'enfant':a.age<17?'adolescent':'adulte';
  const traits=TRAITS.map(t=>`<div class="mini"><span>${t}</span>${bar(a.traits[t])}<em>${Math.round((a.traits[t]||0)*100)}</em></div>`).join('');
  const dev=Object.entries(a.development||{}).map(([k,v])=>`<div class="mini"><span>${DEV_LABELS[k]||k}</span>${bar(v)}<em>${Math.round(v*100)}</em></div>`).join('');
  const skills=Object.entries(a.skills||{}).sort((x,y)=>y[1].level-x[1].level).slice(0,16).map(([k,v])=>`<div class="mini"><span>${esc(k)}</span>${bar(v.level)}<em>${Math.round(v.level*100)}</em></div>`).join('')||'<span class="muted">Aucune compétence acquise.</span>';
  const rules=Object.entries(a.rules||{}).map(([k,v])=>`<div class="mini"><span>${k}</span>${bar(v)}<em>${Math.round(v*100)}</em></div>`).join('');
  const decisions=Object.entries(a.lastDecision||{}).slice(0,9).map(([k,v])=>`<div class="decision"><span>${k}</span><strong>${Number(v).toFixed(2)}</strong></div>`).join('')||'<span class="muted">Décision en cours.</span>';
  const hypotheses=(a.hypotheses||[]).slice(0,12).map(h=>{const key=(h.subject||'').startsWith('artifact:')?(h.subject||'').slice(9):null;const subject=key?artifactMeta(key).label:(h.subject||'');return `<div class="belief"><b>${esc(subject)}</b><span>${esc(h.action)}</span><span>${bar(h.confidence)} ${pct(h.confidence)}</span><small>+${Number(h.evidence_for||0).toFixed(1)} / -${Number(h.evidence_against||0).toFixed(1)} · ${esc(h.source)}</small></div>`;}).join('')||'<span class="muted">Aucune hypothèse formulée.</span>';
  const concepts=(a.concepts||[]).slice(0,10).map(c=>`<div class="belief"><b>concept</b><span>${esc(c.concept)}</span><span>${bar(c.confidence)} ${pct(c.confidence)}</span><small>${Number(c.evidence||0).toFixed(0)} observations</small></div>`).join('')||'<span class="muted">Aucune généralisation abstraite.</span>';
  const discoveries=Object.entries(a.discoveries||{}).map(([k,y])=>`<div class="decision"><span>${esc(artifactMeta(k).label)}</span><strong>an ${Number(y).toFixed(1)}</strong></div>`).join('')||'<span class="muted">Aucune découverte maîtrisée.</span>';
  const relations=Object.entries(a.relations||{}).sort((x,y)=>y[1].trust-x[1].trust).slice(0,8).map(([id,r])=>`<div class="decision"><span>Vie #${id}</span><strong>${Math.round(r.trust*100)} confiance</strong></div>`).join('')||'<span class="muted">Pas encore de relation stable.</span>';
  const memories=(a.memory||[]).slice(0,8).map(m=>`<li>${esc(m.text)}</li>`).join('')||'<li>Aucun souvenir marquant.</li>';
  const parents=(a.parents||[]).length?a.parents.map(x=>`#${x}`).join(', '):'origine';
  const children=(a.children||[]).length?a.children.map(x=>`#${x}`).join(', '):'aucun';
  const communityRelations=(a.community?.relations||[]).map(r=>
    `<div class="decision"><span>Communauté #${r.communityId}</span><strong>${esc(diplomacyLabel(r.state))} · ${Number(r.score).toFixed(2)}</strong></div>`
  ).join('')||'<span class="muted">Aucune relation inter-communauté connue.</span>';
  const community=a.community
    ? `<div class="decision"><span style="color:${communityColor(a.community.id)}">Communauté #${a.community.id}</span><strong>${a.community.size} membres · ${Math.round((a.community.affinity||0)*100)}% affinité</strong></div>${communityRelations}`
    : '<span class="muted">Cette vie n’appartient encore à aucune communauté.</span>';

  root.innerHTML=`
    <div class="agent-head">
      <div><h3>Vie #${a.id}</h3><span>${a.sex} · ${Number(a.age).toFixed(1)} ans · ${stage} · ${a.alive?'vivante':'décédée'}</span></div>
      <b>${Math.round(a.health)}% santé</b>
    </div>
    <div class="vitals">
      <span>faim ${Math.round(a.hunger)}</span><span>soif ${Math.round(a.thirst)}</span>
      <span>énergie ${Math.round(a.energy)}</span><span>réserves ${a.foodStore}</span>
    </div>
    ${infant?'<p class="hint">Nouveau-né : aucune connaissance technique héritée. Il dépend des soins et apprend progressivement.</p>':''}
    <div class="agent-tabs" role="tablist">
      <button type="button" data-agent-tab="overview" class="${agentTab==='overview'?'active':''}">Essentiel</button>
      <button type="button" data-agent-tab="learning" class="${agentTab==='learning'?'active':''}">Apprentissage</button>
      <button type="button" data-agent-tab="social" class="${agentTab==='social'?'active':''}">Identité & social</button>
    </div>
    <section class="agent-view ${agentTab==='overview'?'active':''}" data-agent-view="overview">
      <div class="agent-block"><h4>Action actuelle · ${esc(a.action)}</h4><p class="muted">${esc(a.actionDetail||'Aucun détail supplémentaire.')}</p>${decisions}</div>
      <div class="agent-block"><h4>Développement</h4>${dev}</div>
    </section>
    <section class="agent-view ${agentTab==='learning'?'active':''}" data-agent-view="learning">
      <div class="agent-block"><h4>Compétences</h4>${skills}</div>
      <div class="agent-block"><h4>Hypothèses</h4>${hypotheses}</div>
      <div class="agent-block"><h4>Concepts</h4>${concepts}</div>
      <div class="agent-block"><h4>Découvertes</h4>${discoveries}</div>
    </section>
    <section class="agent-view ${agentTab==='social'?'active':''}" data-agent-view="social">
      <div class="agent-block"><h4>Traits</h4>${traits}</div>
      <div class="agent-block"><h4>Règles propres</h4>${rules}</div>
      <div class="agent-block"><h4>Communauté & diplomatie</h4>${community}</div>
      <div class="agent-block"><h4>Relations individuelles</h4>${relations}</div>
      <div class="agent-block"><h4>Famille</h4><p class="muted">Parents : ${parents}<br>Enfants : ${children}<br>Naissance : ${Number(a.birthYear).toFixed(1)}${a.deathYear!==null?` · décès : ${Number(a.deathYear).toFixed(1)}`:''}</p></div>
      <div class="agent-block"><h4>Mémoire</h4><ul>${memories}</ul></div>
    </section>`;
}

function updateSelectionHud(){
  const hud=document.getElementById('selection-hud');
  if(!selectedAgent){
    hud.hidden=true;
    hud.innerHTML='';
    return;
  }
  hud.hidden=false;
  const communityHud=selectedAgent.community?.id?` · communauté #${selectedAgent.community.id}`:'';
  hud.innerHTML=`<b>Vie #${selectedAgent.id} · ${esc(selectedAgent.action||'observation')}</b><span>${Number(selectedAgent.age).toFixed(1)} ans · ${Math.round(selectedAgent.health)}% santé${communityHud} · cliquer Observer pour les détails</span>`;
}

function openPanel(id,{toggle=false}={}){
  const panel=document.getElementById(id);
  if(!panel)return;
  const already=panel.classList.contains('is-open');
  document.querySelectorAll('.game-panel').forEach(p=>p.classList.remove('is-open'));
  document.querySelectorAll('.game-dock [data-panel]').forEach(b=>b.classList.remove('active'));
  if(toggle&&already)return;
  panel.classList.add('is-open');
  document.querySelector(`.game-dock [data-panel="${id}"]`)?.classList.add('active');
}

function closePanels(){
  document.querySelectorAll('.game-panel').forEach(p=>p.classList.remove('is-open'));
  document.querySelectorAll('.game-dock [data-panel]').forEach(b=>b.classList.remove('active'));
}

canvas.addEventListener('click',async event=>{
  if(!world)return;
  const rect=canvas.getBoundingClientRect();
  const x=(event.clientX-rect.left)/rect.width*1200;
  const y=(event.clientY-rect.top)/rect.height*760;
  let best=null,bestDistance=28;
  for(const agent of world.agents){
    const distance=Math.hypot(agent.x-x,agent.y-y);
    if(distance<bestDistance){bestDistance=distance;best=agent;}
  }
  selectedId=best?.id||null;
  selectedAgent=null;
  render();
  await refreshSelected();
  if(selectedId)openPanel('observer-panel');
});

document.getElementById('inspector').addEventListener('click',event=>{
  const button=event.target.closest('[data-agent-tab]');
  if(!button)return;
  agentTab=button.dataset.agentTab;
  renderInspector();
});

document.querySelectorAll('.game-dock [data-panel]').forEach(button=>{
  button.addEventListener('click',()=>openPanel(button.dataset.panel,{toggle:true}));
});
document.querySelectorAll('[data-close-panel]').forEach(button=>button.addEventListener('click',closePanels));

document.querySelectorAll('[data-journal-tab]').forEach(button=>{
  button.addEventListener('click',()=>{
    document.querySelectorAll('[data-journal-tab]').forEach(b=>b.classList.toggle('active',b===button));
    document.querySelectorAll('.journal-view').forEach(view=>view.classList.toggle('active',view.id===button.dataset.journalTab));
  });
});

document.querySelectorAll('[data-artifact]').forEach(button=>{
  button.addEventListener('click',()=>{
    document.querySelectorAll('[data-artifact]').forEach(b=>b.classList.toggle('active',b===button));
    document.getElementById('artifactType').value=button.dataset.artifact;
  });
});

document.getElementById('toggle').addEventListener('click',async()=>{
  if(!world)return;
  await api('/api/control',{method:'POST',body:JSON.stringify({running:!world.running})});
  await refreshWorld();
});
document.querySelectorAll('[data-speed]').forEach(button=>button.addEventListener('click',async()=>{
  await api('/api/control',{method:'POST',body:JSON.stringify({speed:Number(button.dataset.speed)})});
  await refreshWorld();
}));

document.getElementById('fullscreen').addEventListener('click',async()=>{
  try{
    if(document.fullscreenElement) await document.exitFullscreen();
    else await document.documentElement.requestFullscreen();
  }catch(error){console.warn('Fullscreen unavailable',error);}
});

document.getElementById('reset').addEventListener('click',async()=>{
  if(!confirm('Réinitialiser définitivement le monde ? Les vies, relations, hypothèses, compétences, connaissances et l’historique courant seront effacés.'))return;
  await api('/api/reset',{method:'POST'});
  selectedId=null;
  selectedAgent=null;
  closePanels();
  await refreshWorld();
  renderInspector();
  updateSelectionHud();
});

document.getElementById('inject').addEventListener('click',async()=>{
  await api('/api/inject',{method:'POST',body:JSON.stringify({
    type:document.getElementById('artifactType').value,
    count:Number(document.getElementById('artifactCount').value)
  })});
  await refreshWorld();
});

document.querySelectorAll('[data-shock]').forEach(button=>button.addEventListener('click',async()=>{
  await api('/api/shock',{method:'POST',body:JSON.stringify({type:button.dataset.shock})});
  await refreshWorld();
}));

const bindings={
  population:'initialPopulation',
  fertility:'fertility',
  mutation:'mutation',
  lifespan:'lifespan',
  foodAbundance:'foodAbundance',
  resourceRespawn:'resourceRespawn',
  learningRate:'learningRate',
  socialLearning:'socialLearning',
  meanCuriosity:'meanCuriosity',
  meanAggression:'meanAggression',
  meanEmpathy:'meanEmpathy',
  scarcityPressure:'scarcityPressure'
};

function renderRange(id){
  const el=document.getElementById(id);
  const out=document.querySelector(`[data-out="${id}"]`);
  if(!el||!out)return;
  out.textContent=el.dataset.percent==='1'?`${Math.round(Number(el.value)*100)}%`:el.value;
}

for(const[id,key]of Object.entries(bindings)){
  const el=document.getElementById(id);
  renderRange(id);
  el.addEventListener('input',()=>{
    renderRange(id);
    clearTimeout(settingTimer);
    settingTimer=setTimeout(async()=>{
      await api('/api/settings',{method:'POST',body:JSON.stringify({settings:{[key]:Number(el.value)}})});
    },180);
  });
}

function syncControls(){
  if(!world)return;
  for(const[id,key]of Object.entries(bindings)){
    const el=document.getElementById(id);
    if(world.settings[key]!==undefined&&document.activeElement!==el){
      el.value=world.settings[key];
      renderRange(id);
    }
  }
}

document.querySelectorAll('[data-preset]').forEach(button=>button.addEventListener('click',async()=>{
  const preset=button.dataset.preset;
  let settings={};
  if(preset==='cooperative')settings={meanAggression:.08,meanEmpathy:.82,socialLearning:.78,foodAbundance:.62};
  if(preset==='harsh')settings={meanAggression:.46,meanEmpathy:.34,scarcityPressure:.72,foodAbundance:.31,fertility:.19};
  if(preset==='research')settings={meanCuriosity:.82,learningRate:.38,socialLearning:.68,mutation:.13};
  await api('/api/settings',{method:'POST',body:JSON.stringify({settings})});
  await refreshWorld();
}));

document.getElementById('export').addEventListener('click',()=>{
  if(!world)return;
  const blob=new Blob([JSON.stringify({version:3,settings:world.settings},null,2)],{type:'application/json'});
  const link=document.createElement('a');
  link.href=URL.createObjectURL(blob);
  link.download='sim-lab-config.json';
  link.click();
  URL.revokeObjectURL(link.href);
});

document.getElementById('import').addEventListener('change',async event=>{
  const file=event.target.files[0];
  if(!file)return;
  try{
    const data=JSON.parse(await file.text());
    await api('/api/settings',{method:'POST',body:JSON.stringify({settings:data.settings||{}})});
    await refreshWorld();
  }catch(error){
    alert(`Import impossible: ${error.message}`);
  }
});

window.addEventListener('keydown',event=>{
  const target=event.target;
  const typing=target instanceof HTMLInputElement||target instanceof HTMLSelectElement||target instanceof HTMLTextAreaElement;
  if(typing)return;

  if(event.code==='Space'){
    event.preventDefault();
    document.getElementById('toggle').click();
    return;
  }
  if(event.key==='Escape'){
    closePanels();
    return;
  }
  if(event.key.toLowerCase()==='f'){
    event.preventDefault();
    document.getElementById('fullscreen').click();
    return;
  }
  const button=document.querySelector(`.game-dock [data-shortcut="${event.key}"]`);
  if(button){
    event.preventDefault();
    openPanel(button.dataset.panel,{toggle:true});
  }
});

setInterval(()=>{refreshWorld();},500);
renderInspector();
updateSelectionHud();
refreshWorld();
