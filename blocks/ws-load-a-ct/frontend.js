// ── EsaSim block ──────────────────────────────────────────────────────
// Load a CT (ws-load-a-ct) · version 4 · view, JavaScript: function render(ctx)
// The View's loading dialog for CT scans: drop or choose a folder from your computer (a whole CD/DVD export is fine), see its series, tick the ones to segment and press Load; or give a folder on a worke
// Workspace: Gianluca De Novi's workspace · Author: Gianluca De Novi
// Saved: 2026-11-27
//
// Inputs   ctx.input("id") gives { files, stream }; ctx.rows("id"), ctx.json("id"), ctx.text("id")
//   live        Stream                    Live · several · optional · The loader's live telemetry (channel ct_load), through a Telemetry block
// Settings ctx.params.key
//   loader_node text      Loader node = "load"
//   seg_node    text      Segmentation node = "seg"
// EsaSim rewrites these lines from the block's definition each time it is saved: change the definition, not them.
// ── end of EsaSim block header ────────────────────────────────────────

/* Load a CT · the View's loading dialog for the CT to 3D anatomy flows.
   From this computer: drop or choose the folder that holds the scans (a whole CD/DVD export is fine: DICOMDIR, DICOM/,
   IHE_PDI/…), see the series it holds, tick the ones to segment, and press Load: the run starts, and the ticked
   images (only those, compressed) go to the run's CT loader block, then the segmentation and the 3D anatomy follow.
   From a worker's folder: the scans are already on a worker; give the path. Wired files: the demo case or a Dataset
   block wired to the loader. Patient names and IDs are never read: only the tags that group and order the images. */
function render(ctx) {
  const P = ctx.params || {};
  const LOAD = String(P.loader_node || 'load').trim() || 'load';
  const SEG = String(P.seg_node || 'seg').trim() || 'seg';
  const CHANNEL = 'ct-load', TELE = 'ct_load', PIECE = 192 * 1024, WIN = 6;
  const MEM = (globalThis.__ctLoad = globalThis.__ctLoad || {});        // files picked, kept while the page lives
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const mb = n => n >= 1e9 ? (n / 1e9).toFixed(2) + ' GB' : n >= 1e7 ? Math.round(n / 1e6) + ' MB' : (n / 1e6).toFixed(1) + ' MB';
  const TASKS = ['total', 'total_mr', 'body', 'lung_vessels', 'liver_vessels', 'liver_segments', 'kidney_cysts', 'pleural_pericard_effusion',
    'cerebral_bleed', 'hip_implant', 'head_glands_cavities', 'headneck_bones_vessels', 'head_muscles', 'headneck_muscles'];
  const RES = ['1.5 mm (best)', '3 mm (fast)', '6 mm (fastest)'];
  const DEV = ['auto', 'NVIDIA GPU', 'CPU'];
  const CHOICE = ['The best CT series of each study', 'Every CT series', 'Only these series'];

  let st = Object.assign({ tab: 'local', task: 'total', res: RES[0], dev: 'auto', folder: '', choice: CHOICE[0], only: '' }, ctx.state || {});
  let scan = MEM.scan || null;            // what the picked folder holds
  let busy = '', note = '', sending = null, live = null, lastMode = '';

  const CSS = `
  .ct{--acc:#4c8dff;--ok:#2b8a4a;--warn:#c98a1b;--bad:#c33;--ln:var(--line,#8884);height:100%;display:flex;flex-direction:column;box-sizing:border-box;font-size:12.5px;min-height:0}
  .ct *{box-sizing:border-box}
  .ct .hd{display:flex;align-items:center;gap:8px;padding:6px 10px;border-bottom:1px solid var(--ln);flex-wrap:wrap}
  .ct .hd b{font-size:13px}.ct .sp{flex:1}
  .ct .tabs{display:flex;gap:4px}
  .ct .tab{border:1px solid var(--ln);background:none;color:inherit;border-radius:6px;padding:3px 9px;cursor:pointer;font-size:12px}
  .ct .tab.on{background:rgba(76,141,255,.22);border-color:var(--acc)}
  .ct .body{flex:1;overflow:auto;padding:8px 10px;min-height:0}
  .ct .dz{border:2px dashed var(--ln);border-radius:10px;padding:18px 12px;text-align:center;line-height:1.6}
  .ct .dz.drop{border-color:var(--acc);background:rgba(76,141,255,.08)}
  .ct .btn{border:1px solid var(--ln);background:rgba(127,127,127,.12);color:inherit;border-radius:6px;padding:4px 10px;cursor:pointer;font-size:12px;white-space:nowrap}
  .ct .btn:hover{background:rgba(127,127,127,.25)}.ct .btn:disabled{opacity:.4;cursor:default}
  .ct .btn.pri{background:var(--acc);border-color:var(--acc);color:#fff;font-weight:600}
  .ct .btn.big{font-size:13.5px;padding:7px 16px;box-shadow:0 0 0 3px rgba(76,141,255,.3)}
  .ct .hint{opacity:.68;font-size:11.5px;line-height:1.5;margin:6px 0}
  .ct .row{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:8px 0}
  .ct label.f{display:flex;flex-direction:column;gap:2px;font-size:11px;opacity:.9}
  .ct select,.ct input[type=text]{background:transparent;color:inherit;border:1px solid var(--ln);border-radius:5px;padding:3px 5px;font-size:12px}
  .ct select option{color:#000}
  .ct input[type=text]{min-width:260px}
  .ct table{width:100%;border-collapse:collapse;margin:6px 0;font-size:12px}
  .ct th{text-align:left;font-weight:600;opacity:.75;border-bottom:1px solid var(--ln);padding:3px 5px;white-space:nowrap}
  .ct td{border-bottom:1px solid rgba(127,127,127,.18);padding:3px 5px;vertical-align:top}
  .ct tr.off td{opacity:.5}.ct td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
  .ct .tag{display:inline-block;border-radius:4px;padding:0 5px;font-size:10.5px;background:rgba(127,127,127,.18)}
  .ct .tag.best{background:rgba(43,138,74,.25)}.ct .tag.skip{background:rgba(201,138,27,.22)}
  .ct .prog{border:1px solid var(--ln);border-radius:8px;padding:8px 10px;margin:8px 0}
  .ct .bar{height:6px;border-radius:3px;background:rgba(127,127,127,.2);overflow:hidden;margin:5px 0}
  .ct .bar i{display:block;height:100%;background:var(--acc);transition:width .3s}
  .ct .steps{display:flex;gap:10px;flex-wrap:wrap;font-size:11.5px}
  .ct .steps span{opacity:.45}.ct .steps span.now{opacity:1;font-weight:600}.ct .steps span.done{opacity:.85;color:var(--ok)}
  .ct .err{color:var(--bad);margin:6px 0}.ct .okk{color:var(--ok)}
  .ct .hidden{display:none!important}
  .ct code{font-size:11.5px}`;

  ctx.el.innerHTML = `<style>${CSS}</style><div class="ct">
    <div class="hd"><b>Load a CT</b><span class="sp"></span>
      <div class="tabs"><button class="tab" data-t="local">From this computer</button><button class="tab" data-t="worker">From a worker's folder</button><button class="tab" data-t="wired">Wired files</button></div>
    </div>
    <div class="body"></div>
    <input type="file" class="pick-dir hidden" webkitdirectory directory multiple>
    <input type="file" class="pick-files hidden" multiple>
  </div>`;
  const root = ctx.el.querySelector('.ct'), body = root.querySelector('.body');
  const pickDir = root.querySelector('.pick-dir'), pickFiles = root.querySelector('.pick-files');
  root.querySelectorAll('.tab').forEach(b => b.addEventListener('click', () => { st.tab = b.dataset.t; save(); paint(); }));
  pickDir.addEventListener('change', e => { picked([...e.target.files].map(f => ({ file: f, rel: f.webkitRelativePath || f.name }))); e.target.value = ''; });
  pickFiles.addEventListener('change', e => { picked([...e.target.files].map(f => ({ file: f, rel: f.name }))); e.target.value = ''; });

  function save() { try { ctx.saveState && ctx.saveState(st, true); } catch (_) {} }

  // ── the run and what the loader says ─────────────────────────────────────────────────────────────────────────
  const runActive = () => !!(ctx.run && ctx.run.active);
  function readLive() {
    const s = ((ctx.input && ctx.input('live')) || {}).stream || [];
    let best = null;
    s.forEach(it => {
      const d = it && (it.data !== undefined ? it.data : it);
      if (!d || typeof d !== 'object' || !d.state || (it.channel && it.channel !== TELE)) return;
      if (!best || (+d.t || 0) >= (+best.t || 0)) best = d;
    });
    if (best) live = best;
    return live;
  }

  // ── picking and reading the folder ───────────────────────────────────────────────────────────────────────────
  async function picked(list) {
    if (!list.length) return;
    const seenRel = {};                                          // files of the same name from different folders
    list.forEach(x => { const k = x.rel.toLowerCase(); if (seenRel[k]) x.rel = 'f' + (++seenRel[k]) + '/' + x.rel; else seenRel[k] = 1; });
    busy = 'Reading the headers…'; note = ''; paint();
    try {
      scan = await scanFiles(list, (i, n) => { busy = `Reading the headers: ${i} of ${n} files`; paintBusy(); });
      MEM.scan = scan;
      if (st.pending && st.uids && st.uids.length) {          // the same folder again after the run started: same series
        const keep = scan.series.filter(s => st.uids.includes(s.key));
        if (keep.length) scan.series.forEach(s => { s.on = st.uids.includes(s.key); });
      }
    } catch (e) { note = 'Could not read the folder: ' + ((e && e.message) || e); }
    busy = ''; paint();
    // the run is going and waits: send now, if the series to send are known (ticked before the run started)
    if (waitingForFiles() && st.uids && st.uids.length && scan && scan.series.some(s => s.on && st.uids.includes(s.key))) sendNow();
  }
  async function entriesOf(dt) {      // a folder dropped on the page: walk it
    const out = [], walk = async (en, path) => {
      if (en.isFile) { const f = await new Promise((ok, no) => en.file(ok, no)); out.push({ file: f, rel: path + en.name }); return; }
      if (en.isDirectory) {
        const rd = en.createReader();
        for (;;) { const batch = await new Promise((ok, no) => rd.readEntries(ok, no)); if (!batch.length) break; for (const c of batch) await walk(c, path + en.name + '/'); }
      }
    };
    const items = [...(dt.items || [])].map(i => i.webkitGetAsEntry && i.webkitGetAsEntry()).filter(Boolean);
    if (items.length) { for (const en of items) await walk(en, ''); return out; }
    return [...(dt.files || [])].map(f => ({ file: f, rel: f.name }));
  }

  // ── sending to the loader ────────────────────────────────────────────────────────────────────────────────────
  function chosenFiles() {
    if (!scan) return [];
    const out = [];
    scan.series.filter(s => s.on).forEach(s => s.files.forEach(f => out.push(f)));
    return out;
  }
  function settings() { const o = {}; o[SEG] = { task: st.task, resolution: st.res, device: st.dev }; return o; }
  function start(params, extra) {
    if (runActive()) { note = 'A run is already going: wait for it to end, or stop it, then load again.'; paint(); return; }
    Object.assign(st, extra || {}); save();
    busy = 'Starting the run…'; note = ''; paint();
    let p;
    try { p = ctx.run({ params: Object.assign(settings(), params) }); }
    catch (e) { p = Promise.reject(e); }
    Promise.resolve(p).then(() => { busy = ''; paint(); }, e => {
      busy = ''; st.pending = false; save();
      note = 'The run could not start: ' + ((e && e.message) || e) + '. Press Run in the flow\'s editor if this view cannot start runs here.'; paint();
    });
  }
  function uploadParams(mr) { const lp = {}; lp[LOAD] = { source: 'Upload from the View', series: 'Every CT series', min_images: 1, modalities: mr ? 'CT, MR' : 'CT', wait_minutes: 30 }; return lp; }
  function startReceiving() {                                    // ① the run first: then the folder is chosen once
    const session = Math.random().toString(36).slice(2, 10);
    start(uploadParams(st.task === 'total_mr'), { pending: true, session, uids: [], labels: [] });
  }
  function loadLocal() {                                         // a preview first: the run starts, the folder is asked again
    const files = chosenFiles();
    if (!files.length) { note = 'Tick at least one series.'; paint(); return; }
    if (loaderWaiting() || runActive()) { sendNow(); return; }
    const session = Math.random().toString(36).slice(2, 10);
    MEM.files = files; MEM.session = session;                    // (kept if the page does not show the view again)
    const mr = scan.series.some(s => s.on && s.modality === 'MR');
    start(uploadParams(mr), { pending: true, session, uids: scan.series.filter(s => s.on).map(s => s.key),
      labels: scan.series.filter(s => s.on).map(s => s.label) });
  }
  function sendNow() {                                           // the run waits: these files go now
    const files = chosenFiles();
    if (!files.length) { note = 'Tick at least one series.'; paint(); return; }
    if (!runActive()) { note = 'No run is going on: press Start.'; paint(); return; }
    const d = readLive(), again = !!(d && d.state === 'receiving' && d.session && d.session === st.session && +d.files === files.length);
    st.pending = true; note = '';
    if (!again) st.session = Math.random().toString(36).slice(2, 10);
    MEM.resume = again;
    st.uids = scan.series.filter(s => s.on).map(s => s.key); st.labels = scan.series.filter(s => s.on).map(s => s.label);
    MEM.files = files; MEM.session = st.session; save();
    resume();
  }
  async function resume() {      // the run is going and the loader waits: send the files
    if (sending) return;
    const files = haveFiles() ? MEM.files : null;
    if (!files || !files.length) { paint(); return; }           // (the dialog asks to choose the folder)
    if (!loaderWaiting()) { paint(); return; }                   // (the loader is not listening yet: next tick)
    sending = { session: st.session, n: files.length, sent: 0, bytes: 0, total: files.reduce((n, f) => n + f.file.size, 0), round: 1, resume: !!MEM.resume };
    MEM.resume = false;
    paint();
    try {
      if (sending.resume) await post({ cmd: 'end', session: st.session });    // (the loader says what it still needs)
      else {
        await post({ cmd: 'begin', session: st.session, count: files.length, bytes: sending.total });
        await sendSome(files, files.map((_, i) => i));
      }
      for (let round = 2; round <= 8; round++) {                 // the loader says which files are missing
        const miss = await waitMissing();
        if (!miss || !miss.length) break;
        sending.round = round; paint();
        if (miss === 'all') await post({ cmd: 'begin', session: st.session, count: files.length, bytes: sending.total });
        await sendSome(files, miss === 'all' ? files.map((_, i) => i) : miss);
      }
    } catch (e) {
      note = 'Sending stopped: ' + ((e && e.message) || e) + (runActive() ? '. Press ③ Send again: it goes on with the files the worker does not have yet.' : ' (the run ended)');
    }
    sending = null; paint();
  }
  async function sendSome(files, idx) {
    const gz = typeof CompressionStream === 'function';
    let flying = [];
    for (const i of idx) {
      if (!runActive()) throw new Error('the run ended');
      const f = files[i];
      let bytes = new Uint8Array(await f.file.arrayBuffer());
      if (gz) bytes = new Uint8Array(await new Response(new Blob([bytes]).stream().pipeThrough(new CompressionStream('gzip'))).arrayBuffer());
      try {
        await post({ cmd: 'file', session: st.session, i, rel: f.rel, size: bytes.length, gz });
        for (let off = 0; off < bytes.length || off === 0; off += PIECE) {
          const piece = bytes.subarray(off, off + PIECE);
          flying.push(post({ cmd: 'put', session: st.session, i, off, data: b64(piece) }).catch(e => { sending.failed = (sending.failed || 0) + 1; sending.err = (e && e.message) || String(e); }));
          if (flying.length >= WIN) await flying.shift();
          if (!bytes.length) break;
        }
      } catch (e) {                                              // (left for the next round)
        if (!runActive()) throw e;
        sending.failed = (sending.failed || 0) + 1; sending.err = (e && e.message) || String(e);
      }
      sending.sent++; sending.bytes += f.file.size; paintProgress();
    }
    await Promise.all(flying);
    await post({ cmd: 'end', session: st.session });
  }
  async function waitMissing() {     // after "end": the loader either moves on, or lists the files to send again
    for (let t = 0; t < 240; t++) {
      await new Promise(r => setTimeout(r, 500));
      const d = readLive();
      if (!d || d.session && d.session !== st.session) continue;
      if (['received', 'looking', 'reading', 'done'].includes(d.state)) return [];
      if (d.state === 'error') return null;
      if (d.state === 'receiving' && Array.isArray(d.missing) && d.missing.length && (+d.t || 0) * 1000 > Date.now() - 8000) return d.missing;
      if (d.state === 'waiting' && t > 10) return 'all';         // (it never heard the start: everything again)
      if (!runActive()) return null;
    }
    return null;
  }
  async function post(m, tries = 6) {     // one message to the loader: a failed one is tried again, with a growing pause
    for (let k = 0; ; k++) {
      try { const r = await ctx.send(CHANNEL, m); if (r && r.ok === false) throw new Error(r.error || 'not sent'); return; }
      catch (e) { if (k >= tries - 1 || !runActive()) throw e; await new Promise(r => setTimeout(r, 500 * Math.pow(2, k))); }
    }
  }
  function b64(u) { let s = ''; for (let i = 0; i < u.length; i += 32768) s += String.fromCharCode.apply(null, u.subarray(i, i + 32768)); return btoa(s); }

  function forget() { MEM.files = null; }
  // The page shows the views again (new frames) when a run starts: files picked before that are gone, and a
  // sandboxed view has no storage to keep them. So: start the run first, then choose the folder (one pick); or,
  // after a preview, choose the same folder once more, and the series ticked before go by themselves.
  const loaderWaiting = () => { const d = readLive(); return runActive() && !!d && (d.state === 'waiting' || d.state === 'receiving'); };
  const haveFiles = () => !!(MEM.session && MEM.session === st.session && MEM.files && MEM.files.length);
  const waitingForFiles = () => loaderWaiting() && !sending;        // a run whose loader waits for an upload
  const needFolder = () => waitingForFiles() && !haveFiles();

  // ── drawing ──────────────────────────────────────────────────────────────────────────────────────────────────
  const sel = (key, opts, cur) => `<select data-k="${key}">${opts.map(o => `<option${o === cur ? ' selected' : ''}>${esc(o)}</option>`).join('')}</select>`;
  const segRow = () => `<div class="row">
      <label class="f">Task ${sel('task', TASKS, st.task)}</label>
      <label class="f">Resolution ${sel('res', RES, st.res)}</label>
      <label class="f">Run on ${sel('dev', DEV, st.dev)}</label></div>`;
  function progressHtml() {
    const d = readLive(), active = runActive();
    if (!active && !(d && d.state === 'done')) return '';
    const S = d && d.state, order = ['starting', 'send', 'read', 'segment', 'done'];
    let now = 'starting';
    if (S === 'waiting' || S === 'receiving' || sending) now = 'send';
    if (S === 'received' || S === 'looking' || S === 'reading') now = 'read';
    if (S === 'done' && active) now = 'segment';
    if (S === 'done' && !active) now = 'done';
    const lab = { starting: '① Start the run', send: '② Send the scans', read: '③ Read the series', segment: '④ Segment and build the models', done: '⑤ Done' };
    const step = k => `<span class="${k === now ? 'now' : order.indexOf(k) < order.indexOf(now) ? 'done' : ''}">${lab[k]}</span>`;
    let line = '', pct = 0;
    if (now === 'starting') line = active ? 'The run started: waiting for the loader on the worker…' : 'Starting…';
    if (now === 'send') {
      if (sending) { pct = sending.total ? 100 * sending.bytes / sending.total : 0; line = sending.resume && !sending.sent ? 'Asking the worker which files it still needs…' : `Sending ${sending.sent} of ${sending.n} files (${mb(sending.bytes)} of ${mb(sending.total)})${sending.round > 1 ? ` · round ${sending.round}: the files that did not arrive` : ''}${sending.failed ? ` · ${sending.failed} to send again (${esc(sending.err || '')})` : ''}`; }
      else if (needFolder()) line = 'The run is waiting for your scans: <b>drop the folder</b> in the box below, or press <b>Choose a folder…</b>, then tick the series and press <b>③ Send</b>.';
      else line = d && d.state === 'receiving' ? `The worker has ${d.received || 0} of ${d.files || '?'} files.` : 'The worker is ready.';
    }
    if (now === 'read') { pct = 100; line = d.state === 'looking' ? `Reading the files on the worker (${d.done || 0} of ${d.total || '?'})…` : 'Grouping the images into series and writing the scans…'; }
    if (now === 'segment' || now === 'done') {
      pct = 100;
      const cases = (d.cases || []).map(c => `<code>${esc(c.case)}</code>`).join(', ');
      line = (now === 'segment' ? `Loaded ${cases}. The segmentation and the 3D models follow: watch the run's progress; the 3D anatomy shows the cases as they are done.` : `Loaded ${cases}: choose the case in the 3D anatomy's list.`);
    }
    const err = d && d.state === 'error' ? `<div class="err">${esc(d.error || 'The loader stopped')}: see the run's log.</div>` : '';
    const ws = d && d.series && (now === 'segment' || now === 'done') ? workerTable(d.series) : '';
    return `<div class="prog"><div class="steps">${['starting', 'send', 'read', 'segment', 'done'].map(step).join('')}</div>
      <div class="bar"><i style="width:${Math.round(pct)}%"></i></div><div class="hint">${line}</div>${err}${ws}
      ${sending ? '<button class="btn" data-a="cancel">Cancel</button>' : ''}</div>`;
  }
  function workerTable(list) {
    return `<details><summary class="hint">What the worker found (${list.length} series)</summary><table><tr><th>Series</th><th>Images</th><th>Result</th></tr>${list.map(s =>
      `<tr class="${s.case ? '' : 'off'}"><td>${esc(s.series)}</td><td class="n">${s.images}</td><td>${esc(s.result)}</td></tr>`).join('')}</table></details>`;
  }
  function localHtml() {
    const tbl = scan ? seriesTable() : '';
    const files = chosenFiles(), size = files.reduce((n, f) => n + f.file.size, 0), nOn = scan ? scan.series.filter(s => s.on).length : 0;
    const waiting = runActive(), ready = loaderWaiting();
    const steps = waiting ? '' : `<div class="row"><b>①</b> Choose the segmentation, then press <b>Start</b>; <b>②</b> drop the folder with the scans; <b>③</b> tick the series and press <b>Send</b>.</div>
      ${segRow()}<div class="row"><button class="btn pri" data-a="start">▶ Start</button><span class="hint">The run starts on a worker and waits for your scans (up to 30 minutes).</span></div>`;
    const head = waiting
      ? (ready ? `<b>② The worker is waiting: drop the folder with the scans here</b>` : `<b>The run is starting…</b> you can already drop the folder here`)
      : `<b>Drop the folder with the scans here</b> to see its series first`;
    return `${steps}<div class="dz${waiting && !scan ? ' drop' : ''}">
        ${head}, or <button class="btn${waiting && !scan ? ' pri' : ''}" data-a="dir">Choose a folder…</button> <button class="btn" data-a="files">Choose files…</button>
        <div class="hint">A whole CD/DVD export works as it is (DICOMDIR, DICOM/, IHE_PDI/, viewer files): the images are grouped into series by their DICOM IDs, copies are read once, and pictures, pages and reports are left out. Also NIfTI, NRRD, MHA/MHD and zips.</div>
      </div>
      ${busy ? `<div class="hint">${esc(busy)}</div>` : ''}${tbl}
      ${scan && !sending ? `<div class="row"><button class="btn pri big" data-a="load"${nOn ? '' : ' disabled'}>${waiting ? `③ Send ${nOn} series and segment (${mb(size)})` : `Start and send ${nOn} series (${mb(size)})`}</button>
      <span class="hint">${waiting ? '' : 'The page shows the views again when the run starts and your browser forgets the files: you will choose the folder once more and press Send. (Press ▶ Start first to choose it only once.) '}Only the images of the ticked series are sent, compressed, to the worker that runs the flow. Patient names and IDs are not read here, and the worker writes pixels and geometry only.</span></div>` : ''}`;
  }
  function seriesTable() {
    const s = scan;
    const head = `<div class="hint">${s.files} files: <b>${s.series.length} series</b> in ${s.studies} stud${s.studies === 1 ? 'y' : 'ies'}${s.dups ? `, ${s.dups} copies read once` : ''}${s.other ? `, ${s.other} other files left out (pictures, pages, DICOMDIR…)` : ''}. The best CT series of each study is ticked.</div>`;
    const rows = s.series.map((x, i) => `<tr class="${x.can ? '' : 'off'}">
        <td><input type="checkbox" data-i="${i}"${x.on ? ' checked' : ''}${x.can ? '' : ' disabled'}></td>
        <td>${esc(x.label)}${x.best ? ' <span class="tag best">best</span>' : ''}</td><td>${esc(x.modality)}</td>
        <td class="n">${x.images}</td><td class="n">${x.thick ? x.thick + ' mm' : ''}</td><td class="n">${x.extent ? Math.round(x.extent) + ' mm' : ''}</td>
        <td class="n">${mb(x.bytes)}</td><td>${x.why ? `<span class="tag skip">${esc(x.why)}</span>` : ''}</td></tr>`).join('');
    return head + `<table><tr><th></th><th>Series</th><th>Kind</th><th>Images</th><th>Slices</th><th>Covers</th><th>Size</th><th></th></tr>${rows}</table>`;
  }
  function workerHtml() {
    return `<div class="hint">The scans are already on a worker (a disc copied to its disk, a network share it sees). Give the folder's full path as that worker sees it: the run must go to that worker (choose it in the run panel).</div>
      <div class="row"><label class="f">Folder on the worker <input type="text" data-k="folder" placeholder="D:\\CT2013  or  /data/ct/CT2013" value="${esc(st.folder)}"></label></div>
      <div class="row"><label class="f">Series ${sel('choice', CHOICE, st.choice)}</label>
        <label class="f${st.choice === CHOICE[2] ? '' : ' hidden'}">Series to load <input type="text" data-k="only" placeholder="3, 5  or  Abdomen 1.5" value="${esc(st.only)}"></label></div>
      ${segRow()}<div class="row"><button class="btn pri" data-a="worker"${st.folder ? '' : ' disabled'}>Load and segment</button></div>
      <div class="hint">The loader reads every file under the folder, groups the images into series and writes the chosen ones; the list of what it found is in the run's Series table.</div>`;
  }
  function wiredHtml() {
    return `<div class="hint">Run with the files wired into the loader's <b>Files</b> input: as the flow comes, case s1400 of the TotalSegmentator dataset (with the experts' labels, so the network is scored), or a <b>Dataset</b> block you wired there.</div>
      <div class="row"><label class="f">Series ${sel('choice', CHOICE.slice(0, 2), st.choice === CHOICE[2] ? CHOICE[0] : st.choice)}</label></div>
      ${segRow()}<div class="row"><button class="btn pri" data-a="wired">Load and segment</button></div>`;
  }
  function paint() {
    root.querySelectorAll('.tab').forEach(b => b.classList.toggle('on', b.dataset.t === st.tab));
    const prog = progressHtml();
    body.innerHTML = (note ? `<div class="err">${esc(note)}</div>` : '') + `<div class="pg">${prog}</div>` +
      (st.tab === 'worker' ? workerHtml() : st.tab === 'wired' ? wiredHtml() : localHtml());
    const dz = body.querySelector('.dz');
    if (dz) {
      dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('drop'); });
      dz.addEventListener('dragleave', () => dz.classList.remove('drop'));
      dz.addEventListener('drop', async e => { e.preventDefault(); dz.classList.remove('drop'); picked(await entriesOf(e.dataTransfer)); });
    }
    body.querySelectorAll('[data-a]').forEach(b => b.addEventListener('click', () => act(b.dataset.a)));
    body.querySelectorAll('select[data-k],input[type=text][data-k]').forEach(el => el.addEventListener('change', () => { st[el.dataset.k] = el.value; save(); if (el.tagName === 'SELECT') paint(); }));
    body.querySelectorAll('input[type=text][data-k]').forEach(el => el.addEventListener('input', () => { st[el.dataset.k] = el.value; const b = body.querySelector('[data-a=worker]'); if (b) b.disabled = !st.folder; }));
    body.querySelectorAll('input[type=checkbox][data-i]').forEach(el => el.addEventListener('change', () => { scan.series[+el.dataset.i].on = el.checked; paint(); }));
  }
  function paintBusy() { const h = body.querySelector('.dz + .hint'); if (h) h.textContent = busy; else paint(); }
  function paintProgress() { const pg = body.querySelector('.pg'); if (pg) pg.innerHTML = progressHtml(); const c = pg && pg.querySelector('[data-a=cancel]'); if (c) c.addEventListener('click', () => act('cancel')); }
  function act(a) {
    if (a === 'dir') pickDir.click();
    else if (a === 'files') pickFiles.click();
    else if (a === 'load') loadLocal();
    else if (a === 'start') startReceiving();
    else if (a === 'worker') { const lp = {}; lp[LOAD] = { source: 'Folder on the worker', folder: st.folder, series: st.choice, only: st.only }; start(lp, { pending: false }); }
    else if (a === 'wired') { const lp = {}; lp[LOAD] = { source: 'Files wired in', series: st.choice === CHOICE[2] ? CHOICE[0] : st.choice }; start(lp, { pending: false }); }
    else if (a === 'cancel') { try { ctx.send(CHANNEL, { cmd: 'cancel' }); } catch (_) {} st.pending = false; save(); forget(); note = 'Cancelled.'; paint(); }
  }
  function tick() {
    const d = readLive();
    if (st.pending && d && d.session === st.session && ['received', 'looking', 'reading', 'done', 'error'].includes(d.state)) { st.pending = false; save(); forget(); }
    if (runActive() && haveFiles() && d && (d.state === 'waiting' || (d.state === 'receiving' && d.session !== st.session))) resume();
    const mode = [runActive(), loaderWaiting(), haveFiles(), !!sending].join();
    if (mode !== lastMode && !busy) { lastMode = mode; paint(); return; }
    if (!busy) { const pg = body.querySelector('.pg'); if (pg && !sending) paintProgress(); }
  }
  ctx.on('update', tick);
  ctx.on('run', () => { readLive(); tick(); paint(); });
  const timer = setInterval(tick, 1500);
  if (globalThis.__ctLoadTest) globalThis.__ctLoadTest.view = { picked, act, tick, state: () => st, scan: () => scan, sending: () => sending, stop: () => clearInterval(timer) };
  paint(); tick();
}

// ═══ Reading DICOM headers in the browser (only the tags that group and order the images) ═════════════════════════
const CT_IMAGE_SOPS = {
  '1.2.840.10008.5.1.4.1.1.2': 'CT', '1.2.840.10008.5.1.4.1.1.2.1': 'CT', '1.2.840.10008.5.1.4.1.1.2.2': 'CT',
  '1.2.840.10008.5.1.4.1.1.4': 'MR', '1.2.840.10008.5.1.4.1.1.4.1': 'MR', '1.2.840.10008.5.1.4.1.1.4.4': 'MR',
  '1.2.840.10008.5.1.4.1.1.128': 'PT', '1.2.840.10008.5.1.4.1.1.130': 'PT' };
const CT_WANT = {
  '00080016': 'sopClass', '00080018': 'sop', '00080060': 'modality', '00080008': 'imageType', '0008103E': 'desc',
  '0020000D': 'study', '0020000E': 'series', '00200011': 'number', '00180050': 'thick', '00280010': 'rows', '00280011': 'cols',
  '00280008': 'frames', '00200032': 'ipp', '00200037': 'iop', '00200013': 'inst' };
const CT_LONG_VR = new Set(['OB', 'OD', 'OF', 'OL', 'OV', 'OW', 'SQ', 'SV', 'UC', 'UN', 'UR', 'UT', 'UV']);
const CT_VOL = ['.nii.gz', '.nii', '.nrrd', '.nhdr', '.mha', '.mhd'];
const CT_SIDE = ['.raw', '.zraw', '.raw.gz'];
const CT_SKIP = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.htm', '.html', '.css', '.js', '.pdf', '.txt', '.xml', '.xsl', '.xsd', '.inf',
  '.ini', '.exe', '.dll', '.ttf', '.csv', '.json', '.md', '.mp4', '.avi', '.wmv', '.log', '.cab', '.msi', '.swf', '.jar', '.class', '.sys', '.lnk', '.url', '.dat', '.db'];

/** The wanted tags of a DICOM file's start (an ArrayBuffer), or null when it is not DICOM. {more: true} when the
    buffer ended before the tags did (read a larger part). */
function dicomHeader(buf) {
  const v = new DataView(buf), n = buf.byteLength, out = {};
  let p = 0, explicit = true, little = true;
  const str = (o, l) => { let s = ''; for (let i = 0; i < l; i++) { const c = v.getUint8(o + i); if (c) s += String.fromCharCode(c); } return s.trim(); };
  const tagAt = o => ((little ? v.getUint16(o, true) : v.getUint16(o, false)) * 65536 + (little ? v.getUint16(o + 2, true) : v.getUint16(o + 2, false))) >>> 0;
  const hex = t => t.toString(16).toUpperCase().padStart(8, '0');
  if (n >= 132 && str(128, 4) === 'DICM') {
    p = 132;                                                     // the file meta group: explicit VR, little endian
    while (p + 8 <= n && v.getUint16(p, true) === 0x0002) {
      const el = v.getUint16(p + 2, true), vr = str(p + 4, 2), long = CT_LONG_VR.has(vr);
      const len = long ? v.getUint32(p + 8, true) : v.getUint16(p + 6, true), at = p + (long ? 12 : 8);
      if (el === 0x0010) { const ts = str(at, len).replace(/\0/g, ''); explicit = ts !== '1.2.840.10008.1.2'; little = ts !== '1.2.840.10008.1.2.2'; out.ts = ts; }
      if (el === 0x0002) out.mediaClass = str(at, len);
      p = at + len;
    }
  } else {
    if (n < 16) return null;                                     // no preamble: an old file, implicit VR, if it starts with group 8
    const g = v.getUint16(0, true);
    if (g !== 0x0008 && g !== 0x0002) return null;
    explicit = /^[A-Z]{2}$/.test(str(4, 2)); p = 0;
  }
  if (out.ts === '1.2.840.10008.1.2.1.99') { out.deflated = true; return out; }   // (deflated: the worker reads it)
  const skipUndefined = (o, ex) => {                              // an undefined-length sequence: walk its items
    while (o + 8 <= n) {
      const t = tagAt(o);
      if (t === 0xFFFEE0DD) return o + 8;
      if (t === 0xFFFEE000) {
        const l = little ? v.getUint32(o + 4, true) : v.getUint32(o + 4, false);
        if (l === 0xFFFFFFFF) o = walkItem(o + 8, ex); else o = o + 8 + l;
        continue;
      }
      return -1;
    }
    return -2;                                                    // (the buffer ended inside it: read more)
  };
  const walkItem = (o, ex) => {                                   // elements of an item until its delimiter
    while (o + 8 <= n) {
      const t = tagAt(o);
      if (t === 0xFFFEE00D) return o + 8;
      const r = element(o, ex, null);
      if (r < 0) return n + 1;
      o = r;
    }
    return n + 1;
  };
  function element(o, ex, wanted) {
    const t = tagAt(o);
    let vr = '', len, at;
    if (ex && !(t >>> 16 === 0xFFFE)) {
      vr = str(o + 4, 2);
      if (CT_LONG_VR.has(vr)) { len = little ? v.getUint32(o + 8, true) : v.getUint32(o + 8, false); at = o + 12; }
      else if (/^[A-Z]{2}$/.test(vr)) { len = little ? v.getUint16(o + 6, true) : v.getUint16(o + 6, false); at = o + 8; }
      else return -1;
    } else { len = little ? v.getUint32(o + 4, true) : v.getUint32(o + 4, false); at = o + 8; }
    if (len === 0xFFFFFFFF) {
      return skipUndefined(at, vr === 'UN' ? false : ex);
    }
    if (wanted) {
      const key = CT_WANT[hex(t)];
      if (key) {
        if (at + len > n) return -2;
        if (key === 'rows' || key === 'cols') out[key] = little ? v.getUint16(at, true) : v.getUint16(at, false);
        else out[key] = str(at, len);
      }
    }
    return at + len;
  }
  while (p + 8 <= n) {
    const t = tagAt(p);
    if (t >= 0x7FE00010 || (t >>> 16) > 0x0028 && out.rows !== undefined) return out;   // past what we need
    const r = element(p, explicit, true);
    if (r === -2 || r > n) { out.more = true; return out; }
    if (r < 0) return Object.keys(out).length ? out : null;
    p = r;
  }
  out.more = p < n ? false : true;
  return out;
}

/** Reads the headers of the picked files and groups them into series. list: [{file, rel}]. */
async function scanFiles(list, progress) {
  const low = s => s.toLowerCase(), ends = (s, a) => a.some(e => low(s).endsWith(e));
  const entries = [], volumes = [], zips = [];
  let other = 0, done = 0;
  const todo = [];
  const byFolder = {};
  list.forEach(x => { const d = x.rel.split('/').slice(0, -1).join('/'); (byFolder[d] = byFolder[d] || []).push(x); });
  for (const x of list) {
    const name = low(x.rel.split('/').pop()), parts = low(x.rel).split('/');
    if (parts.slice(0, -1).some(q => ['segmentations', 'segmentation', 'masks', 'mask', 'labels', 'label'].includes(q))) { other++; continue; }
    if (ends(name, CT_VOL)) { volumes.push(x); continue; }
    if (ends(name, CT_SIDE)) continue;                          // (sent with their .mhd / .nhdr)
    if (name.endsWith('.zip')) { zips.push(x); continue; }
    if (name === 'dicomdir' || ends(name, CT_SKIP)) { other++; continue; }
    todo.push(x);
  }
  let k = 0;
  async function worker() {
    while (k < todo.length) {
      const x = todo[k++];
      let h = null;
      try {
        h = dicomHeader(await x.file.slice(0, 65536).arrayBuffer());
        if (h && h.more && x.file.size > 65536) h = dicomHeader(await x.file.slice(0, 1 << 20).arrayBuffer());
      } catch (_) { h = null; }
      if (h && h.series && h.sop) entries.push(Object.assign({ x }, h)); else other++;
      done++;
      if (progress && done % 50 === 0) progress(done, todo.length);
    }
  }
  await Promise.all(Array.from({ length: 8 }, worker));
  // group by series, each image once
  const series = {}, seen = new Set(), studies = [];
  let dups = 0;
  entries.forEach(e => {
    if (seen.has(e.sop)) { dups++; return; }
    seen.add(e.sop);
    const s = series[e.series] = series[e.series] || { key: e.series, study: e.study, number: +e.number || 0, desc: e.desc || '', modality: e.modality || '',
      kind: CT_IMAGE_SOPS[e.sopClass] || '', imageType: e.imageType || '', thick: +parseFloat(e.thick) || 0, files: [], pos: [], frames: 0 };
    s.files.push(e.x); s.frames += Math.max(1, +e.frames || 1);
    const ipp = (e.ipp || '').split('\\').map(Number), iop = (e.iop || '').split('\\').map(Number);
    if (ipp.length === 3 && iop.length === 6 && ipp.concat(iop).every(isFinite)) {
      const nn = [iop[1] * iop[5] - iop[2] * iop[4], iop[2] * iop[3] - iop[0] * iop[5], iop[0] * iop[4] - iop[1] * iop[3]];
      s.pos.push(ipp[0] * nn[0] + ipp[1] * nn[1] + ipp[2] * nn[2]); s.axial = Math.abs(nn[2]) > 0.9;
    }
    if (!studies.includes(s.study)) studies.push(s.study);
  });
  const L = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  const safe = t => String(t).replace(/[^A-Za-z0-9.-]/g, '_').replace(/_+/g, '_').replace(/^_+|_+$/g, '').slice(0, 80) || 'case';
  const out = Object.values(series).sort((a, b) => studies.indexOf(a.study) - studies.indexOf(b.study) || a.number - b.number || a.desc.localeCompare(b.desc));
  out.forEach(s => {
    s.images = s.frames;
    s.bytes = s.files.reduce((n, f) => n + f.file.size, 0);
    const z = s.pos.slice().sort((a, b) => a - b);
    s.extent = z.length > 1 ? z[z.length - 1] - z[0] : 0;
    if (!s.thick && z.length > 1) s.thick = Math.round(Math.abs(z[1] - z[0]) * 100) / 100;
    const base = s.desc ? `S${s.number}_${s.desc}` : `S${s.number}`;
    s.label = safe(studies.length > 1 ? `${L[studies.indexOf(s.study) % 26]}_${base}` : base).slice(0, 60);
    s.can = false; s.why = '';
    if (!s.kind) s.why = 'not an image series (' + (s.modality || '?') + ')';
    else if (/LOCALIZER/i.test(s.imageType)) s.why = 'localiser (scout)';
    else { s.can = true; if (s.kind !== 'CT') s.why = s.kind + ': use the task total_mr'; else if (s.images < 20) s.why = 'few images'; }
  });
  // the best CT series of each study, ticked
  const score = s => [s.axial ? 1 : 0, (s.thick || 9) <= 3 ? 1 : 0, s.extent, -(s.thick || 9), s.images];
  const cmp = (a, b) => { const x = score(a), y = score(b); for (let i = 0; i < x.length; i++) if (x[i] !== y[i]) return x[i] - y[i]; return 0; };
  studies.forEach(u => {
    const pool = out.filter(s => s.study === u && s.can && s.kind === 'CT' && s.images >= 20);
    if (pool.length) { const b = pool.reduce((a, c) => cmp(c, a) > 0 ? c : a); b.best = b.on = true; }
  });
  // volumes and zips: one row each (with the sidecar files of .mhd and .nhdr)
  volumes.forEach(x => {
    const name = x.rel.split('/').pop(), dir = x.rel.split('/').slice(0, -1).join('/'), stem = name.replace(/\.(nii\.gz|nii|nrrd|nhdr|mha|mhd)$/i, '');
    const files = [x].concat(/\.(mhd|nhdr)$/i.test(name) ? (byFolder[dir] || []).filter(y => y !== x && low(y.rel.split('/').pop()).startsWith(low(stem)) && ends(y.rel, CT_SIDE)) : []);
    out.push({ key: 'vol:' + x.rel, label: safe(stem), modality: 'volume', kind: 'volume', images: 1, thick: 0, extent: 0, files, bytes: files.reduce((n, f) => n + f.file.size, 0), can: true, on: true, why: '' });
  });
  zips.forEach(x => out.push({ key: 'zip:' + x.rel, label: x.rel.split('/').pop(), modality: 'zip', kind: 'zip', images: 0, thick: 0, extent: 0, files: [x], bytes: x.file.size, can: true, on: true, why: 'unpacked on the worker' }));
  return { files: list.length, series: out, studies: studies.length, dups, other };
}
