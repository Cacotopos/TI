// Card detail modal for expansion cards section.
(function() {
  const modal = document.getElementById('card-modal');
  const title = document.getElementById('card-modal-title');
  const badges = document.getElementById('card-modal-badges');
  const statsContainer = document.getElementById('card-modal-stats');
  const abilitiesContainer = document.getElementById('card-modal-abilities');
  const prereqContainer = document.getElementById('card-modal-prereq');
  const sourceContainer = document.getElementById('card-modal-source');
  const actionsContainer = document.getElementById('card-modal-actions');
  const frontImg = document.getElementById('card-modal-front');
  const frontWrapper = document.getElementById('card-modal-front-wrapper');
  const backImg = document.getElementById('card-modal-back');
  const backWrapper = document.getElementById('card-modal-back-wrapper');
  const backImgWrapper = document.getElementById('card-modal-back-img-wrapper');
  const imagesGrid = document.getElementById('card-modal-images');
  const description = document.getElementById('card-modal-description');
  const flavourContainer = document.getElementById('card-modal-flavour');
  const faqDetails = document.getElementById('card-modal-faq');
  const faqContent = document.getElementById('card-modal-faq-content');
  const closeBtn = document.getElementById('card-modal-close');

  if (!modal) return;

  function escapeHtml(text) {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function isUnitType(type) { return type && type.startsWith('Unit -'); }
  function formatStats(stats) {
    const labels = { cost: 'Cost', combat: 'Combat', move: 'Move', capacity: 'Capacity' };
    const parts = [];
    ['cost', 'combat', 'move', 'capacity'].forEach(key => {
      const stat = stats?.[key];
      if (!stat || !stat.enabled) return;
      parts.push(`<span class="px-2 py-1 rounded-md bg-gray-700 text-gray-100 text-xs whitespace-nowrap">${labels[key]} ${stat.value == null ? '-' : escapeHtml(String(stat.value))}</span>`);
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
      parts.push(`<span class="px-2 py-1 rounded-md bg-blue-600 text-white text-xs font-semibold">${label} ${val} (x${roll.multi || 1})</span>`);
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
      parts.push(`<span class="px-2 py-1 rounded-md bg-cyan-500 text-black text-xs font-semibold whitespace-nowrap">Influence ${escapeHtml(String(source.influence))}</span>`);
    }
    if (source.resource !== undefined && source.resource !== null && source.resource !== '') {
      parts.push(`<span class="px-2 py-1 rounded-md bg-yellow-400 text-black text-xs font-semibold whitespace-nowrap">Resource ${escapeHtml(String(source.resource))}</span>`);
    }
    if (type === 'Station') {
      parts.push('<span class="px-2 py-1 rounded-md bg-blue-600 text-white text-xs font-semibold whitespace-nowrap">Station</span>');
    } else if (source.trait) {
      const traits = Array.isArray(source.trait) ? source.trait : (source.trait ? [source.trait] : []);
      const traitColors = { hazardous: 'bg-red-600', cultural: 'bg-green-600', industrial: 'bg-yellow-500 text-black' };
      traits.forEach(trait => {
        const color = traitColors[trait] || 'bg-gray-700';
        parts.push(`<span class="px-2 py-1 rounded-md ${color} text-xs font-semibold whitespace-nowrap capitalize">${escapeHtml(trait)}</span>`);
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
      back: item.dataset.cardBack,
      frontPath: item.dataset.cardFrontPath,
      flavour: item.dataset.cardFlavour,
      orientation: item.dataset.cardOrientation,
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
    let html = escapeHtml(text)
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
  }

  function open(card) {
    title.textContent = card.name || card.id;
    const subtitleEl = document.getElementById('card-modal-subtitle');
    if (subtitleEl) {
      subtitleEl.textContent = card.subtitle || '';
      subtitleEl.classList.toggle('hidden', !card.subtitle);
    }
    // Per-image labels (only shown when both front and back are present)
    const frontLabel = document.getElementById('card-modal-front-label');
    const frontLabelTitle = document.getElementById('card-modal-front-label-title');
    const frontLabelSubtitle = document.getElementById('card-modal-front-label-subtitle');
    const backHeading = document.getElementById('card-modal-back-heading');
    const backTitleEl = document.getElementById('card-modal-back-title');
    const backSubtitleEl = document.getElementById('card-modal-back-subtitle');
    const hasBack = !!card.back;
    if (frontLabel && frontLabelTitle) {
      frontLabel.classList.toggle('hidden', !hasBack);
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
    const orientation = card.orientation === 'portrait' ? 'portrait' : 'landscape';
    frontWrapper.classList.remove('portrait', 'landscape');
    frontWrapper.classList.add(orientation);
    if (backImgWrapper) {
      backImgWrapper.classList.remove('portrait', 'landscape');
      backImgWrapper.classList.add(orientation);
    }

    try { card.stats = JSON.parse(card.stats || '{}'); } catch (e) { card.stats = {}; }
    try { card.abilities = JSON.parse(card.abilities || '{}'); } catch (e) { card.abilities = {}; }
    try { card.prereq = JSON.parse(card.prereq || '{}'); } catch (e) { card.prereq = {}; }
    try { card.synergy = JSON.parse(card.synergy || '{}'); } catch (e) { card.synergy = {}; }
    try { card.source = JSON.parse(card.source || '{}'); } catch (e) { card.source = {}; }

    const badgeList = [
      card.type ? `<span class="px-2 py-1 rounded-md bg-blue-600 text-white text-xs font-semibold">${escapeHtml(card.type)}</span>` : '',
      card.faction ? `<span class="px-2 py-1 rounded-md bg-gray-700 text-gray-100 text-xs">${escapeHtml(card.faction)}</span>` : '',
    ].filter(Boolean).join('');
    badges.innerHTML = badgeList;

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
      imagesGrid.classList.add('has-back');
    } else {
      backImg.src = '';
      backImg.alt = '';
      backWrapper.classList.add('hidden');
      imagesGrid.classList.remove('has-back');
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

  console.log('cards.js loaded');
})();
