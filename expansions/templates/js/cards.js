// Card detail modal for expansion cards section.
(function() {
  const modal = document.getElementById('card-modal');
  const title = document.getElementById('card-modal-title');
  const statsContainer = document.getElementById('card-modal-stats');
  const abilitiesContainer = document.getElementById('card-modal-abilities');
  const prereqContainer = document.getElementById('card-modal-prereq');
  const sourceContainer = document.getElementById('card-modal-source');
  const actionsContainer = document.getElementById('card-modal-actions');
  const frontImg = document.getElementById('card-modal-front');
  const frontWrapper = document.getElementById('card-modal-front-wrapper');
  const backImg = document.getElementById('card-modal-back');
  const backWrapper = document.getElementById('card-modal-back-wrapper');
  const imagesGrid = document.getElementById('card-modal-images');
  const imagesLabels = document.getElementById('card-modal-images-labels');
  const imagesCards = document.getElementById('card-modal-images-cards');
  const description = document.getElementById('card-modal-description');
  const flavourContainer = document.getElementById('card-modal-flavour');
  const faqDetails = document.getElementById('card-modal-faq');
  const faqContent = document.getElementById('card-modal-faq-content');
  const closeBtn = document.getElementById('card-modal-close');

  if (!modal) return;

  function escapeHtml(text) {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function escapeHtmlText(text) {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
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
    return `<span class="px-2 py-1 rounded-md bg-gray-700 text-gray-100 text-xs whitespace-nowrap">Placement</span> ${parts.join('')}`;
  }
  function formatSynergy(synergy) {
    if (!synergy || !synergy.enabled || !synergy.value) return '';
    const colorMap = { G: ['bg-green-600', 'Green'], Y: ['bg-yellow-500 text-black', 'Yellow'], R: ['bg-red-600', 'Red'], B: ['bg-blue-600', 'Blue'] };
    const parts = synergy.value.split('').map(c => {
      const [cls, name] = colorMap[c] || ['bg-gray-700', c];
      return `<span class="px-2 py-1 rounded-md ${cls} text-xs font-semibold whitespace-nowrap">${name}</span>`;
    });
    return parts.length ? `<span class="px-2 py-1 rounded-md bg-gray-700 text-gray-100 text-xs">Synergy</span> ${parts.join('')}` : '';
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
    if (type === 'Station') {
      parts.push('<span class="px-2 py-1 rounded-md bg-blue-600 text-white text-xs font-semibold whitespace-nowrap">Station</span>');
    } else if (source.trait) {
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

  function normalizePath(path) {
    if (!path) return '';
    return path.startsWith('assets/images/') ? path : `assets/images/${path}`;
  }
  function findCardItemByPath(path) {
    return document.querySelector(`.card-item[data-card-front-path="${CSS.escape(normalizePath(path))}"]`);
  }
  function cardDataFromElement(item) {
    return {
      id: item.dataset.cardId,
      name: item.dataset.cardName,
      subtitle: item.dataset.cardSubtitle || '',
      backTitle: item.dataset.cardBackTitle || '',
      backSubtitle: item.dataset.cardBackSubtitle || '',
      backOrientation: item.dataset.cardBackOrientation || '',
      type: item.dataset.cardType,
      faction: item.dataset.cardFaction,
      section: item.dataset.cardSection,
      group: item.dataset.cardGroup,
      description: item.dataset.cardDescription,
      faq: item.dataset.cardFaq,
      stats: item.dataset.cardStats,
      abilities: item.dataset.cardAbilities,
      prereq: item.dataset.cardPrereq,
      color: item.dataset.cardColor,
      synergy: item.dataset.cardSynergy,
      source: item.dataset.cardSource,
      placement: item.dataset.cardPlacement,
      back: item.dataset.cardBack,
      frontPath: item.dataset.cardFrontPath,
      flavour: item.dataset.cardFlavour,
      orientation: item.dataset.cardOrientation,
      component: item.dataset.cardComponent,
      tileType: item.dataset.cardTileType,
      anomalies: item.dataset.cardAnomalies,
      wormholes: item.dataset.cardWormholes,
    };
  }
  function renderCardActions(card) {
    actionsContainer.innerHTML = '';
    const buttons = [];
    const source = card.source || {};
    const linkedPath = normalizePath(source.linkedAbility || '');
    if (source.enabled && linkedPath) {
      const linked = findCardItemByPath(linkedPath);
      if (linked) {
        const name = linked.dataset.cardName || source.linkedAbility;
        buttons.push(`<button type="button" class="linked-ability-btn px-3 py-1 rounded-md bg-accent text-white text-sm font-medium hover:opacity-90" data-path="${escapeHtml(linkedPath)}">View linked ability: ${escapeHtml(name)}</button>`);
      }
    }
    const parentPath = normalizePath(card.parentPath || '');
    const parent = findCardItemByPath(parentPath);
    if (parent) {
      const name = parent.dataset.cardName || parentPath;
      buttons.push(`<button type="button" class="parent-card-btn px-3 py-1 rounded-md bg-gray-700 text-gray-100 text-sm font-medium hover:bg-gray-600" data-path="${escapeHtml(parentPath)}">Back to parent: ${escapeHtml(name)}</button>`);
    }
    actionsContainer.innerHTML = buttons.join('');
    actionsContainer.classList.toggle('hidden', !buttons.length);
  }

  function renderMarkdown(text) {
    if (!text) return '';
    let html = escapeHtmlText(text)
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
    return `<p>${html}</p>`;
  }

  function close() {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    if (window.location.hash.startsWith('#card:')) {
      history.replaceState(null, '', window.location.pathname + window.location.search);
    }
  }

  function open(card) {
    title.textContent = card.name || card.id;
    const subtitleEl = document.getElementById('card-modal-subtitle');
    if (subtitleEl) {
      subtitleEl.textContent = escapeHtml(card.type || '');
      subtitleEl.classList.toggle('hidden', !card.type);
    }
    const metaEl = document.getElementById('card-modal-meta');
    if (metaEl) {
      let parts;
      if (card.component === 'tile') {
        const anomalyList = (card.anomalies || '').split(',').filter(Boolean);
        const wormholeList = (card.wormholes || '').split(',').filter(Boolean);
        parts = [card.tileType ? card.tileType.replace(/-/g, ' ') : '', anomalyList.join(', '), wormholeList.join(', ')].filter(Boolean);
      } else {
        parts = [card.group, card.faction].filter(Boolean).map(escapeHtml);
      }
      metaEl.textContent = parts.join(' · ');
      metaEl.classList.toggle('hidden', !parts.length);
    }
    // Per-image labels (only shown when both front and back are present)
    const frontLabelTitle = document.getElementById('card-modal-front-label-title');
    const frontLabelSubtitle = document.getElementById('card-modal-front-label-subtitle');
    const backHeading = document.getElementById('card-modal-back-heading');
    const backTitleEl = document.getElementById('card-modal-back-title');
    const backSubtitleEl = document.getElementById('card-modal-back-subtitle');
    const hasBack = !!card.back;
    if (frontLabelTitle) {
      frontLabelTitle.textContent = card.name || card.id;
      if (frontLabelSubtitle) {
        frontLabelSubtitle.textContent = card.subtitle || '';
        frontLabelSubtitle.classList.toggle('hidden', !card.subtitle);
      }
    }
    if (backHeading && backTitleEl) {
      const hasBT = hasBack && !!(card.backTitle || card.backSubtitle);
      backHeading.classList.toggle('hidden', !hasBT);
      backTitleEl.textContent = card.backTitle || '';
      if (backSubtitleEl) {
        backSubtitleEl.textContent = card.backSubtitle || '';
        backSubtitleEl.classList.toggle('hidden', !card.backSubtitle);
      }
    }
    frontImg.src = card.frontPath;
    frontImg.alt = card.name || card.id;
    const orientation = card.orientation === 'portrait' ? 'portrait' : (card.orientation === 'square' ? 'square' : 'landscape');
    frontWrapper.classList.remove('portrait', 'landscape', 'square');
    frontWrapper.classList.add(orientation);
    if (backWrapper) {
      const backOrientation = card.backOrientation === 'portrait' ? 'portrait' : (card.backOrientation === 'square' ? 'square' : (card.backOrientation === 'landscape' ? 'landscape' : orientation));
      backWrapper.classList.remove('portrait', 'landscape', 'square');
      backWrapper.classList.add(backOrientation);
    }

    try { card.stats = JSON.parse(card.stats || '{}'); } catch (e) { card.stats = {}; }
    try { card.abilities = JSON.parse(card.abilities || '{}'); } catch (e) { card.abilities = {}; }
    try { card.prereq = JSON.parse(card.prereq || '{}'); } catch (e) { card.prereq = {}; }
    try { card.synergy = JSON.parse(card.synergy || '{}'); } catch (e) { card.synergy = {}; }
    try { card.source = JSON.parse(card.source || '{}'); } catch (e) { card.source = {}; }
    try { card.placement = JSON.parse(card.placement || '{}'); } catch (e) { card.placement = {}; }

    const statsHtml = isUnitType(card.type) ? formatStats(card.stats) : '';
    statsContainer.innerHTML = statsHtml;
    statsContainer.classList.toggle('hidden', !statsHtml);

    const abilitiesHtml = isUnitType(card.type) ? formatAbilities(card.abilities) : '';
    abilitiesContainer.innerHTML = abilitiesHtml;
    abilitiesContainer.classList.toggle('hidden', !abilitiesHtml);

    const prereqHtml = formatPrereq(card.prereq, card.color);
    prereqContainer.innerHTML = prereqHtml;
    prereqContainer.classList.toggle('hidden', !prereqHtml);

    const synergyContainer = document.getElementById('card-modal-synergy');
    if (synergyContainer) {
      const synergyHtml = formatSynergy(card.synergy);
      synergyContainer.innerHTML = synergyHtml;
      synergyContainer.classList.toggle('hidden', !synergyHtml);
    }

    const placementContainer = document.getElementById('card-modal-placement');
    if (placementContainer) {
      const placementHtml = formatPlacement(card.placement);
      placementContainer.innerHTML = placementHtml;
      placementContainer.classList.toggle('hidden', !placementHtml);
    }

    const sourceHtml = formatSource(card.source, card.type);
    sourceContainer.innerHTML = sourceHtml;
    sourceContainer.classList.toggle('hidden', !sourceHtml);
    renderCardActions(card);

    if (card.flavour) {
      flavourContainer.textContent = card.flavour;
      flavourContainer.classList.remove('hidden');
    } else {
      flavourContainer.textContent = '';
      flavourContainer.classList.add('hidden');
    }

    if (card.description) {
      description.innerHTML = renderMarkdown(card.description);
      description.classList.remove('hidden');
    } else {
      description.innerHTML = '';
      description.classList.add('hidden');
    }

    let faq = [];
    try {
      faq = JSON.parse(card.faq || '[]');
    } catch (e) {
      faq = [];
    }
    if (faq.length > 0) {
      faqContent.innerHTML = faq.map(qa => `
        <div class="bg-bg border border-border rounded-lg p-3">
          <p class="font-semibold text-gray-100">Q: ${escapeHtml(qa.q)}</p>
          <p class="text-muted mt-1">A: ${escapeHtml(qa.a)}</p>
        </div>
      `).join('');
      faqDetails.classList.remove('hidden');
    } else {
      faqContent.innerHTML = '';
      faqDetails.classList.add('hidden');
    }

    if (card.back) {
      backImg.src = 'assets/images/' + card.back;
      backImg.alt = (card.name || card.id) + ' back';
      backWrapper.classList.remove('hidden');
      imagesLabels.classList.add('has-back');
      imagesCards.classList.add('has-back');
    } else {
      backImg.src = '';
      backImg.alt = '';
      backWrapper.classList.add('hidden');
      imagesLabels.classList.remove('has-back');
      imagesCards.classList.remove('has-back');
    }

    modal.classList.remove('hidden');
    modal.classList.add('flex');
  }

  const parentByPath = {};
  document.querySelectorAll('.card-item').forEach(item => {
    try {
      const source = JSON.parse(item.dataset.cardSource || '{}');
      if (source.enabled && source.linkedAbility) {
        parentByPath[normalizePath(source.linkedAbility)] = item.dataset.cardFrontPath;
      }
    } catch (e) {}
  });

  document.querySelectorAll('.card-item').forEach(item => {
    item.addEventListener('click', () => {
      const card = cardDataFromElement(item);
      card.parentPath = parentByPath[item.dataset.cardFrontPath] || '';
      open(card);
    });
  });

  closeBtn.addEventListener('click', close);
  modal.addEventListener('click', e => {
    if (e.target === modal) close();
  });
  actionsContainer.addEventListener('click', e => {
    const btn = e.target.closest('.linked-ability-btn, .parent-card-btn');
    if (!btn) return;
    const targetPath = normalizePath(btn.dataset.path);
    const target = findCardItemByPath(targetPath);
    if (!target) return;
    const targetCard = cardDataFromElement(target);
    targetCard.parentPath = parentByPath[targetPath] || '';
    open(targetCard);
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !modal.classList.contains('hidden')) close();
  });

  function openFromHash() {
    const hash = decodeURIComponent(window.location.hash);
    if (!hash.startsWith('#card:')) return;
    const id = hash.slice(6);
    const item = document.querySelector(`.card-item[data-card-id="${CSS.escape(id)}"]`);
    if (!item) return;
    item.scrollIntoView({ behavior: 'smooth', block: 'center' });
    const card = cardDataFromElement(item);
    card.parentPath = parentByPath[item.dataset.cardFrontPath] || '';
    open(card);
  }

  window.addEventListener('hashchange', openFromHash);
  openFromHash();

  console.log('cards.js loaded');
})();
