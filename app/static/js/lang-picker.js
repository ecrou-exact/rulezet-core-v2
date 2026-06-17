/*
  lang-picker.js — Google Translate custom integration.
  Defines googleTranslateElementInit (called by GT script as ?cb=)
  and the lpToggle / lpSelect / lpReset globals used by base.html markup.
  Must be loaded synchronously BEFORE the translate.google.com script tag.
*/

var LANGS = [
    { code: 'fr',    name: 'Français',        flag: '🇫🇷' },
    { code: 'es',    name: 'Español',          flag: '🇪🇸' },
    { code: 'de',    name: 'Deutsch',          flag: '🇩🇪' },
    { code: 'it',    name: 'Italiano',         flag: '🇮🇹' },
    { code: 'pt',    name: 'Português',        flag: '🇵🇹' },
    { code: 'nl',    name: 'Nederlands',       flag: '🇳🇱' },
    { code: 'pl',    name: 'Polski',           flag: '🇵🇱' },
    { code: 'lb',    name: 'Lëtzebuergesch',   flag: '🇱🇺' },
    { code: 'ru',    name: 'Русский',          flag: '🇷🇺' },
    { code: 'zh-CN', name: '中文',             flag: '🇨🇳' },
    { code: 'ja',    name: '日本語',           flag: '🇯🇵' },
    { code: 'ar',    name: 'العربية',          flag: '🇸🇦' },
    { code: 'tr',    name: 'Türkçe',           flag: '🇹🇷' },
    { code: 'ko',    name: '한국어',           flag: '🇰🇷' },
];

/* Called by Google's script after it loads */
function googleTranslateElementInit() {
    new google.translate.TranslateElement({
        pageLanguage: 'en',
        autoDisplay:  false,
    }, 'google_translate_element');
}

(function () {

    /* ── Build the language list items ───────────────── */
    function buildList() {
        var list = document.getElementById('langPickerList');
        if (!list) return;
        LANGS.forEach(function (l) {
            var btn = document.createElement('button');
            btn.className    = 'lang-picker-item';
            btn.dataset.code = l.code;
            btn.innerHTML    =
                '<span class="lang-flag">' + l.flag + '</span>' +
                '<span class="lang-name">' + l.name + '</span>';
            btn.onclick = function () { lpSelect(l.code, l.name, l.flag); };
            list.appendChild(btn);
        });
    }

    /* ── Read active lang from cookie ────────────────── */
    function readActiveLang() {
        var m = document.cookie.match(/googtrans=\/\w+\/([\w-]+)/);
        return m ? m[1] : null;
    }

    /* ── Refresh active state in the UI ─────────────── */
    function updateActiveUI() {
        var active = readActiveLang();
        var badge  = document.getElementById('langPickerActive');
        document.querySelectorAll('.lang-picker-item').forEach(function (el) {
            el.classList.toggle('is-active', el.dataset.code === active);
        });
        if (badge) {
            if (active) {
                var found = LANGS.find(function (l) { return l.code === active; });
                badge.textContent = found ? found.flag : '';
                badge.style.display = 'inline';
            } else {
                badge.textContent   = '';
                badge.style.display = 'none';
            }
        }
    }

    /* ── Toggle dropdown ─────────────────────────────── */
    window.lpToggle = function () {
        var dd  = document.getElementById('langPickerDropdown');
        var btn = document.getElementById('langPickerBtn');
        if (!dd) return;
        var open = dd.classList.toggle('is-open');
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        if (open) updateActiveUI();
    };

    /* ── Close on outside click ──────────────────────── */
    document.addEventListener('click', function (e) {
        var picker = document.getElementById('langPicker');
        if (picker && !picker.contains(e.target)) {
            var dd = document.getElementById('langPickerDropdown');
            if (dd) dd.classList.remove('is-open');
        }
    });

    /* ── Interact with the hidden GT combo ───────────── */
    function gtComboSelect(code) {
        var combo = document.querySelector('.goog-te-combo');
        if (combo) {
            combo.value = code;
            combo.dispatchEvent(new Event('change'));
            return true;
        }
        return false;
    }

    /* ── Select a language ───────────────────────────── */
    window.lpSelect = function (code, name, flag) {
        var dd = document.getElementById('langPickerDropdown');
        if (dd) dd.classList.remove('is-open');

        if (!gtComboSelect(code)) {
            var tries = 0;
            var iv = setInterval(function () {
                if (gtComboSelect(code) || ++tries > 10) clearInterval(iv);
            }, 200);
        }

        var host = location.hostname;
        document.cookie = 'googtrans=/auto/' + code + '; path=/';
        document.cookie = 'googtrans=/auto/' + code + '; path=/; domain=' + host;

        var badge = document.getElementById('langPickerActive');
        if (badge) { badge.textContent = flag; badge.style.display = 'inline'; }

        document.querySelectorAll('.lang-picker-item').forEach(function (el) {
            el.classList.toggle('is-active', el.dataset.code === code);
        });
    };

    /* ── Reset to original language ──────────────────── */
    window.lpReset = function () {
        var host = location.hostname;
        document.cookie = 'googtrans=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/';
        document.cookie = 'googtrans=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; domain=' + host;
        location.reload();
    };

    /* ── Init on DOM ready ───────────────────────────── */
    document.addEventListener('DOMContentLoaded', function () {
        buildList();
        updateActiveUI();
    });

})();
