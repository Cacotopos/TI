// Common UI interactions for expansion sites.
(function() {
  const searchInput = document.getElementById('search-input');
  const searchResults = document.getElementById('search-results');
  const resultsList = document.getElementById('search-results-list');

  if (searchInput) {
    searchInput.addEventListener('input', function() {
      const query = this.value.trim();
      if (!query || typeof window.searchExpansion !== 'function') {
        if (searchResults) searchResults.classList.add('hidden');
        return;
      }
      const results = window.searchExpansion(query);
      if (resultsList) {
        resultsList.innerHTML = results.map(r =>
          `<li class="border-b border-border py-2 last:border-0"><strong class="text-gray-100">${r.title}</strong><p class="text-muted text-sm">${r.text.slice(0, 120)}...</p></li>`
        ).join('');
      }
      if (searchResults) {
        searchResults.classList.remove('hidden');
      }
    });
  }

  console.log('ui.js loaded');
})();
