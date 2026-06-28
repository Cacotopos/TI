// Card detail modal for expansion cards section.
(function() {
  const modal = document.getElementById('card-modal');
  const title = document.getElementById('card-modal-title');
  const frontImg = document.getElementById('card-modal-front');
  const backImg = document.getElementById('card-modal-back');
  const description = document.getElementById('card-modal-description');
  const faqContainer = document.getElementById('card-modal-faq');
  const closeBtn = document.getElementById('card-modal-close');

  if (!modal) return;

  function close() {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
  }

  function open(card) {
    title.textContent = card.name || card.id;
    frontImg.src = card.frontPath;
    frontImg.alt = card.name || card.id;

    if (card.description) {
      description.textContent = card.description;
      description.classList.remove('hidden');
    } else {
      description.classList.add('hidden');
    }

    let faq = [];
    try {
      faq = JSON.parse(card.faq || '[]');
    } catch (e) {
      faq = [];
    }
    if (faq.length > 0) {
      faqContainer.innerHTML = faq.map(qa => `
        <div class="bg-bg border border-border rounded-lg p-3">
          <p class="font-semibold text-gray-100">Q: ${qa.q}</p>
          <p class="text-muted mt-1">A: ${qa.a}</p>
        </div>
      `).join('');
      faqContainer.classList.remove('hidden');
    } else {
      faqContainer.classList.add('hidden');
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
