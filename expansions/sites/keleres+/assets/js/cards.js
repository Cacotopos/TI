// Card detail modal for expansion cards section.
(function() {
  const modal = document.getElementById('card-modal');
  const title = document.getElementById('card-modal-title');
  const badges = document.getElementById('card-modal-badges');
  const statsContainer = document.getElementById('card-modal-stats');
  const abilitiesContainer = document.getElementById('card-modal-abilities');
  const prereqContainer = document.getElementById('card-modal-prereq');
  const frontImg = document.getElementById('card-modal-front');
  const backImg = document.getElementById('card-modal-back');
  const description = document.getElementById('card-modal-description');
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
      parts.push(`<span class="px-2 py-1 rounded-md bg-blue-600 text-white text-xs font-semibold">${label} ${val} x (${roll.multi || 1})</span>`);
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
    frontImg.src = card.frontPath;
    frontImg.alt = card.name || card.id;

    try { card.stats = JSON.parse(card.stats || '{}'); } catch (e) { card.stats = {}; }
    try { card.abilities = JSON.parse(card.abilities || '{}'); } catch (e) { card.abilities = {}; }
    try { card.prereq = JSON.parse(card.prereq || '{}'); } catch (e) { card.prereq = {}; }

    const badgeList = [
      card.type ? `<span class="px-2 py-1 rounded-md bg-blue-600 text-white text-xs font-semibold">${escapeHtml(card.type)}</span>` : '',
      card.faction ? `<span class="px-2 py-1 rounded-md bg-gray-700 text-gray-100 text-xs">${escapeHtml(card.faction)}</span>` : '',
      card.section ? `<span class="px-2 py-1 rounded-md bg-gray-700 text-gray-100 text-xs">${escapeHtml(card.section)}</span>` : '',
      card.group ? `<span class="px-2 py-1 rounded-md bg-gray-700 text-gray-100 text-xs">${escapeHtml(card.group)}</span>` : '',
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
      backImg.classList.remove('hidden');
    } else {
      backImg.classList.add('hidden');
    }

    modal.classList.remove('hidden');
    modal.classList.add('flex');
  }

  document.querySelectorAll('.card-item').forEach(item => {
    item.addEventListener('click', () => {
      open({
        id: item.dataset.cardId,
        name: item.dataset.cardName,
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
        back: item.dataset.cardBack,
        frontPath: item.dataset.cardFrontPath,
      });
    });
  });

  closeBtn.addEventListener('click', close);
  modal.addEventListener('click', e => {
    if (e.target === modal) close();
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !modal.classList.contains('hidden')) close();
  });

  console.log('cards.js loaded');
})();
