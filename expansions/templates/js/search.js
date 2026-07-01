/**
 * Static JS search.
 *
 * Uses window.SITE_DATA (inlined by the generator into search-data.js) so
 * search works with file:// as well as HTTP — no fetch required.
 */
(function() {
  const site = window.SITE_DATA || {};

  const index = new Map();
  const docs = [];

  function addDoc(id, text, title, url, kind, snippet, fields) {
    const doc = { id, title, url, kind, text: (snippet || text).slice(0, 200), fields: fields || {} };
    docs.push(doc);
    const tokens = text.toLowerCase().split(/\W+/).filter(t => t.length > 1);
    tokens.forEach(token => {
      if (!index.has(token)) index.set(token, new Set());
      index.get(token).add(doc);
    });
  }

  addDoc('overview', site.overview || '', 'Overview', 'index.html', 'page', site.overview);
  addDoc('name', site.name || '', site.name, 'index.html', 'page', site.name);
  addDoc('description', site.description || '', 'Description', 'index.html', 'page', site.description);

  (site.sections || []).forEach((section, i) => {
    addDoc(`section-${i}`, section.title || '', section.title, `${section.id}.html`, 'section', section.title);
  });

  (site.images || []).forEach((img, i) => {
    const faqText = (img.faq || []).map(qa => `${qa.q} ${qa.a}`).join(' ');
    const statsText = img.stats ? Object.values(img.stats).map(s => s.enabled ? (s.value || '-') : '').join(' ') : '';
    const abilities = img.abilities || {};
    const abilityText = [
      abilities.deploy ? 'Deploy' : '',
      abilities.planetaryShield ? 'Planetary Shield' : '',
      abilities.sustainDamage ? 'Sustain Damage' : '',
      abilities.bombardment ? `Bombardment ${abilities.bombardment.value != null ? abilities.bombardment.value : abilities.bombardment.target} (x${abilities.bombardment.multi || 1})` : '',
      abilities.antiFighterBarrage ? `Anti-Fighter Barrage ${abilities.antiFighterBarrage.value != null ? abilities.antiFighterBarrage.value : abilities.antiFighterBarrage.target} (x${abilities.antiFighterBarrage.multi || 1})` : '',
      abilities.spaceCannon ? `Space Cannon ${abilities.spaceCannon.value != null ? abilities.spaceCannon.value : abilities.spaceCannon.target} (x${abilities.spaceCannon.multi || 1})` : '',
      abilities.production ? `Production ${abilities.production.value != null ? abilities.production.value : abilities.production.target} (x${abilities.production.multi || 1})` : '',
    ].join(' ');
    const prereqText = img.prereq && img.prereq.enabled ? img.prereq.value : '';
    const colorText = img.color || '';
    const source = img.source || {};
    const sourceText = source.enabled ? `${source.influence || ''} ${source.resource || ''} ${(source.trait || []).join(' ')} ${source.legendary ? 'Legendary' : ''} ${source.relic ? 'Relic' : ''} ${source.techSpeciality || ''} ${source.linkedAbility || ''}` : '';
    const synergy = img.synergy || {};
    const synergyText = synergy.enabled ? (synergy.value || '') : '';
    const placementText = (img.placement && img.placement.enabled) ? (img.placement.rules || []).map(r => (r.not ? 'not ' : '') + r.value).join(' ') : '';
    const fields = {
      subtitle: img.subtitle || '',
      type: img.type || '',
      faction: img.faction || '',
      group: img.group || '',
      folder: img.folder || '',
      description: img.description || '',
      flavour: img.flavour || '',
      stats: img.stats || {},
      abilities: img.abilities || {},
      prereq: img.prereq || {},
      color: img.color || '',
      source: img.source || {},
      synergy: img.synergy || {},
      placement: img.placement || {},
      faq: img.faq || [],
    };
    const searchText = `${img.name || ''} ${img.subtitle || ''} ${img.folder || ''} ${img.group || ''} ${img.type || ''} ${img.faction || ''} ${img.description || ''} ${img.flavour || ''} ${faqText} ${statsText} ${abilityText} ${prereqText} ${colorText} ${sourceText} ${synergyText} ${placementText}`;
    const snippet = [img.subtitle, img.type, img.faction, img.group].filter(Boolean).join(' · ');
    const url = `${img.section || 'cards'}.html`;
    addDoc(`image-${i}`, searchText, img.name || img.id, url, 'card', snippet, fields);
  });

  window.searchExpansion = function(query) {
    const q = query.toLowerCase().trim();
    if (!q) return [];
    const tokens = q.split(/\W+/).filter(t => t.length > 1);
    if (tokens.length === 0) {
      return docs.filter(d => d.text.toLowerCase().includes(q));
    }
    const scores = new Map();
    tokens.forEach(token => {
      (index.get(token) || new Set()).forEach(doc => {
        scores.set(doc, (scores.get(doc) || 0) + 1);
      });
      // partial prefix match
      index.forEach((docSet, key) => {
        if (key.startsWith(token) && key !== token) {
          docSet.forEach(doc => scores.set(doc, (scores.get(doc) || 0) + 0.5));
        }
      });
    });
    return Array.from(scores.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([doc]) => doc);
  };
  window.searchReady = Promise.resolve();
  console.log('search.js loaded', docs.length, 'documents');
})();
