// Common UI interactions for expansion sites.
(function() {
  const searchInput = document.getElementById('search-input');
  const searchBtn = document.getElementById('search-btn');
  const searchResults = document.getElementById('search-results');
  const resultsList = document.getElementById('search-results-list');

  function escapeHtml(text) {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function renderMarkdown(text) {
    if (!text) return '';
    let html = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/^###### (.*$)/gim, '<h6>$1</h6>')
      .replace(/^##### (.*$)/gim, '<h5>$1</h5>')
      .replace(/^#### (.*$)/gim, '<h4>$1</h4>')
      .replace(/^### (.*$)/gim, '<h3>$1</h3>')
      .replace(/^## (.*$)/gim, '<h2>$1</h2>')
      .replace(/^# (.*$)/gim, '<h1>$1</h1>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="text-accent hover:underline">$1</a>')
      .replace(/^\s*-\s+(.*$)/gim, '<li>$1</li>')
      .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
      .replace(/\n\n/g, '</p><p>')
      .replace(/\n/g, '<br>');
    return `<p class="text-sm text-gray-100">${html}</p>`;
  }

  function highlightQuery(text, query) {
    if (!text || !query) return escapeHtml(text);
    const q = query.toLowerCase().trim();
    const tokens = q.split(/\W+/).filter(t => t.length > 0);
    if (tokens.length === 0) return escapeHtml(text);
    const pattern = new RegExp(`(${tokens.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi');
    return escapeHtml(text).replace(pattern, '<mark class="bg-accent/30 text-white rounded px-1">$1</mark>');
  }

  function highlightHtml(html, query) {
    if (!html || !query) return html;
    const q = query.toLowerCase().trim();
    const tokens = q.split(/\W+/).filter(t => t.length > 0);
    if (tokens.length === 0) return html;
    const tokenPattern = new RegExp(`^(${tokens.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})$`, 'i');
    const div = document.createElement('div');
    div.innerHTML = html;
    const walker = document.createTreeWalker(div, NodeFilter.SHOW_TEXT);
    const textNodes = [];
    while (walker.nextNode()) textNodes.push(walker.currentNode);
    textNodes.forEach(node => {
      const parent = node.parentNode;
      const text = node.textContent;
      const tokens = text.split(/(\W+)/);
      if (tokens.length <= 1) return;
      const fragment = document.createDocumentFragment();
      tokens.forEach(part => {
        if (tokenPattern.test(part)) {
          const mark = document.createElement('mark');
          mark.className = 'bg-accent/30 text-white rounded px-1';
          mark.textContent = part;
          fragment.appendChild(mark);
        } else {
          fragment.appendChild(document.createTextNode(part));
        }
      });
      parent.replaceChild(fragment, node);
    });
    return div.innerHTML;
  }

  function isUnitType(type) { return type && type.startsWith('Unit -'); }

  function formatStats(stats) {
    const labels = { cost: 'Cost', combat: 'Combat', move: 'Move', capacity: 'Capacity' };
    const parts = [];
    ['cost', 'combat', 'move', 'capacity'].forEach(key => {
      const stat = stats?.[key];
      if (!stat || !stat.enabled) return;
      const val = stat.value == null ? '-' : escapeHtml(String(stat.value));
      const multi = (stat.multi != null && stat.multi !== '' && Number(stat.multi) > 1) ? ` (x${stat.multi})` : '';
      parts.push(`<span class="px-2 py-1 rounded-md bg-gray-700 text-gray-100 text-xs whitespace-nowrap">${labels[key]} ${val}${multi}</span>`);
    });
    return parts.join('');
  }

  function formatAbilities(abilities) {
    if (!abilities) return '';
    const parts = [];
    if (abilities.deploy) parts.push('<span class="px-2 py-1 rounded-md bg-gray-700 text-gray-100 text-xs">Deploy</span>');
    if (abilities.planetaryShield) parts.push('<span class="px-2 py-1 rounded-md bg-gray-700 text-gray-100 text-xs">Planetary Shield</span>');
    if (abilities.sustainDamage) parts.push('<span class="px-2 py-1 rounded-md bg-gray-700 text-gray-100 text-xs">Sustain Damage</span>');
    const rolls = [
      ['bombardment', 'Bombardment'],
      ['antiFighterBarrage', 'Anti-Fighter Barrage'],
      ['spaceCannon', 'Space Cannon'],
      ['production', 'Production'],
    ];
    rolls.forEach(([key, label]) => {
      const roll = abilities[key];
      if (!roll) return;
      const val = roll.value != null ? roll.value : roll.target;
      if (val === '' || val == null) return;
      const multi = (roll.multi != null && roll.multi !== '' && Number(roll.multi) > 1) ? ` (x${roll.multi})` : '';
      parts.push(`<span class="px-2 py-1 rounded-md bg-blue-600 text-white text-xs font-semibold">${label} ${val}${multi}</span>`);
    });
    return parts.join('');
  }

  function formatPrereq(prereq, color) {
    const parts = [];
    const colorNames = { G: 'Green', Y: 'Yellow', R: 'Red', B: 'Blue' };
    if (prereq && prereq.enabled && prereq.value) {
      parts.push(`<span class="px-2 py-1 rounded-md bg-gray-700 text-gray-100 text-xs whitespace-nowrap">Prerequisite: ${escapeHtml(prereq.value)}</span>`);
    }
    if (color && colorNames[color]) {
      const colorClasses = { G: 'bg-green-600', Y: 'bg-yellow-500 text-black', R: 'bg-red-600', B: 'bg-blue-600' };
      parts.push(`<span class="px-2 py-1 rounded-md ${colorClasses[color]} text-xs font-semibold whitespace-nowrap">${colorNames[color]}</span>`);
    }
    return parts.join('');
  }

  const PILL_COLORS = {
    hazardous: ['#D31800', 'white'],
    industrial: ['#06B700', 'white'],
    cultural: ['#01A7DB', 'black'],
    influence: ['#56C3F0', 'black'],
    resource: ['#F3D21C', 'black'],
  };
  function pillStyle(bg, text) { return `background-color: ${bg}; color: ${text};`; }

  function formatPlacement(placement) {
    if (!placement || !placement.enabled || !placement.rules || !placement.rules.length) return '';
    const labels = { any: 'Any', hazardous: 'Hazardous', industrial: 'Industrial', cultural: 'Cultural', legendary: 'Legendary', tech_planet: 'Tech Planet', frontier_special: 'Frontier/special', mecatol: 'Mecatol Rex', relic: 'Relic' };
    const parts = placement.rules.map(r => {
      const label = labels[r.value] || r.value;
      const [bg, text] = r.not ? ['#B91C1C', 'white'] : (PILL_COLORS[r.value] || ['#4F46E5', 'white']);
      return `<span class="px-2 py-1 rounded-md text-xs font-semibold whitespace-nowrap" style="${pillStyle(bg, text)}">${r.not ? 'Not ' : ''}${escapeHtml(label)}</span>`;
    });
    return parts.join('');
  }

  function formatSynergy(synergy) {
    if (!synergy || !synergy.enabled || !synergy.value) return '';
    const colorMap = { G: ['bg-green-600', 'Green'], Y: ['bg-yellow-500 text-black', 'Yellow'], R: ['bg-red-600', 'Red'], B: ['bg-blue-600', 'Blue'] };
    const parts = synergy.value.split('').map(c => {
      const [cls, name] = colorMap[c] || ['bg-gray-700', c];
      return `<span class="px-2 py-1 rounded-md ${cls} text-xs font-semibold whitespace-nowrap">${name}</span>`;
    });
    return parts.join('');
  }

  function formatSource(source, type) {
    if (!source || !source.enabled) return '';
    const parts = [];
    if (source.influence !== undefined && source.influence !== null && source.influence !== '') {
      parts.push(`<span class="px-2 py-1 rounded-md text-black text-xs font-semibold whitespace-nowrap" style="${pillStyle(PILL_COLORS.influence[0], PILL_COLORS.influence[1])}">Influence ${escapeHtml(String(source.influence))}</span>`);
    }
    if (source.resource !== undefined && source.resource !== null && source.resource !== '') {
      parts.push(`<span class="px-2 py-1 rounded-md text-black text-xs font-semibold whitespace-nowrap" style="${pillStyle(PILL_COLORS.resource[0], PILL_COLORS.resource[1])}">Resource ${escapeHtml(String(source.resource))}</span>`);
    }
    if (type === 'Station' || source.station) {
      parts.push('<span class="px-2 py-1 rounded-md bg-gray-500 text-white text-xs font-semibold whitespace-nowrap">Station</span>');
    }
    if (type !== 'Station' && source.trait) {
      const traits = Array.isArray(source.trait) ? source.trait : (source.trait ? [source.trait] : []);
      traits.forEach(trait => {
        const [bg, text] = PILL_COLORS[trait] || ['#374151', 'white'];
        parts.push(`<span class="px-2 py-1 rounded-md text-xs font-semibold whitespace-nowrap capitalize" style="${pillStyle(bg, text)}">${escapeHtml(trait)}</span>`);
      });
    }
    if (source.legendary) parts.push('<span class="px-2 py-1 rounded-md bg-pink-400 text-black text-xs font-semibold whitespace-nowrap">Legendary</span>');
    if (source.relic) parts.push('<span class="px-2 py-1 rounded-md bg-orange-300 text-black text-xs font-semibold whitespace-nowrap">Relic</span>');
    if (source.techSpeciality) parts.push(`<span class="px-2 py-1 rounded-md bg-gray-700 text-gray-100 text-xs whitespace-nowrap">Tech: ${escapeHtml(source.techSpeciality)}</span>`);
    return parts.join('');
  }

  function formatFaq(faq) {
    if (!faq || !faq.length) return '';
    return faq.map(qa => `<div class="bg-bg border border-border rounded-lg p-2 mt-1"><p class="text-sm font-semibold text-gray-100">Q: ${escapeHtml(qa.q)}</p><p class="text-sm text-muted mt-1">A: ${escapeHtml(qa.a)}</p></div>`).join('');
  }

  function renderPillRow(label, pills) {
    if (!pills) return '';
    return `<div class="mt-2"><span class="text-xs text-muted uppercase tracking-wide">${label}</span><div class="flex flex-wrap gap-2 mt-1">${pills}</div></div>`;
  }

  function renderResults(results, query) {
    if (!resultsList) return;
    if (results.length === 0) {
      resultsList.innerHTML = '<li class="text-muted">No results found.</li>';
    } else {
      resultsList.innerHTML = results.map(r => {
        const href = (r.kind === 'card' && r.cardId) ? `${r.url}#card:${encodeURIComponent(r.cardId)}` : r.url;
        let body = '';
        if (r.kind === 'card' && r.fields) {
          const f = r.fields;
          const meta = [f.type, f.faction, f.group, f.folder].filter(Boolean).join(' · ');
          const descriptionHtml = f.description ? highlightHtml(renderMarkdown(f.description), query) : '';
          const flavourHtml = f.flavour ? highlightHtml(`<p class="italic text-muted text-sm mt-1">${escapeHtml(f.flavour)}</p>`, query) : '';
          body = `
            ${meta ? `<p class="text-sm text-muted mt-1">${highlightQuery(meta, query)}</p>` : ''}
            ${descriptionHtml ? `<div class="mt-2">${descriptionHtml}</div>` : ''}
            ${flavourHtml}
            ${renderPillRow('Stats', isUnitType(f.type) ? formatStats(f.stats) : '')}
            ${renderPillRow('Abilities', isUnitType(f.type) ? formatAbilities(f.abilities) : '')}
            ${renderPillRow('Placement', formatPlacement(f.placement))}
            ${renderPillRow('Source', formatSource(f.source, f.type))}
            ${renderPillRow('Prerequisite', formatPrereq(f.prereq, f.color))}
            ${renderPillRow('Synergy', formatSynergy(f.synergy))}
            ${f.faq && f.faq.length ? `<div class="mt-2"><span class="text-xs text-muted uppercase tracking-wide">FAQ</span>${formatFaq(f.faq)}</div>` : ''}
          `;
        } else {
          const snippet = r.text ? (r.text.length > 240 ? r.text.slice(0, 240) + '\u2026' : r.text) : '';
          body = snippet ? `<p class="text-muted text-sm mt-1">${highlightQuery(snippet, query)}</p>` : '';
        }
        return `<li class="border-b border-border py-3 last:border-0">
          <a href="${href}" class="font-semibold text-gray-100 hover:text-accent">${highlightQuery(r.title, query)}</a>
          <span class="ml-2 text-xs px-2 py-0.5 rounded-full bg-border text-muted">${r.kind}</span>
          ${body}
        </li>`;
      }).join('');
    }
    if (searchResults) searchResults.classList.remove('hidden');
  }

  async function runSearch() {
    if (!searchInput) return;
    if (window.searchReady) await window.searchReady;
    if (typeof window.searchExpansion !== 'function') return;
    const query = searchInput.value.trim();
    if (!query) {
      if (searchResults) searchResults.classList.add('hidden');
      return;
    }
    renderResults(window.searchExpansion(query), query);
  }

  if (searchInput) {
    searchInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') runSearch();
    });
  }
  if (searchBtn) {
    searchBtn.addEventListener('click', runSearch);
  }

  console.log('ui.js loaded');
})();
