/**
 * Static JS search.
 *
 * Builds a simple inverted index from data.json and exposes search(query).
 */
(async function() {
  const site = await fetch('data.json').then(r => r.json());

  const index = new Map();
  const docs = [];

  function addDoc(id, text, title, url, kind) {
    const doc = { id, title, url, kind, text: text.toLowerCase() };
    docs.push(doc);
    const tokens = text.toLowerCase().split(/\W+/).filter(t => t.length > 2);
    tokens.forEach(token => {
      if (!index.has(token)) index.set(token, new Set());
      index.get(token).add(doc);
    });
  }

  addDoc('overview', site.overview || '', 'Overview', 'index.html', 'page');
  addDoc('name', site.name || '', site.name, 'index.html', 'page');
  addDoc('description', site.description || '', 'Description', 'index.html', 'page');

  (site.sections || []).forEach((section, i) => {
    addDoc(`section-${i}`, section.title || '', section.title, `${section.id}.html`, 'section');
  });

  (site.images || []).forEach((img, i) => {
    const card = (site.cards || {})[img.id] || {};
    const cardText = `${card.name || img.name} ${card.description || ''} ${(card.faq || []).map(qa => `${qa.q} ${qa.a}`).join(' ')}`;
    addDoc(`image-${i}`, `${img.name} ${img.folder} ${cardText}`, card.name || img.name, 'cards.html', 'card');
  });

  const searchReady = new Promise(resolve => {
    window.searchExpansion = function(query) {
      const q = query.toLowerCase().trim();
      if (!q) return [];
      const tokens = q.split(/\W+/).filter(t => t.length > 2);
      if (tokens.length === 0) {
        return docs.filter(d => d.text.includes(q));
      }
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
    resolve();
  });

  window.searchReady = searchReady;
  console.log('search.js loaded', docs.length, 'documents');
})();
