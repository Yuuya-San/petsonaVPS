// Global Loader Management - Request Queue Based System
window.LoaderManager = window.LoaderManager || {
    overlay: null,
    activeRequests: 0, // Track number of ongoing requests
    globalTimeout: null,
    maxGlobalWaitTime: 120000, // 2 minute absolute max (fallback only)
    isLoading: false,
    debounceTimer: null,
    debounceDelay: 300, // Delay before actually hiding
    ignoredRequestPatterns: [
        /google\.com\/recaptcha/, 
        /gstatic\.com\//,
        /recaptcha\/api\.js/,
    ],

    shouldTrackRequest(url) {
        if (!url || typeof url !== 'string') return true;
        return !this.ignoredRequestPatterns.some(pattern => pattern.test(url));
    },

    init() {
        this.overlay = document.getElementById('loader-overlay');
        if (!this.overlay) return;
        
        // Show loader on various events
        this.attachEventListeners();
        this.interceptFetch();
        this.interceptXHR();
    },
    
    hasExistingLoader(ignoreElement = null) {
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
            const elements = document.querySelectorAll(selector);

            for (const element of elements) {
                if (!element || element.id === 'loader-overlay') continue;
                if (element.offsetParent === null) continue;
                if (ignoreElement && ignoreElement.contains(element)) continue;
                if (this.isButtonSpinnerElement(element)) continue;

                return true;
            }
        }

        return false;
    },

    isButtonSpinnerElement(element) {
        if (!element) return false;

        if (element.matches('.btn-spinner, .spinner-border, .spinner-spin, .fa-spinner, .fa-spin, [data-loading="true"]')) {
            return true;
        }

        return !!element.closest('button.is-loading, .btn.is-loading, button.loading, .btn.loading, [data-loading="true"]');
    },

    hasActiveLoadingIndicator() {
        const selectors = [
            '.btn-spinner',
            '.spinner',
            '.spinner-border',
            '.spinner-spin',
            '.loading-spinner',
            '.fa-spinner',
            '.fa-spin',
            'button.is-loading',
            '.btn.is-loading',
            'button.loading',
            '.btn.loading',
            '[data-loading="true"]'
        ];

        const elements = document.querySelectorAll(selectors.join(','));
        return Array.from(elements).some(element => {
            if (!element || element.id === 'loader-overlay') return false;
            return element.offsetParent !== null;
        });
    },
    
    attachEventListeners() {
        // Form submissions
        document.addEventListener('submit', (e) => {
            const form = e.target;
            
            // Skip modal forms and opt-out forms
            if (form.closest('.modal') || form.dataset.noLoader === 'true') return;
            
            this.incrementRequest('form-submit');
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
                if (!this.hasExistingLoader(button)) {
                    this.incrementRequest('button-click');
                    this.show();
                }
            }
        });
        
        // Tab switching (if using tab libraries)
        document.addEventListener('tabChange', () => {
            this.incrementRequest('tab-change');
            this.show();
        });
        document.addEventListener('tab-change', () => {
            this.incrementRequest('tab-change');
            this.show();
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
            
            // Skip if page already has a loader (ignore link-local spinners)
            if (this.hasExistingLoader(link)) return;
            
            // Show loader for actual navigation
            this.incrementRequest('navigation');
            this.show();
        });
    },
    
    interceptFetch() {
        const originalFetch = window.fetch;
        const self = this;
        
        window.fetch = function(...args) {
            const requestUrl = args[0] instanceof Request ? args[0].url : String(args[0] || '');
            if (self.shouldTrackRequest(requestUrl) && !self.hasExistingLoader()) {
                self.incrementRequest('fetch');
                self.show();
            }
            
            return originalFetch.apply(this, args)
                .then(response => {
                    if (self.shouldTrackRequest(requestUrl)) {
                        self.decrementRequest('fetch');
                    }
                    return response;
                })
                .catch(error => {
                    if (self.shouldTrackRequest(requestUrl)) {
                        self.decrementRequest('fetch');
                    }
                    throw error;
                });
        };
    },
    
    interceptXHR() {
        const originalOpen = XMLHttpRequest.prototype.open;
        const originalSend = XMLHttpRequest.prototype.send;
        const self = this;
        
        XMLHttpRequest.prototype.open = function(method, url, ...rest) {
            this._loaderTracked = self.shouldTrackRequest(String(url || ''));
            return originalOpen.apply(this, [method, url, ...rest]);
        };
        
        XMLHttpRequest.prototype.send = function(...args) {
            if (this._loaderTracked && !self.hasExistingLoader()) {
                self.incrementRequest('xhr');
                self.show();
            }
            
            const self_ref = self;
            const onStateChange = () => {
                if (this.readyState === XMLHttpRequest.DONE && this._loaderTracked) {
                    self_ref.decrementRequest('xhr');
                }
            };
            
            this.addEventListener('readystatechange', onStateChange);
            return originalSend.apply(this, args);
        };
    },
    
    incrementRequest(source) {
        this.activeRequests++;
        this.clearGlobalTimeout();
        this.resetGlobalTimeout();
    },
    
    decrementRequest(source) {
        if (this.activeRequests > 0) {
            this.activeRequests--;
        }
        
        // Only hide if no more active requests
        if (this.activeRequests <= 0) {
            this.activeRequests = 0; // Reset to 0 to prevent negative
            this.scheduleHide();
        }
    },
    
    scheduleHide() {
        // Debounce the hide to prevent flickering from rapid requests
        clearTimeout(this.debounceTimer);
        this.debounceTimer = setTimeout(() => {
            if (this.activeRequests <= 0) {
                if (this.hasActiveLoadingIndicator()) {
                    this.scheduleHide();
                } else {
                    this.hide();
                }
            }
        }, this.debounceDelay);
    },
    
    show() {
        if (!this.overlay) return;
        
        this.isLoading = true;
        this.overlay.classList.add('active');
        
        // Clear any pending hide
        clearTimeout(this.debounceTimer);
    },
    
    hide() {
        if (!this.overlay || this.activeRequests > 0 || this.hasActiveLoadingIndicator()) {
            // Don't hide if there are still active requests or button-level loading indicators are visible
            return;
        }
        
        this.isLoading = false;
        this.overlay.classList.remove('active');
        this.activeRequests = 0;
        this.clearGlobalTimeout();
    },
    
    resetGlobalTimeout() {
        this.clearGlobalTimeout();
        
        // Absolute maximum timeout (fallback only, should rarely trigger)
        // This prevents completely stuck loaders but respects actual requests
        this.globalTimeout = setTimeout(() => {
            this.activeRequests = 0;
            this.hide();
        }, this.maxGlobalWaitTime);
    },
    
    clearGlobalTimeout() {
        if (this.globalTimeout) {
            clearTimeout(this.globalTimeout);
            this.globalTimeout = null;
        }
    }
};

// Initialize loader when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => window.LoaderManager.init());
} else {
    window.LoaderManager.init();
}

// Expose for manual control if needed
window.showLoader = () => {
    LoaderManager.incrementRequest('manual');
    LoaderManager.show();
};

window.hideLoader = () => {
    LoaderManager.decrementRequest('manual');
    LoaderManager.hide();
};

// For cases where you need to manually manage loader
window.getLoaderStatus = () => ({
    isLoading: LoaderManager.isLoading,
    activeRequests: LoaderManager.activeRequests
});
