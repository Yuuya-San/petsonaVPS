document.addEventListener('DOMContentLoaded', () => {
    const loader = document.getElementById('loader-overlay');
    if (!loader) return;

    function showLoader() {
        loader.classList.add('active');
    }

    function hideLoader() {
        loader.classList.remove('active');
    }

    // Always hide loader when page finishes loading
    window.addEventListener('load', hideLoader);

    // Show loader ONLY on real form submit (not modals)
    document.addEventListener('submit', (e) => {
        const form = e.target;

        // Skip modal forms
        if (form.closest('.modal')) return;

        // Skip opt-out forms
        if (form.dataset.noLoader === 'true') return;

        showLoader();
    });
});
