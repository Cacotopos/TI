// Changelog page: severity/aspect/text filtering + click-to-compare modal.
(function () {
  const entries = Array.from(document.querySelectorAll('.cl-entry'));
  const groups = Array.from(document.querySelectorAll('.cl-group'));
  const textInput = document.getElementById('cl-filter-text');
  const severityBox = document.getElementById('cl-severity-filters');
  const aspectBox = document.getElementById('cl-aspect-filters');
  const countEl = document.getElementById('cl-count');
  const emptyEl = document.getElementById('cl-empty');
  const entriesBox = document.getElementById('cl-entries');

  const TYPES = ['new', 'major', 'moderate', 'minor', 'replacement', 'removed', 'added', 'changed'];
  const ASPECTS = ['title', 'art', 'layout', 'flavor', 'ability', 'placement'];
  const activeTypes = new Set(TYPES);
  const activeAspects = new Set();

  const PILL_BASE = 'px-2 py-1 rounded text-xs font-semibold uppercase border cursor-pointer select-none transition-colors';
  const PILL_ON = 'bg-accent text-white border-accent';
  const PILL_OFF = 'bg-bg text-muted border-border hover:text-gray-100';

  function makePill(container, label, active, onToggle) {
    const el = document.createElement('span');
    el.className = `${PILL_BASE} ${active ? PILL_ON : PILL_OFF}`;
    el.textContent = label;
    el.addEventListener('click', () => onToggle(el));
    container.appendChild(el);
    return el;
  }

  function applyFilters() {
    const q = (textInput.value || '').trim().toLowerCase();
    let visible = 0;
    entries.forEach(entry => {
      const type = entry.dataset.type || '';
      const aspects = (entry.dataset.aspects || '').split(' ').filter(Boolean);
      const text = entry.dataset.search || '';
      const typeOk = activeTypes.has(type);
      const aspectOk = activeAspects.size === 0 || aspects.some(a => activeAspects.has(a));
      const textOk = !q || text.includes(q);
      const show = typeOk && aspectOk && textOk;
      entry.classList.toggle('hidden', !show);
      if (show) visible += 1;
    });
    groups.forEach(g => {
      const anyVisible = Array.from(g.querySelectorAll('.cl-entry')).some(e => !e.classList.contains('hidden'));
      g.classList.toggle('hidden', !anyVisible);
    });
    countEl.textContent = `${visible} of ${entries.length} change${entries.length === 1 ? '' : 's'}`;
    emptyEl.classList.toggle('hidden', visible !== 0);
  }

  TYPES.forEach(t => {
    makePill(severityBox, t, true, el => {
      const on = !activeTypes.has(t);
      if (on) activeTypes.add(t); else activeTypes.delete(t);
      el.className = `${PILL_BASE} ${on ? PILL_ON : PILL_OFF}`;
      applyFilters();
    });
  });
  ASPECTS.forEach(a => {
    makePill(aspectBox, a, false, el => {
      const on = !activeAspects.has(a);
      if (on) activeAspects.add(a); else activeAspects.delete(a);
      el.className = `${PILL_BASE} ${on ? PILL_ON : PILL_OFF}`;
      applyFilters();
    });
  });

  textInput.addEventListener('input', applyFilters);
  applyFilters();

  // --- Click-to-compare modal ---
  const modal = document.getElementById('changelog-modal');
  const titleEl = document.getElementById('clm-title');
  const badgesEl = document.getElementById('clm-badges');
  const imagesEl = document.getElementById('clm-images');
  const notesEl = document.getElementById('clm-notes');

  function makeBadge(text, cls) {
    const el = document.createElement('span');
    el.className = cls;
    el.textContent = text;
    return el;
  }

  function makeFigure(src, caption) {
    const fig = document.createElement('figure');
    fig.className = 'text-center';
    const img = document.createElement('img');
    img.src = src;
    img.alt = caption;
    img.className = 'max-w-full max-h-[65vh] mx-auto rounded-lg border border-border';
    const cap = document.createElement('figcaption');
    cap.className = 'text-xs text-muted mt-2';
    cap.textContent = caption;
    fig.appendChild(img);
    fig.appendChild(cap);
    return fig;
  }

  function openModal(entry) {
    const leftLabel = entriesBox.dataset.leftLabel || 'Old';
    const rightLabel = entriesBox.dataset.rightLabel || 'New';
    titleEl.textContent = entry.dataset.name || '';

    badgesEl.innerHTML = '';
    if (entry.dataset.type) {
      badgesEl.appendChild(makeBadge(entry.dataset.type, 'text-xs font-bold uppercase px-2 py-1 rounded bg-slate-700 text-slate-200'));
    }
    (entry.dataset.aspects || '').split(' ').filter(Boolean).forEach(a => {
      badgesEl.appendChild(makeBadge(a, 'text-xs uppercase px-2 py-1 rounded bg-bg border border-border text-muted'));
    });

    imagesEl.innerHTML = '';
    const figs = [];
    if (entry.dataset.left) figs.push(makeFigure(entry.dataset.left, leftLabel));
    if (entry.dataset.right) figs.push(makeFigure(entry.dataset.right, rightLabel));
    figs.forEach(f => imagesEl.appendChild(f));
    imagesEl.className = `grid gap-4 mb-4 ${figs.length === 2 ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1'}`;

    const notes = entry.dataset.notes || '';
    notesEl.textContent = notes;
    notesEl.classList.toggle('hidden', !notes);

    modal.classList.remove('hidden');
    modal.classList.add('flex');
  }

  function closeModal() {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
  }

  entriesBox.addEventListener('click', e => {
    const entry = e.target.closest('.cl-entry');
    if (entry) openModal(entry);
  });
  document.getElementById('clm-close').addEventListener('click', closeModal);
  modal.addEventListener('click', e => {
    if (e.target === modal) closeModal();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !modal.classList.contains('hidden')) closeModal();
  });
})();
