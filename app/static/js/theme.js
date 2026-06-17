/*
  theme.js — applied sync before CSS to prevent flash.
  Themes: 'system' | 'light' | 'dark' | 'ocean' | 'forest' | 'midnight'

  Arch:
  - light/dark use Bootstrap's data-bs-theme attribute only
  - ocean/forest/midnight use data-bs-theme="dark" + data-theme="<name>"
  - system follows OS preference and resolves to light or dark
  - DB is the source of truth (server injects data-user-theme)
  - localStorage mirrors DB for instant no-flash behaviour
*/

var _DARK_THEMES    = ['dark', 'forest', 'midnight', 'slate', 'christmas'];
var _CUSTOM_THEMES  = ['ocean', 'forest', 'midnight', 'slate', 'christmas'];
var _BODY_COLORS    = {
    light:     '#F5F1EC',
    dark:      '#0E0C10',
    ocean:     '#E8F4FD',
    forest:    '#020704',
    midnight:  '#030108',
    slate:     '#0C1422',
    christmas: '#0B1610',
};

// Extend with server-injected custom themes (window.__CUSTOM_THEMES__ set in base.html)
if (window.__CUSTOM_THEMES__) {
    window.__CUSTOM_THEMES__.forEach(function(t) {
        if (t.is_dark && _DARK_THEMES.indexOf(t.css_key) === -1)   _DARK_THEMES.push(t.css_key);
        if (_CUSTOM_THEMES.indexOf(t.css_key) === -1)               _CUSTOM_THEMES.push(t.css_key);
        if (t.bg_body)                                               _BODY_COLORS[t.css_key] = t.bg_body;
    });
}

(function () {
    var html        = document.documentElement;
    var serverTheme = html.getAttribute('data-user-theme');
    var theme;

    if (!serverTheme || serverTheme === 'system') {
        var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        theme = prefersDark ? 'dark' : 'light';
    } else {
        theme = serverTheme;
    }

    localStorage.setItem('theme', theme);
    applyTheme(theme);
})();

function applyTheme(theme) {
    var html    = document.documentElement;
    var isDark  = _DARK_THEMES.indexOf(theme) !== -1;
    var isCustom = _CUSTOM_THEMES.indexOf(theme) !== -1;

    /* Bootstrap dark / light mode */
    html.setAttribute('data-bs-theme', isDark ? 'dark' : 'light');

    /* Custom palette (ocean / forest / midnight) */
    if (isCustom) {
        html.setAttribute('data-theme', theme);
    } else {
        html.removeAttribute('data-theme');
    }

    /* Instant body bg — eliminates flash before CSS loads */
    html.style.backgroundColor = _BODY_COLORS[theme] || _BODY_COLORS.light;

    localStorage.setItem('theme', theme);
}

function toggleTheme() {
    var current = localStorage.getItem('theme') || 'light';
    /* Toggle only between light ↔ dark; custom themes are set from Settings */
    var next = (current === 'dark' || _CUSTOM_THEMES.indexOf(current) !== -1)
        ? 'light'
        : 'dark';
    applyTheme(next);
    updateThemeIcon(next);
    _saveThemeToDb(next);
}

function updateThemeIcon(theme) {
    var icon = document.getElementById('theme-icon');
    if (!icon) return;
    var isDark = _DARK_THEMES.indexOf(theme) !== -1;
    icon.className = isDark ? 'fas fa-sun' : 'fas fa-moon';
}

function _saveThemeToDb(theme) {
    var csrf = document.getElementById('csrf_token');
    if (!csrf) return;
    fetch('/config/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf.value },
        body: JSON.stringify({ theme: theme }),
    });
}

document.addEventListener('DOMContentLoaded', function () {
    var theme = localStorage.getItem('theme') || 'light';
    updateThemeIcon(theme);
});
