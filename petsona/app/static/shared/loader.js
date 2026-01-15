// Global Loader Management
const LoaderManager = {
    overlay: null,
    timeout: null,
    maxWaitTime: 5000, // 5 second max timeout
    isLoading: false,
    
    init() {
        this.overlay = document.getElementById('loader-overlay');
        if (!this.overlay) return;
        
        // Show loader on various events
        this.attachEventListeners();
    },
    
    hasExistingLoader() {
        // Check for common loading indicators on the page (but exclude the global loader)
        const selectors = [
            '[class*="loader"]',
            '[class*="loading"]',
            '[class*="spinner"]',
            '[class*="progress"]',
            '[id*="loader"]',
            '[id*="loading"]',
            '[data-loading="true"]',
            '.spin',
            '.spinning',
            '.preloader',
            '.load'
        ];
        
        for (const selector of selectors) {
            const element = document.querySelector(selector);
            // Skip the global loader overlay itself
            if (element && element.id !== 'loader-overlay' && element.offsetParent !== null) {
                return true;
            }
        }
        
        return false;
    },
    
    attachEventListeners() {
        // Form submissions
        document.addEventListener('submit', (e) => {
            const form = e.target;
            
            // Skip modal forms and opt-out forms
            if (form.closest('.modal') || form.dataset.noLoader === 'true') return;
            
            this.show();
        });
        
        // ALL BUTTON CLICKS - Show loader for submit buttons (modals, CRUD, forms)
        document.addEventListener('click', (e) => {
            const button = e.target.closest('button');
            if (!button) return;
            
            // Skip disabled buttons and opt-out buttons
            if (button.disabled || button.dataset.noLoader === 'true') return;
            
            // Skip if button is inside a hash link or has specific classes to exclude
            if (button.classList.contains('no-loader')) return;
            
            // Show loader for:
            // 1. Submit buttons (type="submit")
            // 2. Buttons with submit class (btn-submit, submit-btn, etc.)
            // 3. Buttons inside forms
            // 4. Buttons with data-action="submit/save/delete/create/update"
            const isSubmitButton = button.type === 'submit';
            const hasSubmitClass = button.classList.contains('btn-submit') || 
                                   button.classList.contains('submit-btn') ||
                                   button.classList.contains('save-btn') ||
                                   button.classList.contains('create-btn') ||
                                   button.classList.contains('delete-btn') ||
                                   button.classList.contains('update-btn');
            const isInForm = !!button.closest('form');
            const hasSubmitAction = button.dataset.action === 'submit' || 
                                   button.dataset.action === 'save' ||
                                   button.dataset.action === 'create' ||
                                   button.dataset.action === 'update' ||
                                   button.dataset.action === 'delete';
            
            if (isSubmitButton || hasSubmitClass || (isInForm && !button.classList.contains('cancel')) || hasSubmitAction) {
                // Show loader (respects page's own loader if it exists)
                if (!this.hasExistingLoader()) {
                    this.show();
                }
            }
        });
        
        // Tab switching (if using tab libraries)
        document.addEventListener('tabChange', () => {
            this.show();
        });
        document.addEventListener('tab-change', () => {
            this.show();
        });
        
        // Page visibility change (switching tabs/windows)
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && this.isLoading && !this.hasExistingLoader()) {
                this.show();
            }
        });
        
        // Navigation links that aren't hash-based
        document.addEventListener('click', (e) => {
            const link = e.target.closest('a');
            if (!link) return;
            
            const href = link.getAttribute('href');
            
            // Skip hash links, external links, and special links
            if (!href || href.startsWith('#') || 
                link.target === '_blank' || 
                link.hasAttribute('download') ||
                link.dataset.noLoader === 'true') {
                return;
            }
            
            // Skip if it's a modal trigger or accordion toggle
            if (link.closest('[role="dialog"]') || 
                link.closest('[role="region"]') ||
                link.hasAttribute('data-toggle')) {
                return;
            }
            
            // Skip if page already has a loader
            if (this.hasExistingLoader()) return;
            
            // Show loader for actual navigation
            this.show();
        });
        
        // AJAX/Fetch requests
        this.interceptFetch();
        
        // Hide loader when page finishes loading
        window.addEventListener('load', () => this.hide());
        
        // Failsafe: Hide if stuck for too long
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && this.isLoading && !this.hasExistingLoader()) {
                this.resetTimeout();
            }
        });
    },
    
    interceptFetch() {
        const originalFetch = window.fetch;
        
        window.fetch = function(...args) {
            // Only show loader if no existing loader on page
            if (!LoaderManager.hasExistingLoader()) {
                LoaderManager.show();
            }
            
            return originalFetch.apply(this, args)
                .then(response => {
                    // Keep loader visible briefly for better UX
                    setTimeout(() => LoaderManager.hide(), 300);
                    return response;
                })
                .catch(error => {
                    setTimeout(() => LoaderManager.hide(), 300);
                    throw error;
                });
        };
    },
    
    show() {
        if (!this.overlay) return;
        
        this.isLoading = true;
        this.overlay.classList.add('active');
        this.resetTimeout();
    },
    
    hide() {
        if (!this.overlay) return;
        
        this.isLoading = false;
        this.overlay.classList.remove('active');
        this.clearTimeout();
    },
    
    resetTimeout() {
        this.clearTimeout();
        
        // Auto-hide after max wait time to prevent stuck loader
        this.timeout = setTimeout(() => {
            this.hide();
        }, this.maxWaitTime);
    },
    
    clearTimeout() {
        if (this.timeout) {
            clearTimeout(this.timeout);
            this.timeout = null;
        }
    }
};

// Initialize loader when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => LoaderManager.init());
} else {
    LoaderManager.init();
}

// Expose for manual control if needed
window.showLoader = () => LoaderManager.show();
window.hideLoader = () => LoaderManager.hide();
