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
    const faqText = (img.faq || []).map(qa => `${qa.q} ${qa.a}`).join(' ');
    const statsText = img.stats ? Object.values(img.stats).map(s => s.enabled ? (s.value || '-') : '').join(' ') : '';
    const abilities = img.abilities || {};
    const abilityText = [
      abilities.deploy ? 'Deploy' : '',
      abilities.planetaryShield ? 'Planetary Shield' : '',
      abilities.sustainDamage ? 'Sustain Damage' : '',
      abilities.bombardment ? `Bombardment ${abilities.bombardment.value != null ? abilities.bombardment.value : abilities.bombardment.target} ${abilities.bombardment.multi}` : '',
      abilities.antiFighterBarrage ? `Anti-Fighter Barrage ${abilities.antiFighterBarrage.value != null ? abilities.antiFighterBarrage.value : abilities.antiFighterBarrage.target} ${abilities.antiFighterBarrage.multi}` : '',
      abilities.spaceCannon ? `Space Cannon ${abilities.spaceCannon.value != null ? abilities.spaceCannon.value : abilities.spaceCannon.target} ${abilities.spaceCannon.multi}` : '',
      abilities.production ? `Production ${abilities.production.value != null ? abilities.production.value : abilities.production.target} ${abilities.production.multi}` : '',
    ].join(' ');
    const text = `${img.name || ''} ${img.folder || ''} ${img.group || ''} ${img.type || ''} ${img.faction || ''} ${img.description || ''} ${faqText} ${statsText} ${abilityText}`;
    const url = `${img.section || 'cards'}.html`;
    addDoc(`image-${i}`, text, img.name || img.id, url, 'card');
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
