/**
 * Cognicare Theme Manager (Vanilla JS)
 * Handles Dark Mode and Light Mode switching with localStorage persistence,
 * system preference detection, accessible button states, and zero dependencies.
 */
(function () {
    'use strict';

    var STORAGE_KEY = 'cognicare-theme';
    var THEME_DARK = 'dark';
    var THEME_LIGHT = 'light';

    function getSavedTheme() {
        try {
            return localStorage.getItem(STORAGE_KEY);
        } catch (e) {
            return null;
        }
    }

    function getSystemTheme() {
        try {
            if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
                return THEME_DARK;
            }
        } catch (e) {}
        return THEME_LIGHT;
    }

    function getCurrentTheme() {
        return document.documentElement.getAttribute('data-theme') || getSavedTheme() || getSystemTheme();
    }

    function updateToggleUI(theme) {
        var btn = document.getElementById('theme-toggle');
        if (!btn) return;

        var isDark = (theme === THEME_DARK);
        btn.setAttribute('aria-pressed', isDark ? 'true' : 'false');

        var lightLabel = btn.getAttribute('data-label-light') || 'Switch to Light Mode';
        var darkLabel = btn.getAttribute('data-label-dark') || 'Switch to Dark Mode';
        btn.setAttribute('aria-label', isDark ? lightLabel : darkLabel);

        var iconSpan = btn.querySelector('.theme-toggle-icon');
        var textSpan = btn.querySelector('.theme-toggle-text');

        if (iconSpan) {
            iconSpan.textContent = isDark ? '☀️' : '🌙';
        }
        if (textSpan) {
            var lightText = btn.getAttribute('data-text-light') || 'Light';
            var darkText = btn.getAttribute('data-text-dark') || 'Dark';
            textSpan.textContent = isDark ? lightText : darkText;
        }
    }

    function applyTheme(theme, savePreference) {
        if (theme !== THEME_DARK && theme !== THEME_LIGHT) {
            theme = THEME_LIGHT;
        }

        document.documentElement.setAttribute('data-theme', theme);

        if (savePreference) {
            try {
                localStorage.setItem(STORAGE_KEY, theme);
            } catch (e) {}
        }

        updateToggleUI(theme);
    }

    function toggleTheme() {
        var current = getCurrentTheme();
        var next = (current === THEME_DARK) ? THEME_LIGHT : THEME_DARK;
        applyTheme(next, true);
    }

    function init() {
        var active = getCurrentTheme();
        updateToggleUI(active);

        var btn = document.getElementById('theme-toggle');
        if (btn) {
            btn.addEventListener('click', toggleTheme);
        }

        // Listen to system preference changes only if user hasn't explicitly set a preference
        if (window.matchMedia) {
            try {
                var mql = window.matchMedia('(prefers-color-scheme: dark)');
                var handler = function (e) {
                    if (!getSavedTheme()) {
                        applyTheme(e.matches ? THEME_DARK : THEME_LIGHT, false);
                    }
                };
                if (mql.addEventListener) {
                    mql.addEventListener('change', handler);
                } else if (mql.addListener) {
                    mql.addListener(handler);
                }
            } catch (e) {}
        }
    }

    // Expose CognicareTheme object for testability
    window.CognicareTheme = {
        getTheme: getCurrentTheme,
        setTheme: function (theme) {
            applyTheme(theme, true);
        },
        toggle: toggleTheme
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
