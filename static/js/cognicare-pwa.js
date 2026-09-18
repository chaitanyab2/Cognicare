/**
 * Cognicare Progressive Web App (PWA) Manager
 * - Handles Service Worker registration (/sw.js at root scope)
 * - Handles native beforeinstallprompt with dignified, accessible install banner
 * - Persists user banner dismissal preference to avoid annoyance
 * - Synchronizes <meta name="theme-color"> with active data-theme
 */

(function () {
  'use strict';

  var DISMISS_KEY = 'cognicare-pwa-dismissed';
  var DISMISS_DAYS = 7;
  var deferredPrompt = null;

  // 1. Service Worker Registration
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js', { scope: '/' })
        .then(function (registration) {
          // SW registered successfully
        })
        .catch(function (error) {
          console.warn('Service Worker registration note:', error);
        });
    });
  }

  // 2. Synchronize <meta name="theme-color"> with active data-theme
  function syncThemeColor() {
    var theme = document.documentElement.getAttribute('data-theme') || 'light';
    var metaTheme = document.querySelector('meta[name="theme-color"]');
    if (metaTheme) {
      // #0f766e for light mode, #0b1320 for dark mode
      metaTheme.setAttribute('content', theme === 'dark' ? '#0b1320' : '#0f766e');
    }
  }

  syncThemeColor();

  if (window.MutationObserver) {
    var themeObserver = new MutationObserver(function (mutations) {
      mutations.forEach(function (mutation) {
        if (mutation.attributeName === 'data-theme') {
          syncThemeColor();
        }
      });
    });
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme']
    });
  }

  // 3. Install Prompt Handling
  function isDismissed() {
    try {
      var val = localStorage.getItem(DISMISS_KEY);
      if (!val) return false;
      var timestamp = parseInt(val, 10);
      if (isNaN(timestamp)) return false;
      return (Date.now() - timestamp) < (DISMISS_DAYS * 24 * 60 * 60 * 1000);
    } catch (e) {
      return false;
    }
  }

  function showInstallBanner() {
    var banner = document.getElementById('pwa-install-banner');
    if (!banner || isDismissed()) return;

    banner.removeAttribute('hidden');
    banner.classList.add('pwa-banner--visible');
    banner.setAttribute('aria-hidden', 'false');
  }

  function hideInstallBanner() {
    var banner = document.getElementById('pwa-install-banner');
    if (!banner) return;

    banner.classList.remove('pwa-banner--visible');
    banner.setAttribute('hidden', '');
    banner.setAttribute('aria-hidden', 'true');
  }

  window.addEventListener('beforeinstallprompt', function (e) {
    // Prevent standard mini-infobar
    e.preventDefault();
    deferredPrompt = e;
    showInstallBanner();
  });

  window.addEventListener('appinstalled', function () {
    hideInstallBanner();
    deferredPrompt = null;
  });

  // Attach event listeners once DOM is ready
  function initInstallBanner() {
    var installBtn = document.getElementById('pwa-install-btn');
    var dismissBtn = document.getElementById('pwa-dismiss-btn');

    if (installBtn) {
      installBtn.addEventListener('click', function () {
        if (deferredPrompt) {
          deferredPrompt.prompt();
          deferredPrompt.userChoice.then(function (choiceResult) {
            if (choiceResult.outcome === 'accepted') {
              try {
                localStorage.removeItem(DISMISS_KEY);
              } catch (e) {}
            }
            deferredPrompt = null;
            hideInstallBanner();
          });
        }
      });
    }

    if (dismissBtn) {
      dismissBtn.addEventListener('click', function () {
        try {
          localStorage.setItem(DISMISS_KEY, Date.now().toString());
        } catch (e) {}
        hideInstallBanner();
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initInstallBanner);
  } else {
    initInstallBanner();
  }

  // Expose API for testing/debugging
  window.CognicarePWA = {
    syncThemeColor: syncThemeColor,
    showInstallBanner: showInstallBanner,
    hideInstallBanner: hideInstallBanner,
    isDismissed: isDismissed
  };
})();
