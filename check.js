tailwind.config = {
  theme: {
    extend: {
      fontFamily: { jakarta: ['"Plus Jakarta Sans"', 'sans-serif'] },
      colors: {
        brand: { primary: '#C08552', secondary: '#8C5A3C', background: '#FFF8F0', surface: '#FFF8F0', accent: '#4B2E2B' },
        slate: { 950: '#1A1C1A' }
      }
    }
  }
}
  // ── State ──
  const API_URL = 'http://localhost:8000';
  let currentData = null;
  window.currentScene = null;
  window.currentControls = null;
  let isSpeaking = false;
  let wireframeOn = false;
  let highContrast = false;
  let reducedMotion = false;
  let fontSizeIndex = 1;
  let simplified = false;

  const TIER = { high:{icon:'✦',color:'text-green-600',bg:'bg-green-50',border:'border-green-200',fill:'bg-green-500'}, medium:{icon:'◆',color:'text-blue-600',bg:'bg-blue-50',border:'border-blue-200',fill:'bg-blue-500'}, low:{icon:'▲',color:'text-amber-600',bg:'bg-amber-50',border:'border-amber-200',fill:'bg-amber-500'}, fallback:{icon:'⟳',color:'text-red-600',bg:'bg-red-50',border:'border-red-200',fill:'bg-red-500'} };

  // ── Accessibility logic ──
  const fontSizes = ['14px', '16px', '18px'];
  function changeFontSize(direction) {
      if (direction === 0) {
          fontSizeIndex = 1; // Reset to A
      } else {
          fontSizeIndex = Math.max(0, Math.min(2, fontSizeIndex + direction));
      }
      document.body.style.fontSize = fontSizes[fontSizeIndex];
      const btns = document.querySelectorAll('.font-size-btn');
      btns.forEach((b, i) => {
          if (i === fontSizeIndex) {
              b.classList.add('bg-white', 'shadow-sm');
              b.classList.remove('hover:bg-white');
          } else {
              b.classList.remove('bg-white', 'shadow-sm');
              b.classList.add('hover:bg-white');
          }
      });
  }

  function toggleHighContrast() {
      highContrast = !highContrast;
      const root = document.documentElement;
      if (highContrast) {
          root.style.setProperty('--bg', '#ffffff');
          root.style.setProperty('--text', '#000000');
          root.style.setProperty('--surface', '#ffffff');
          root.style.setProperty('--border', '#000000');
          root.style.setProperty('--text-dim', '#333333');
          document.body.classList.add('high-contrast'); // keep existing CSS fallback class
          document.getElementById('wsContrastBtn') && document.getElementById('wsContrastBtn').classList.add('active');
      } else {
          root.style.setProperty('--bg', '#FFF8F0'); // matching update 1 hex
          root.style.setProperty('--text', '#1A1C1A');
          root.style.setProperty('--surface', '#FFF8F0');
          root.style.setProperty('--border', '#e5e7eb');
          root.style.setProperty('--text-dim', '#6b7280');
          document.body.classList.remove('high-contrast');
          document.getElementById('wsContrastBtn') && document.getElementById('wsContrastBtn').classList.remove('active');
      }
  }

  function toggleReducedMotion() {
      reducedMotion = !reducedMotion;
      if (reducedMotion) {
          if (window.currentControls) {
              window.currentControls.autoRotate = false;
          }
          const style = document.createElement('style');
          style.id = 'reduced-motion-style';
          style.textContent = '* { animation: none !important; transition: none !important; }';
          document.head.appendChild(style);
      } else {
          if (window.currentControls) {
              window.currentControls.autoRotate = true;
          }
          const existing = document.getElementById('reduced-motion-style');
          if (existing) existing.remove();
      }
  }

  function toggleSimplified() {
      simplified = !simplified;
      if (window.currentScene) {
          window.currentScene.traverse(function(obj) {
              if (obj.isMesh) {
                  if (Array.isArray(obj.material)) {
                      obj.material.forEach(m => {
                          m.flatShading = simplified;
                          m.needsUpdate = true;
                      });
                  } else {
                      obj.material.flatShading = simplified;
                      obj.material.needsUpdate = true;
                  }
              }
          });
      }
      const btn = document.getElementById('wsSimplifiedBtn');
      if (btn) btn.classList.toggle('active', simplified);
  }

  function toggleAudioDescription(name, description, tier, score, source) {
      if (isSpeaking) {
          window.speechSynthesis.cancel();
          isSpeaking = false;
          document.querySelectorAll('.audio-desc-btn').forEach(b => b.textContent = '🔊');
          return;
      }
      const text = `3D model of ${name}. ${description}. 
                    Source: ${source}. 
                    Confidence level: ${tier}. 
                    Match score: ${Math.round(score * 100)} percent.`;
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.9;
      utterance.onend = () => { 
          isSpeaking = false; 
          document.querySelectorAll('.audio-desc-btn').forEach(b => b.textContent = '🔊');
      };
      window.speechSynthesis.speak(utterance);
      isSpeaking = true;
      document.querySelectorAll('.audio-desc-btn').forEach(b => b.textContent = '⏹');
  }

  function toggleWireframe() {
      wireframeOn = !wireframeOn;
      if (window.currentScene) {
          window.currentScene.traverse(function(obj) {
              if (obj.isMesh) {
                  if (Array.isArray(obj.material)) {
                      obj.material.forEach(m => m.wireframe = wireframeOn);
                  } else {
                      obj.material.wireframe = wireframeOn;
                  }
              }
          });
      }
      const ebtn = document.getElementById('exploreWireframeBtn');
      if (ebtn) ebtn.textContent = wireframeOn ? 'Solid' : 'Wireframe';
      const wbtn = document.getElementById('wsWireframeBtn');
      if (wbtn) wbtn.classList.toggle('active', wireframeOn);
  }

  function handleWorkspaceSpeech() {
      if (!currentData) return;
      const m = currentData.all_results?.[0] || {};
      toggleAudioDescription(currentData.name || 'Untitled', currentData.explanation || '', currentData.confidence_tier || 'medium', currentData.best_score || 0, m.source || m.api_source || 'unknown');
  }
  function toggleSpeechWs() { handleWorkspaceSpeech(); }

  // ── Navigation ──
  function showPage(name) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById('page-' + name).classList.add('active');
    document.querySelectorAll('.nav-link').forEach(l => { l.classList.remove('active'); l.classList.add('text-slate-400'); l.classList.remove('text-slate-950'); });
    const link = document.querySelector(`.nav-link[data-page="${name}"]`);
    if (link) { link.classList.add('active','text-slate-950'); link.classList.remove('text-slate-400'); }
    if (name === 'library') renderLibrary();
    if (name === 'workspace' && currentData) populateWorkspace(currentData);
    if (name === 'analysis' && currentData) populateAnalysis(currentData);
  }

  function escapeHtml(s) { return s ? String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;') : ''; }
  function avatarHtml(name, thumb, sm) {
    const ch = (name||'?')[0].toUpperCase(), cls = sm ? 'letter-avatar-warm letter-avatar-sm' : 'letter-avatar-warm';
    const altText = `${name||'Unknown'} 3D model`;
    if (!thumb) return `<div class="${cls}" role="img" aria-label="${escapeHtml(altText)}">${ch}</div>`;
    return `<div style="position:relative;display:inline-flex"><img src="${thumb}" alt="${escapeHtml(altText)}" class="${sm?'w-9 h-9 rounded-lg object-cover':'w-20 h-20 rounded-2xl object-cover'}" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'"/><div class="${cls}" role="img" aria-label="${escapeHtml(altText)}" style="display:none">${ch}</div></div>`;
  }

  // ── Search ──
  function quickSearch(q) { document.getElementById('searchInput').value = q; if(q) doSearch(); else document.getElementById('searchInput').focus(); }
  async function doSearch() {
    const query = document.getElementById('searchInput').value.trim();
    if (!query) return;
    const btn = document.getElementById('searchBtn');
    btn.disabled = true; btn.innerHTML = '<div class="spinner mx-auto"></div>';
    const sb = document.getElementById('statusBar'); sb.classList.remove('hidden'); sb.classList.add('flex');
    const dot = document.getElementById('statusDot'), txt = document.getElementById('statusText'), badge = document.getElementById('statusBadge');
    dot.className = 'w-2 h-2 rounded-full bg-green-500 animate-pulse'; txt.textContent = 'Searching vector database...'; badge.innerHTML = '';
    document.getElementById('resultsSection').classList.add('hidden');
    document.getElementById('emptyState').classList.add('hidden');
    const fallbackTimeout = setTimeout(() => { txt.textContent = 'Generating fallback via TripoSR (~30-60s)...'; dot.className = 'w-2 h-2 rounded-full bg-red-500 animate-pulse'; }, 7000);
    try {
      const res = await fetch(`${API_URL}/query`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({query, top_k:10}) });
      clearTimeout(fallbackTimeout);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      currentData = data;
      const tier = data.confidence_tier || 'medium', tc = TIER[tier] || TIER.medium;
      dot.className = `w-2 h-2 rounded-full ${data.mode==='fallback'?'bg-red-500':'bg-green-500'}`;
      txt.textContent = data.mode==='fallback' ? `Generated TripoSR model in ${data.latency_ms||0}ms` : `Best match found across 4 domains in ${data.latency_ms||0}ms`;
      badge.innerHTML = `<span class="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${tc.bg} ${tc.color} ${tc.border} border">${tc.icon} ${tier}</span>`;
      if (!data.name && data.mode !== 'fallback') { document.getElementById('emptyState').classList.remove('hidden'); return; }
      renderBestMatch(data); renderTopResults(data.all_results || [], tier);
      document.getElementById('resultsSection').classList.remove('hidden');
      saveToLibrary(query, data);
      populateWorkspace(data); populateAnalysis(data);
    } catch(e) { clearTimeout(fallbackTimeout); dot.className='w-2 h-2 rounded-full bg-red-500'; txt.textContent=`Error: ${e.message}`; }
    finally { btn.disabled = false; btn.textContent = 'Search'; }
  }

  // ── Render Best Match ──
  function renderBestMatch(data) {
    const area = document.getElementById('bestMatchArea');
    const m = data.all_results && data.all_results.length > 0 ? data.all_results[0] : {};
    const tier = data.confidence_tier || 'medium', tc = TIER[tier] || TIER.medium;
    const isFb = data.mode === 'fallback';
    let viewerHtml = '';
    if (data.render_type === 'glb' && data.model_url) {
      viewerHtml = `<div class="viewer-canvas" id="threejs-container"><div id="threejs-badge" class="absolute top-4 left-4 z-10 ${isFb?'bg-red-500/90':'bg-green-500/90'} text-white text-[10px] font-bold uppercase tracking-wider px-3 py-1 rounded-full flex items-center gap-2"><span class="w-1.5 h-1.5 rounded-full bg-white animate-pulse"></span>${isFb?'TripoSR Live':'Live Render'}</div><div id="threejs-loading" class="absolute inset-0 flex items-center justify-center text-slate-400 text-sm z-10">Loading GLB...</div><button onclick="toggleWireframe()" id="exploreWireframeBtn" class="absolute top-4 right-4 z-10 bg-black/50 text-white text-[10px] font-bold uppercase tracking-wider px-3 py-1.5 rounded-full backdrop-blur-sm hover:bg-black/70 transition">Wireframe</button></div>`;
    } else if ((data.render_type==='sketchfab_embed'||data.render_type==='molecule_viewer') && data.embed_url) {
      viewerHtml = `<div class="viewer-canvas"><div class="absolute top-4 left-4 z-10 bg-green-500/90 text-white text-[10px] font-bold uppercase tracking-wider px-3 py-1 rounded-full flex items-center gap-2"><span class="w-1.5 h-1.5 rounded-full bg-white animate-pulse"></span>Interactive 3D</div><iframe src="${data.embed_url}?autostart=0&ui_theme=dark" allowfullscreen loading="lazy"></iframe></div>`;
    } else {
      const thumb = m.thumbnail || m.thumbnail_url || '';
      viewerHtml = `<div class="bg-brand-surface rounded-3xl p-10 flex flex-col items-center justify-center min-h-[300px] gap-4">${avatarHtml(data.name, thumb)}<span class="text-[10px] uppercase tracking-widest text-brand-accent font-semibold">Reference Card</span></div>`;
    }
    const linkUrl = data.model_page_url || data.embed_url || data.model_url || '';
    const linkBtn = linkUrl ? `<a href="${linkUrl.startsWith('http')?linkUrl:API_URL+linkUrl}" target="_blank" class="inline-flex items-center gap-1 px-4 py-2 rounded-full bg-brand-secondary text-white text-xs font-bold hover:opacity-90 transition">↗ View Source</a>` : '';
    area.innerHTML = `<div class="grid md:grid-cols-2 gap-0 bg-white rounded-[2rem] border border-black/5 shadow-[0_20px_40px_rgba(26,28,26,0.05)] overflow-hidden fade-in">
      <div class="relative">${viewerHtml}</div>
      <div class="p-8 flex flex-col justify-between">
        <div>
          ${isFb ? '<div class="flex items-center gap-2 mb-3"><span class="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span><span class="text-[10px] uppercase tracking-widest text-red-500 font-bold">TripoSR GPU Generation</span></div>' : ''}
          <p class="text-[10px] uppercase tracking-widest text-slate-400 mb-1">${escapeHtml(m.source||m.api_source||'database')}</p>
          <div class="flex items-center gap-3 mb-3"><h3 class="text-xl font-extrabold tracking-tight">${escapeHtml(data.name||'Untitled')}</h3><button onclick="toggleAudioDescription('${escapeHtml(data.name||'').replace(/'/g, "\\'")}', '${escapeHtml((data.explanation||'').substring(0,200)).replace(/'/g, "\\'")}', '${tier}', ${data.best_score || 0}, '${escapeHtml(m.source||m.api_source||'database').replace(/'/g, "\\'")}')" class="w-7 h-7 rounded-full border border-black/10 flex items-center justify-center text-sm hover:border-brand-secondary transition audio-desc-btn">🔊</button></div>
          ${data.explanation ? `<p class="text-xs text-slate-500 leading-relaxed mb-4">${escapeHtml(data.explanation)}</p>` : ''}
          <span class="inline-flex items-center gap-1 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider ${tc.bg} ${tc.color} ${tc.border} border mb-4">${tc.icon} ${tier} confidence</span>
        </div>
        <div>
          <div class="space-y-2 mb-4">
            <div class="flex items-center gap-2 text-xs text-slate-500"><span class="w-14">Semantic</span><div class="flex-1 score-bar"><div class="score-fill bg-green-500" style="width:${Math.min((m.faiss_score||0)*100,100)}%"></div></div><span class="w-8 text-right">${(m.faiss_score||0).toFixed(2)}</span></div>
            <div class="flex items-center gap-2 text-xs text-slate-500"><span class="w-14">Relevance</span><div class="flex-1 score-bar"><div class="score-fill bg-blue-500" style="width:${Math.min((m.clip_score||0)*100,100)}%"></div></div><span class="w-8 text-right">${(m.clip_score||0).toFixed(2)}</span></div>
            <div class="flex items-center gap-2 text-xs text-slate-500"><span class="w-14">Structural</span><div class="flex-1 score-bar"><div class="score-fill bg-amber-500" style="width:${Math.min((m.structural_score||0)*100,100)}%"></div></div><span class="w-8 text-right">${(m.structural_score||0).toFixed(2)}</span></div>
          </div>
          ${linkBtn}
        </div>
      </div>
    </div>`;
    if (data.render_type === 'glb' && data.model_url) {
      const mu = String(data.model_url), url = mu.startsWith('http') ? mu : API_URL + mu;
      initThreeJS(url, 'threejs-container', 'threejs-loading');
    }
  }

  // ── Top Results ──
  function renderTopResults(results, tierCtx) {
    const area = document.getElementById('topResultsArea');
    if (!results || results.length < 2) { area.innerHTML = ''; return; }
    const items = results.slice(0, 5);
    area.innerHTML = `<p class="text-[10px] uppercase tracking-[0.15em] text-brand-accent font-semibold mb-4">Top ${items.length} Candidates</p><div class="space-y-3">${items.map((r,i) => {
      const isSf = r.api_source==='sketchfab';
      const pageUrl = r.model_page_url || r.embed_url || '';
      return `<div class="bg-white rounded-2xl border border-black/5 p-4 hover:border-brand-primary/40 transition cursor-pointer group result-card" onclick="renderResult(${i})">
        <div class="flex items-center gap-3">
          <span class="text-xs font-bold text-brand-secondary w-6">#${i+1}</span>
          ${avatarHtml(r.name, r.thumbnail, true)}
          <div class="flex-1 min-w-0"><div class="text-sm font-bold truncate">${escapeHtml(r.name||'Untitled')}</div><div class="text-[10px] text-slate-400">${escapeHtml(r.source||'unknown')}</div></div>
          <span class="text-[10px] px-2 py-0.5 rounded-full font-bold ${isSf?'bg-red-50 text-red-500':'bg-blue-50 text-blue-500'}">${isSf?'Sketchfab':'FAISS'}</span>
          <button onclick="event.stopPropagation();toggleAudioDescription('${escapeHtml(r.name||'').replace(/'/g, "\\'")}', '${escapeHtml((r.description||'').substring(0,100)).replace(/'/g, "\\'")}', 'medium', ${r.faiss_score || r.clip_score || 0}, '${escapeHtml(r.source||'unknown').replace(/'/g, "\\'")}')" class="w-6 h-6 rounded-full border border-black/10 flex items-center justify-center text-xs hover:border-brand-secondary transition audio-desc-btn">🔊</button>
        </div>
        <div class="flex gap-3 mt-3">
          <div class="flex items-center gap-1 text-[10px] text-slate-400 flex-1"><span>Sem</span><div class="flex-1 score-bar"><div class="score-fill bg-green-500" style="width:${Math.min((r.faiss_score||0)*100,100)}%"></div></div><span>${(r.faiss_score||0).toFixed(2)}</span></div>
          <div class="flex items-center gap-1 text-[10px] text-slate-400 flex-1"><span>Rel</span><div class="flex-1 score-bar"><div class="score-fill bg-blue-500" style="width:${Math.min((r.clip_score||0)*100,100)}%"></div></div><span>${(r.clip_score||0).toFixed(2)}</span></div>
          <div class="flex items-center gap-1 text-[10px] text-slate-400 flex-1"><span>Str</span><div class="flex-1 score-bar"><div class="score-fill bg-amber-500" style="width:${Math.min((r.structural_score||0)*100,100)}%"></div></div><span>${(r.structural_score||0).toFixed(2)}</span></div>
        </div>
        <div class="exp-panel hidden mt-3 pt-3 border-t border-black/5">
          ${r.description?`<p class="text-xs text-slate-500 mb-2">${escapeHtml(r.description)}</p>`:''}
          ${pageUrl?`<a href="${pageUrl}" target="_blank" class="text-xs text-brand-secondary font-semibold hover:underline">↗ Open details</a>`:''}
        </div>
      </div>`;}).join('')}</div>`;
  }

  // ── Render Specific Result from Top 5 ──
  function renderResult(index) {
    if (!currentData || !currentData.all_results || !currentData.all_results[index]) return;
    const r = currentData.all_results[index];
    
    // Highlight the clicked result card as active
    document.querySelectorAll('.result-card').forEach((el, i) => {
      if (i === index) el.classList.add('ring-2', 'ring-brand-secondary');
      else el.classList.remove('ring-2', 'ring-brand-secondary');
    });

    // Create synthesized data object
    const mergedData = {
      ...currentData,
      name: r.name,
      render_type: r.render_type,
      model_url: r.model_url,
      embed_url: r.embed_url,
      explanation: r.description || currentData.explanation,
      best_score: r.faiss_score || r.clip_score || currentData.best_score,
      all_results: [r, ...currentData.all_results.filter((_, i) => i !== index)]
    };
    
    // Update main viewer and details
    renderBestMatch(mergedData);
    populateWorkspace(mergedData);
  }

  // ── Three.js (exact same logic) ──
  function initThreeJS(glbUrl, containerId, loadingId) {
    if (!window.THREE || !window.THREE.GLTFLoader) { document.getElementById(loadingId).textContent='Three.js not loaded'; return; }
    const container = document.getElementById(containerId), loading = document.getElementById(loadingId);
    const scene = new THREE.Scene(); window.currentScene = scene;
    scene.background = new THREE.Color(0x1a1a2e);
    scene.add(new THREE.AmbientLight(0xffffff, 2.5));
    const d1 = new THREE.DirectionalLight(0xffffff, 3.0); d1.position.set(5,5,5); scene.add(d1);
    const d2 = new THREE.DirectionalLight(0xffffff, 1.5); d2.position.set(-5,-3,-5); scene.add(d2);
    const d3 = new THREE.DirectionalLight(0xffffff, 2.0); d3.position.set(0,0,10); scene.add(d3);
    const w = container.clientWidth||400, h = container.clientHeight||420;
    const camera = new THREE.PerspectiveCamera(45, w/h, 0.1, 100); camera.position.set(0, 1.5, 3);
    const renderer = new THREE.WebGLRenderer({antialias:true, alpha:true}); renderer.setSize(w,h); renderer.setPixelRatio(window.devicePixelRatio);
    renderer.domElement.style.cssText = 'width:100%;height:100%;display:block;border-radius:16px;';
    container.appendChild(renderer.domElement);
    const controls = window.THREE.OrbitControls ? new window.THREE.OrbitControls(camera, renderer.domElement) : null;
    if (controls) { controls.enableDamping=true; controls.dampingFactor=0.05; controls.autoRotate=true; controls.autoRotateSpeed=2.0; window.currentControls = controls;
      if (reducedMotion) controls.autoRotate = false;
    }
    new window.THREE.GLTFLoader().load(glbUrl, gltf => {
      const model = gltf.scene, box = new THREE.Box3().setFromObject(model), center = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3());
      const scale = 2.0 / (Math.max(size.x,size.y,size.z)||1);
      model.scale.set(scale,scale,scale); model.position.sub(center.multiplyScalar(scale));
      scene.add(model); if(loading) loading.style.display='none';
    }, undefined, err => { console.error(err); if(loading) loading.innerHTML='<span class="text-red-400 text-xs">Error loading GLB</span>'; });
    (function animate(){ requestAnimationFrame(animate); if(controls) controls.update(); renderer.render(scene,camera); })();
    new ResizeObserver(()=>{ const nw=container.clientWidth,nh=container.clientHeight; if(nw&&nh){camera.aspect=nw/nh;camera.updateProjectionMatrix();renderer.setSize(nw,nh);} }).observe(container);
  }



  // ── Workspace Population ──
  function populateWorkspace(data) {
    const m = data.all_results && data.all_results.length > 0 ? data.all_results[0] : {};
    const score = Math.round((data.best_score||0)*100);
    document.getElementById('wsConfScore').textContent = score + '%';
    document.getElementById('wsConfBar').style.width = score + '%';
    document.getElementById('wsConfExplain').textContent = data.explanation || 'No explanation available.';
    document.getElementById('wsSemVal').textContent = (m.faiss_score||0).toFixed(2);
    document.getElementById('wsSemBar').style.width = Math.min((m.faiss_score||0)*100,100)+'%';
    document.getElementById('wsRelVal').textContent = (m.clip_score||0).toFixed(2);
    document.getElementById('wsRelBar').style.width = Math.min((m.clip_score||0)*100,100)+'%';
    document.getElementById('wsStrVal').textContent = (m.structural_score||0).toFixed(2);
    document.getElementById('wsStrBar').style.width = Math.min((m.structural_score||0)*100,100)+'%';
    // Meta
    const metaCard = document.getElementById('wsMetaCard'), metaBody = document.getElementById('wsMetaBody');
    metaCard.classList.remove('hidden');
    metaBody.innerHTML = `<div class="flex justify-between"><span>Name</span><span class="font-bold text-slate-800">${escapeHtml(data.name||'')}</span></div>
      <div class="flex justify-between"><span>Source</span><span class="font-bold text-slate-800">${escapeHtml(m.source||m.api_source||'unknown')}</span></div>
      <div class="flex justify-between"><span>Render</span><span class="font-bold text-slate-800">${data.render_type||'—'}</span></div>
      <div class="flex justify-between"><span>Mode</span><span class="font-bold text-slate-800">${data.mode||'—'}</span></div>`;
    // Viewer
    const vc = document.getElementById('wsViewerContainer'), wl = document.getElementById('wsLoading'), wb = document.getElementById('wsViewerBadge');
    // Clear previous
    vc.querySelectorAll('canvas, iframe').forEach(e => e.remove());
    wl.style.display = 'flex'; wb.classList.add('hidden');
    isWireframe = false; isSimplified = false;
    document.getElementById('wsWireframeBtn')?.classList.remove('active');
    document.getElementById('wsSimplifiedBtn')?.classList.remove('active');
    const isFb = data.mode === 'fallback';
    if (data.render_type === 'glb' && data.model_url) {
      wb.classList.remove('hidden'); wb.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-white animate-pulse"></span>${isFb?'TripoSR Live':'Live Render'}`;
      const mu = String(data.model_url), url = mu.startsWith('http') ? mu : API_URL + mu;
      initThreeJS(url, 'wsViewerContainer', 'wsLoading');
    } else if ((data.render_type==='sketchfab_embed'||data.render_type==='molecule_viewer') && data.embed_url) {
      wb.classList.remove('hidden'); wb.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-white animate-pulse"></span>Interactive 3D';
      const iframe = document.createElement('iframe'); iframe.src = data.embed_url+'?autostart=0&ui_theme=dark'; iframe.allowFullscreen = true; iframe.loading = 'lazy';
      iframe.style.cssText = 'width:100%;height:100%;min-height:420px;border:none;border-radius:16px;';
      vc.appendChild(iframe); wl.style.display = 'none';
    } else {
      wl.innerHTML = `<div class="flex flex-col items-center gap-3">${avatarHtml(data.name, m.thumbnail||m.thumbnail_url)}<span class="text-[10px] uppercase tracking-widest text-slate-400 font-semibold">Reference Card</span></div>`;
    }
    // System msg
    const sysMsg = document.getElementById('wsSystemMsg'), sysTxt = document.getElementById('wsSystemText');
    sysMsg.classList.remove('hidden');
    sysTxt.textContent = data.mode === 'fallback' ? `TripoSR generation complete for "${data.name}". Model rendered in GLB format.` : `Validation complete. "${data.name}" retrieved with ${(data.best_score*100).toFixed(0)}% confidence.`;
  }

  // ── Analysis Population ──
  function populateAnalysis(data) {
    const score = Math.round((data.best_score||0)*100);
    document.getElementById('analysisConfidence').textContent = score + '%';
    document.getElementById('analysisIntegrity').textContent = score >= 60 ? 'Passed' : 'Needs Review';
    document.getElementById('analysisLatency').textContent = (data.latency_ms||0) + 'ms avg';
    document.getElementById('analysisFallbackStatus').textContent = data.mode === 'fallback' ? 'Active Fallback' : 'Standby';
    document.getElementById('analysisFallbackStatus').className = data.mode === 'fallback' ? 'text-xl font-extrabold mb-2 text-red-600' : 'text-xl font-extrabold mb-2';
    document.getElementById('analysisHealth').textContent = score >= 60 ? 'Optimal' : 'Degraded';
    document.getElementById('analysisHealth').className = score >= 60 ? 'text-green-600' : 'text-amber-600';
    document.getElementById('analysisSummaryText').textContent = `Processed query "${document.getElementById('searchInput').value}" with ${score}% confidence and ${(data.latency_ms||0)}ms latency. Mode: ${data.mode||'retrieved'}.`;
  }

  // ── Library (localStorage) ──
  function getLibrary() { try { return JSON.parse(localStorage.getItem('ccai_library')||'[]'); } catch { return []; } }
  function saveToLibrary(query, data) {
    const lib = getLibrary();
    const exists = lib.find(l => l.query.toLowerCase() === query.toLowerCase());
    if (exists) { Object.assign(exists, { data, timestamp: Date.now() }); }
    else { lib.unshift({ query, data, timestamp: Date.now(), domain: data.all_results?.[0]?.source || 'unknown' }); }
    if (lib.length > 30) lib.length = 30;
    localStorage.setItem('ccai_library', JSON.stringify(lib));
  }
  function renderLibrary() {
    let lib = getLibrary();
    const grid = document.getElementById('libraryGrid');
    if (lib.length === 0) { grid.innerHTML = `<div class="col-span-full text-center py-16 text-slate-400 text-sm">No concepts saved yet. Search for something to get started.<br><button onclick="showPage('explore')" class="mt-4 px-6 py-2 rounded-full bg-brand-secondary text-white font-bold text-xs uppercase">Explore</button></div>`; return; }
    grid.innerHTML = lib.map(item => {
      const d = item.data, m = d.all_results?.[0] || {};
      const thumb = m.thumbnail || m.thumbnail_url || '';
      const tier = d.confidence_tier || 'medium';
      const tc = TIER[tier] || TIER.medium;
      return `<div class="bg-white rounded-3xl border border-black/5 overflow-hidden shadow-[0_20px_40px_rgba(26,28,26,0.03)] flex flex-col group">
        <div class="h-44 bg-brand-surface flex items-center justify-center overflow-hidden relative">
          ${thumb ? `<img src="${thumb}" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" onerror="this.outerHTML='<div class=\\'letter-avatar-warm\\'>${(item.query||'?')[0].toUpperCase()}</div>'"/>` : `<div class="letter-avatar-warm">${(item.query||'?')[0].toUpperCase()}</div>`}
          <div class="absolute top-3 left-3 px-2 py-0.5 rounded-full ${tc.bg} ${tc.color} ${tc.border} border text-[10px] font-bold uppercase tracking-wider backdrop-blur-md">${tc.icon} ${tier}</div>
        </div>
        <div class="p-5 flex-1 flex flex-col">
          <div class="text-sm font-bold mb-1">${escapeHtml(d.name || item.query)}</div>
          <p class="text-[10px] text-slate-400 mb-3">${escapeHtml(item.domain)}</p>
          <div class="mt-auto">
            <button onclick="document.getElementById('searchInput').value='${escapeHtml(item.query).replace(/'/g, "\\'")}';showPage('explore');doSearch();" class="w-full py-2.5 rounded-xl bg-brand-surface text-brand-secondary font-bold text-xs hover:bg-brand-secondary hover:text-white transition">View Again</button>
          </div>
        </div>
      </div>`; }).join('');
  }
