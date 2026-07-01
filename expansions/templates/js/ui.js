// Common UI interactions for expansion sites.
(function() {
  const searchInput = document.getElementById('search-input');
  const searchBtn = document.getElementById('search-btn');
  const searchResults = document.getElementById('search-results');
  const resultsList = document.getElementById('search-results-list');

  function escapeHtml(text) {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function highlightQuery(text, query) {
    if (!text || !query) return escapeHtml(text);
    const q = query.toLowerCase().trim();
    const tokens = q.split(/\W+/).filter(t => t.length > 0);
    if (tokens.length === 0) return escapeHtml(text);
    const pattern = new RegExp(`(${tokens.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi');
    return escapeHtml(text).replace(pattern, '<mark class="bg-accent/30 text-white rounded px-1">$1</mark>');
  }

  function renderField(label, value, query) {
    if (!value || !value.trim()) return '';
    return `<div class="mt-1"><span class="text-xs text-muted uppercase tracking-wide">${label}</span> <span class="text-sm text-gray-100">${highlightQuery(value, query)}</span></div>`;
  }

  function renderResults(results, query) {
    if (!resultsList) return;
    if (results.length === 0) {
      resultsList.innerHTML = '<li class="text-muted">No results found.</li>';
    } else {
      resultsList.innerHTML = results.map(r => {
        const href = (r.kind === 'card' && r.id) ? `${r.url}#card:${encodeURIComponent(r.id)}` : r.url;
        let body = '';
        if (r.kind === 'card' && r.fields) {
          const f = r.fields;
          const meta = [f.type, f.faction, f.group, f.folder].filter(Boolean).join(' · ');
          body = `
            ${meta ? `<p class="text-sm text-muted mt-1">${highlightQuery(meta, query)}</p>` : ''}
            ${renderField('Description', f.description, query)}
            ${renderField('Flavor', f.flavour, query)}
            ${renderField('Stats', f.stats, query)}
            ${renderField('Abilities', f.abilities, query)}
            ${renderField('Placement', f.placement, query)}
            ${renderField('Source', f.source, query)}
            ${renderField('Synergy', f.synergy, query)}
            ${renderField('Prerequisite', f.prereq, query)}
            ${renderField('Color', f.color, query)}
            ${renderField('FAQ', f.faq, query)}
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
