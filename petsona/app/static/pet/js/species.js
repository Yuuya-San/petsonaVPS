const btn = document.getElementById("loadMoreBtn");

if (btn) {
  btn.addEventListener("click", async () => {
    const page = btn.dataset.nextPage;

    const res = await fetch(`/species?page=${page}`, {
      headers: { "X-Requested-With": "XMLHttpRequest" }
    });

    const html = await res.text();
    document.getElementById("species-grid")
      .insertAdjacentHTML("beforeend", html);

    btn.dataset.nextPage = parseInt(page) + 1;
    if (!html.trim()) btn.remove();
  });
}
