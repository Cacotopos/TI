/**
 * Static JS search.
 *
 * Builds a simple inverted index from data.json and exposes search(query).
 */
(async function() {
  const config = await fetch('data.json').then(r => r.json());

  const index = new Map();
  const docs = [];

  function addDoc(id, text, title) {
    const doc = { id, title, text: text.toLowerCase() };
    docs.push(doc);
    const tokens = text.toLowerCase().split(/\W+/).filter(t => t.length > 2);
    tokens.forEach(token => {
      if (!index.has(token)) index.set(token, new Set());
      index.get(token).add(doc);
    });
  }

  addDoc('overview', config.overview || '', 'Overview');
  addDoc('name', config.name || '', config.name);
  addDoc('description', config.description || '', 'Description');
  (config.sections || []).forEach((section, i) => {
    addDoc(`section-${i}`, section.title || '', section.title);
  });

  window.searchExpansion = function(query) {
    const q = query.toLowerCase().trim();
    if (!q) return docs;
    const tokens = q.split(/\W+/).filter(t => t.length > 2);
    if (tokens.length === 0) return docs.filter(d => d.text.includes(q));
    const scores = new Map();
    tokens.forEach(token => {
      const matches = index.get(token) || new Set();
      matches.forEach(doc => {
        scores.set(doc, (scores.get(doc) || 0) + 1);
      });
    });
    return Array.from(scores.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([doc]) => doc);
  };

  console.log('search.js loaded', docs.length, 'documents');
})();
