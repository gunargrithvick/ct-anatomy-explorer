/* CT Anatomy Explorer – viewer logic (NiiVue). Plain JavaScript, no build step.
 * Layers: 0 = CT, 1 = expert masks, 2 = AI masks, 3 = comparison (computed here in the browser).
 */
(() => {
  'use strict';
  const NV = window.niivue;
  const $ = (s) => document.querySelector(s);
  const WINDOWS = { abdomen: [-160, 240], lung: [-1350, 150], bone: [-450, 1050] }; // W/L 400/40, 1500/-600, 1500/300
  const MODE_HINT = {
    reference: 'Masks drawn by experts (the reference).',
    ai: 'Masks predicted by the VISTA-3D AI model.',
    compare: 'Where the AI agrees with the experts, where it adds extra and where it misses.',
  };
  const state = { manifest: null, caseIdx: 0, mode: 'reference', visible: new Set(), opacity: 0.55,
                  window: 'abdomen', layout: 'multi' };
  let nv = null;
  let L = { ct: 0, ref: 1, ai: -1, cmp: -1 };

  const organs = () => state.manifest.organs;
  const cases = () => state.manifest.cases;
  const current = () => cases()[state.caseIdx];
  const organByIndex = (i) => organs().find((o) => o.index === i);

  init();

  async function init() {
    if (!NV) return fatal('The viewer library (vendor/niivue.umd.js) did not load.');
    nv = new NV.Niivue({
      backColor: [0.04, 0.055, 0.075, 1],
      crosshairColor: [1, 0.85, 0.2, 0.75],
      isRadiologicalConvention: true,
      sagittalNoseLeft: true,
      multiplanarShowRender: NV.SHOW_RENDER.ALWAYS,
      multiplanarLayout: NV.MULTIPLANAR_TYPE.GRID,
      show3Dcrosshair: true,
      isColorbar: false,
      logLevel: 'error',
      loadingText: '',
    });
    await nv.attachTo('gl');
    nv.onLocationChange = onLocation;
    try {
      const r = await fetch('data/cases.json', { cache: 'no-cache' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      state.manifest = await r.json();
    } catch (e) {
      return fatal('Could not load data/cases.json. If you opened index.html directly from your disk, ' +
                   'start a small web server instead: python -m http.server -d docs 8000 and open http://localhost:8000');
    }
    if (!cases().length) return fatal('No cases in data/cases.json yet.');
    if (state.manifest.version) $('#version').textContent = 'v' + state.manifest.version;
    buildCaseSelect();
    wireControls();
    readHash();
    if (window.innerWidth < 700) { state.layout = 'axial'; pressOnly('layout', 'axial'); } // phones: one big view
    await loadCase(state.caseIdx);
  }

  // ------------------------------------------------------------------ loading
  async function loadCase(i) {
    state.caseIdx = i;
    const c = current();
    const hasAI = Boolean(c.files.ai);
    if (!hasAI) state.mode = 'reference';
    showLoading(true);
    const [lo, hi] = WINDOWS[state.window];
    const vols = [
      { url: 'data/' + c.files.ct, name: 'ct.nii.gz', colormap: 'gray', cal_min: lo, cal_max: hi },
      { url: 'data/' + c.files.reference, name: 'reference.nii.gz', opacity: 0 },
    ];
    if (hasAI) vols.push({ url: 'data/' + c.files.ai, name: 'ai.nii.gz', opacity: 0 });
    try {
      await nv.loadVolumes(vols);
    } catch (e) {
      showLoading(false);
      return fatal(`Could not load the scan files for ${c.id}: ${e}`);
    }
    L = { ct: 0, ref: 1, ai: hasAI ? 2 : -1, cmp: -1 };
    if (hasAI) {
      const cmp = nv.volumes[L.ref].clone();
      cmp.name = 'compare';
      nv.addVolume(cmp);
      L.cmp = nv.volumes.length - 1;
    }
    state.visible = new Set(organs().filter((o) => isPresent(c, o)).map((o) => o.index));
    renderCaseInfo(c);
    buildOrganList(c);
    renderMetrics(c);
    renderDownloads(c);
    setModeButtons();
    applyLayers();
    applyLayout();
    const start = (c.focus_mm || {}).liver || Object.values(c.focus_mm || {})[0];
    if (start) jumpTo(start);
    showLoading(false);
    writeHash();
  }

  function isPresent(c, o) {
    const m = c.metrics && c.metrics.organs && c.metrics.organs[o.key];
    if (!m) return Boolean((c.focus_mm || {})[o.key]);
    return m.vol_ref_ml > 0 || m.vol_ai_ml > 0;
  }

  // ------------------------------------------------------------------ layers
  function organLut() {
    const R = [0], G = [0], B = [0], A = [0], I = [0], labels = [''];
    for (const o of organs()) {
      R.push(o.color[0]); G.push(o.color[1]); B.push(o.color[2]);
      A.push(state.visible.has(o.index) ? 255 : 0);
      I.push(o.index); labels.push(o.name);
    }
    return { R, G, B, A, I, labels };
  }

  function compareLut() {
    const R = [0], G = [0], B = [0], A = [0], I = [0], labels = [''];
    for (const [k, v] of Object.entries(state.manifest.compare)) {
      R.push(v.color[0]); G.push(v.color[1]); B.push(v.color[2]); A.push(255); I.push(Number(k)); labels.push(v.name);
    }
    return { R, G, B, A, I, labels };
  }

  function computeCompare() {
    // 1 = agree, 2 = AI only (extra), 3 = missed by AI - using only the organs that are ticked
    const ref = nv.volumes[L.ref].img, ai = nv.volumes[L.ai].img, out = nv.volumes[L.cmp].img;
    const vis = new Uint8Array(256);
    state.visible.forEach((i) => { vis[i] = 1; });
    for (let k = 0; k < out.length; k++) {
      const r = vis[ref[k]] ? ref[k] : 0;
      const a = vis[ai[k]] ? ai[k] : 0;
      out[k] = r === 0 ? (a === 0 ? 0 : 2) : (a === r ? 1 : (a === 0 ? 3 : 2));
    }
  }

  function applyLayers() {
    const lut = organLut();
    nv.volumes[L.ref].setColormapLabel(lut);
    if (L.ai >= 0) nv.volumes[L.ai].setColormapLabel(lut);
    if (L.cmp >= 0) {
      nv.volumes[L.cmp].setColormapLabel(compareLut());
      if (state.mode === 'compare') computeCompare();
    }
    const show = { reference: L.ref, ai: L.ai, compare: L.cmp }[state.mode];
    for (const idx of [L.ref, L.ai, L.cmp]) {
      if (idx >= 0) nv.volumes[idx].opacity = idx === show ? state.opacity : 0;
    }
    const [lo, hi] = WINDOWS[state.window];
    nv.volumes[L.ct].cal_min = lo;
    nv.volumes[L.ct].cal_max = hi;
    nv.updateGLVolume();
    renderLegend();
    $('#modeHint').textContent = MODE_HINT[state.mode];
    if (nv.volumes.length) nv.createOnLocationChange(); // refresh the cursor read-out
  }

  function applyLayout() {
    const t = { multi: nv.sliceTypeMultiplanar, axial: nv.sliceTypeAxial, coronal: nv.sliceTypeCoronal,
                sagittal: nv.sliceTypeSagittal, render: nv.sliceTypeRender }[state.layout];
    nv.opts.show3Dcrosshair = state.layout !== 'render';
    nv.setSliceType(t);
  }

  // ------------------------------------------------------------------ UI builders
  function buildCaseSelect() {
    const sel = $('#caseSelect');
    sel.innerHTML = '';
    cases().forEach((c, i) => {
      const opt = document.createElement('option');
      opt.value = String(i);
      opt.textContent = `${c.title || 'Case ' + (i + 1)}${c.description ? ' – ' + c.description : ''}`;
      sel.appendChild(opt);
    });
  }

  function renderCaseInfo(c) {
    $('#caseSelect').value = String(state.caseIdx);
    $('#caseDesc').textContent = [c.id, c.pathology && c.pathology !== 'no_pathology' ? c.pathology.replace(/_/g, ' ') : '']
      .filter(Boolean).join(' · ');
    const b = $('#caseBadges');
    b.innerHTML = '';
    if (c.demo) b.appendChild(badge('demo', c.demo_note || 'DEMO DATA – for testing the viewer only'));
    if (!c.files.ai) b.appendChild(badge('info', 'AI results not available yet'));
  }

  function badge(kind, text) {
    const s = document.createElement('span');
    s.className = 'badge ' + kind;
    s.textContent = text;
    return s;
  }

  function diceClass(d) {
    if (d === null || d === undefined) return '';
    return d >= 0.9 ? 'good' : d >= 0.8 ? 'ok' : 'bad';
  }

  function buildOrganList(c) {
    const ul = $('#organList');
    ul.innerHTML = '';
    for (const o of organs()) {
      const m = c.metrics && c.metrics.organs ? c.metrics.organs[o.key] : null;
      const present = isPresent(c, o);
      const li = document.createElement('li');
      if (!present) li.className = 'absent';
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = state.visible.has(o.index);
      cb.disabled = !present;
      cb.setAttribute('aria-label', 'Show ' + o.name);
      cb.addEventListener('change', () => {
        if (cb.checked) state.visible.add(o.index); else state.visible.delete(o.index);
        applyLayers();
      });
      const sw = document.createElement('span');
      sw.className = 'sw';
      sw.style.background = `rgb(${o.color.join(',')})`;
      const name = document.createElement('button');
      name.type = 'button';
      name.className = 'name';
      name.textContent = o.name + (present ? '' : ' (not in scan)');
      name.disabled = !present;
      name.addEventListener('click', () => {
        const mm = (c.focus_mm || {})[o.key];
        if (!state.visible.has(o.index)) { state.visible.add(o.index); cb.checked = true; applyLayers(); }
        if (mm) jumpTo(mm);
      });
      const chip = document.createElement('span');
      const d = m ? m.dice : null;
      chip.className = 'chip ' + diceClass(d);
      chip.textContent = d === null || d === undefined ? '–' : d.toFixed(2);
      chip.title = 'Dice (agreement with experts)';
      li.append(cb, sw, name, chip);
      ul.appendChild(li);
    }
  }

  function renderMetrics(c) {
    const tb = $('#metricsTable tbody');
    tb.innerHTML = '';
    const flags = $('#flags');
    flags.innerHTML = '';
    if (!c.metrics) {
      $('#meanDice').textContent = '';
      tb.innerHTML = '<tr><td colspan="5">No AI results for this case yet.</td></tr>';
      return;
    }
    $('#meanDice').textContent = c.metrics.mean_dice != null ? `mean Dice ${c.metrics.mean_dice.toFixed(2)}` : '';
    for (const o of organs()) {
      const m = c.metrics.organs[o.key];
      if (!m || (m.vol_ref_ml === 0 && m.vol_ai_ml === 0)) continue;
      const tr = document.createElement('tr');
      const diff = m.vol_diff_pct == null ? '–' : (m.vol_diff_pct > 0 ? '+' : '') + m.vol_diff_pct.toFixed(0) + '%';
      tr.innerHTML = `<td><span class="dot" style="background:rgb(${o.color.join(',')})"></span>${o.name}</td>` +
        `<td class="${diceClass(m.dice)}">${m.dice == null ? '–' : m.dice.toFixed(2)}</td>` +
        `<td>${m.vol_ref_ml.toFixed(0)}</td><td>${m.vol_ai_ml.toFixed(0)}</td><td>${diff}</td>`;
      tb.appendChild(tr);
    }
    for (const f of c.metrics.flags || []) {
      const d = document.createElement('div');
      d.className = 'flag';
      d.textContent = '⚠ ' + f;
      flags.appendChild(d);
    }
  }

  function renderDownloads(c) {
    const ul = $('#downloads');
    ul.innerHTML = '';
    const items = [
      ['ct', 'CT scan (web copy, NIfTI)'],
      ['reference', 'Expert masks (NIfTI)'],
      ['ai_fullres', 'AI masks, full resolution (NIfTI)'],
      ['metrics_csv', 'Scores for this case (CSV)'],
    ];
    for (const [k, label] of items) {
      if (!c.files[k]) continue;
      const li = document.createElement('li');
      const size = c.size_mb && c.size_mb[k] != null ? ` <small>${c.size_mb[k]} MB</small>` : '';
      li.innerHTML = `<a href="data/${c.files[k]}" download>${label}</a>${size}`;
      ul.appendChild(li);
    }
    const key = 'value,organ\n' + organs().map((o) => `${o.index},${o.name}`).join('\n') + '\n';
    const li = document.createElement('li');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([key], { type: 'text/csv' }));
    a.download = 'label_key.csv';
    a.textContent = 'Label key: mask value → organ (CSV)';
    li.appendChild(a);
    ul.appendChild(li);

    const m = state.manifest;
    $('#aboutText').textContent = `${m.model}. Data: ${m.dataset}. Scans were cropped and resampled to ` +
      `${(c.web_spacing_mm || []).join(' × ')} mm for fast loading; scores were computed on the original scans. ` +
      `The AI may have seen similar public scans during training, so treat the scores as agreement, not as a clinical validation.` +
      (m.generated ? ` Generated ${m.generated}.` : '');
  }

  function renderLegend() {
    const lg = $('#legend');
    if (state.mode !== 'compare') { lg.hidden = true; return; }
    lg.innerHTML = Object.values(state.manifest.compare)
      .map((v) => `<div><i style="background:rgb(${v.color.join(',')})"></i>${v.name}</div>`).join('');
    lg.hidden = false;
  }

  function setModeButtons() {
    const hasAI = L.ai >= 0;
    document.querySelectorAll('[data-mode]').forEach((b) => {
      b.disabled = b.dataset.mode !== 'reference' && !hasAI;
      b.setAttribute('aria-pressed', String(b.dataset.mode === state.mode));
    });
  }

  function pressOnly(attr, value) {
    document.querySelectorAll(`[data-${attr}]`).forEach((b) => b.setAttribute('aria-pressed', String(b.dataset[attr] === value)));
  }

  function wireControls() {
    $('#caseSelect').addEventListener('change', (e) => loadCase(Number(e.target.value)));
    document.querySelectorAll('[data-mode]').forEach((b) => b.addEventListener('click', () => {
      if (b.disabled) return;
      state.mode = b.dataset.mode;
      setModeButtons();
      applyLayers();
      writeHash();
    }));
    document.querySelectorAll('[data-window]').forEach((b) => b.addEventListener('click', () => {
      state.window = b.dataset.window;
      pressOnly('window', state.window);
      applyLayers();
    }));
    document.querySelectorAll('[data-layout]').forEach((b) => b.addEventListener('click', () => {
      state.layout = b.dataset.layout;
      pressOnly('layout', state.layout);
      applyLayout();
    }));
    $('#opacity').addEventListener('input', (e) => {
      state.opacity = Number(e.target.value) / 100;
      $('#opacityVal').textContent = e.target.value + '%';
      applyLayers();
    });
    $('#allOn').addEventListener('click', () => {
      state.visible = new Set(organs().filter((o) => isPresent(current(), o)).map((o) => o.index));
      buildOrganList(current());
      applyLayers();
    });
    $('#allOff').addEventListener('click', () => {
      state.visible = new Set();
      buildOrganList(current());
      applyLayers();
    });
    window.addEventListener('resize', () => nv && nv.resizeListener());
  }

  // ------------------------------------------------------------------ navigation & readout
  function jumpTo(mm) {
    nv.scene.crosshairPos = nv.mm2frac(mm);
    nv.drawScene();
    nv.createOnLocationChange();
  }

  function onLocation(data) {
    if (!data || !data.values || !state.manifest) return;
    const v = (i) => (i >= 0 && data.values[i] ? Math.round(data.values[i].value) : null);
    const name = (val) => { const o = organByIndex(val); return o ? o.name : '—'; };
    const parts = [];
    const hu = v(L.ct);
    if (hu !== null) parts.push(`CT ${hu} HU`);
    parts.push(`Expert: ${name(v(L.ref))}`);
    if (L.ai >= 0) parts.push(`AI: ${name(v(L.ai))}`);
    if (state.mode === 'compare' && L.cmp >= 0) {
      const k = v(L.cmp);
      if (k) parts.push(state.manifest.compare[String(k)].name);
    }
    $('#readout').textContent = parts.join('  ·  ');
  }

  // ------------------------------------------------------------------ helpers
  function showLoading(on) { $('#loading').hidden = !on; }

  function fatal(msg) {
    const el = $('#loading');
    el.hidden = false;
    el.style.padding = '24px';
    el.style.textAlign = 'center';
    el.textContent = msg;
  }

  function readHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    const id = p.get('case');
    const i = cases().findIndex((c) => c.id === id);
    if (i >= 0) state.caseIdx = i;
    if (['reference', 'ai', 'compare'].includes(p.get('mode'))) state.mode = p.get('mode');
  }

  function writeHash() {
    history.replaceState(null, '', `#case=${encodeURIComponent(current().id)}&mode=${state.mode}`);
  }
})();
