// Card detail modal for expansion cards section.
(function() {
  const modal = document.getElementById('card-modal');
  const title = document.getElementById('card-modal-title');
  const badges = document.getElementById('card-modal-badges');
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

    const badgeList = [
      card.type ? `<span class="px-2 py-1 rounded-md bg-blue-600 text-white text-xs font-semibold">${escapeHtml(card.type)}</span>` : '',
      card.faction ? `<span class="px-2 py-1 rounded-md bg-gray-700 text-gray-100 text-xs">${escapeHtml(card.faction)}</span>` : '',
      card.section ? `<span class="px-2 py-1 rounded-md bg-gray-700 text-gray-100 text-xs">${escapeHtml(card.section)}</span>` : '',
      card.group ? `<span class="px-2 py-1 rounded-md bg-gray-700 text-gray-100 text-xs">${escapeHtml(card.group)}</span>` : '',
    ].filter(Boolean).join('');
    badges.innerHTML = badgeList;

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
