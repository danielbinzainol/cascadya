const staggeredCards = document.querySelectorAll("[data-stagger]");
staggeredCards.forEach((card, index) => {
  card.style.setProperty("--stagger-index", String(index));
});
