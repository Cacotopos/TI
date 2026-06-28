// Common UI interactions for expansion sites.
(function() {
  const searchInput = document.getElementById('search-input');
  const searchBtn = document.getElementById('search-btn');
  const searchResults = document.getElementById('search-results');
  const resultsList = document.getElementById('search-results-list');

  function renderResults(results) {
    if (!resultsList) return;
    if (results.length === 0) {
      resultsList.innerHTML = '<li class="text-muted">No results found.</li>';
    } else {
      resultsList.innerHTML = results.map(r =>
        `<li class="border-b border-border py-2 last:border-0">
          <a href="${r.url}" class="font-semibold text-gray-100 hover:text-accent">${r.title}</a>
          <span class="ml-2 text-xs px-2 py-0.5 rounded-full bg-border text-muted">${r.kind}</span>
          <p class="text-muted text-sm">${r.text.slice(0, 120)}...</p>
        </li>`
      ).join('');
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
    renderResults(window.searchExpansion(query));
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
