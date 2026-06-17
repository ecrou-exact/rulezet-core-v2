/*
  christmas-effects.js — Self-activating Christmas overlay.
  Injects animated lights strip + falling snow only when data-theme="christmas".
  Cleans up automatically when the theme changes.
  No external deps — runs immediately, safe before DOMContentLoaded.
*/

(function () {
    'use strict';

    var BULB_COLORS  = ['#FF3030', '#2FCC6A', '#FFD700', '#4A90D9', '#FF88CC', '#FFFFFF'];
    var SNOW_CHARS   = ['❄', '❅', '❆', '✦', '•'];
    var SNOW_COUNT   = 38;
    var BULB_SPACING = 52;  /* px between bulb centres */
    var BLINK_DURS   = [1.4, 1.8, 2.2, 2.6, 1.0, 3.0]; /* seconds per color */

    /* ── helpers ─────────────────────────────────────── */

    function rand(min, max) { return min + Math.random() * (max - min); }
    function randInt(min, max) { return Math.floor(rand(min, max)); }
    function pick(arr) { return arr[randInt(0, arr.length)]; }

    function isChristmas() {
        return document.documentElement.getAttribute('data-theme') === 'christmas';
    }

    /* ── lights strip ────────────────────────────────── */

    function buildLights() {
        if (document.getElementById('xmas-lights')) return;

        var wrap = document.createElement('div');
        wrap.id = 'xmas-lights';
        wrap.setAttribute('aria-hidden', 'true');

        /* Wire */
        var wire = document.createElement('div');
        wire.className = 'xmas-wire';
        wrap.appendChild(wire);

        /* Bulbs — enough to cover 3840px (4K) at BULB_SPACING px each */
        var count = Math.ceil(3840 / BULB_SPACING) + 2;

        for (var i = 0; i < count; i++) {
            var colorIdx = i % BULB_COLORS.length;
            var color    = BULB_COLORS[colorIdx];
            var dur      = BLINK_DURS[colorIdx];
            /* Stagger blink: neighbours don't blink together */
            var delay    = -rand(0, dur);

            /* Slight vertical variation for the "sagging wire" feel */
            var topOff   = Math.round(rand(-1, 3));

            var bulb = document.createElement('span');
            bulb.className = 'xmas-bulb';
            bulb.style.cssText =
                'left:' + (i * BULB_SPACING + rand(-4, 4)) + 'px;' +
                'top:' + topOff + 'px;' +
                '--bc:' + color + ';';

            var glass = document.createElement('span');
            glass.className = 'xmas-bulb-glass';
            glass.style.cssText =
                '--bc:' + color + ';' +
                '--dur:' + dur + 's;' +
                '--delay:' + delay.toFixed(2) + 's;';

            bulb.appendChild(glass);
            wrap.appendChild(bulb);
        }

        /* Insert as very first child of body (behind everything) */
        document.body.insertBefore(wrap, document.body.firstChild);
    }

    /* ── snowflakes ──────────────────────────────────── */

    function buildSnow() {
        if (document.getElementById('xmas-snow')) return;

        var container = document.createElement('div');
        container.id = 'xmas-snow';
        container.setAttribute('aria-hidden', 'true');

        for (var i = 0; i < SNOW_COUNT; i++) {
            var flake = document.createElement('span');
            flake.className = 'xmas-flake';

            var size  = rand(7, 16);
            var left  = rand(0, 98);      /* vw */
            var dur   = rand(9, 22);      /* s  */
            var delay = -rand(0, dur);    /* start mid-fall for instant effect */
            var drift = rand(-60, 60);    /* horizontal drift px */
            var opacity = rand(0.45, 0.9);

            flake.textContent = pick(SNOW_CHARS);
            flake.style.cssText =
                'left:' + left + 'vw;' +
                'font-size:' + size + 'px;' +
                'opacity:' + opacity + ';' +
                '--dur:' + dur + 's;' +
                '--delay:' + delay.toFixed(1) + 's;' +
                '--drift:' + drift + 'px;';

            container.appendChild(flake);
        }

        document.body.appendChild(container);
    }

    /* ── star trail cursor (subtle) ─────────────────── */

    var _trail_enabled = false;
    var _trail_cleanup = null;

    function enableTrail() {
        if (_trail_enabled) return;
        _trail_enabled = true;
        var handler = function (e) {
            if (!isChristmas()) return;
            var star = document.createElement('span');
            star.className = 'xmas-cursor-star';
            star.textContent = pick(['★', '✦', '❄', '·', '✧']);
            star.style.cssText =
                'position:fixed;' +
                'left:' + e.clientX + 'px;' +
                'top:' + e.clientY + 'px;' +
                'pointer-events:none;' +
                'z-index:10001;' +
                'font-size:' + rand(8, 16) + 'px;' +
                'color:' + pick(['#FFD700','#E8372A','#2FCC6A','#ffffff']) + ';' +
                'animation:xmas-star-trail 0.8s ease-out forwards;' +
                'transform:translate(-50%,-50%);' +
                'will-change:transform,opacity;';
            document.body.appendChild(star);
            setTimeout(function () { star.remove(); }, 820);
        };
        /* Throttle to ~16ms */
        var last = 0;
        var throttled = function (e) {
            var now = Date.now();
            if (now - last < 80) return;
            last = now;
            handler(e);
        };
        document.addEventListener('mousemove', throttled);
        _trail_cleanup = function () { document.removeEventListener('mousemove', throttled); };
    }

    function disableTrail() {
        if (!_trail_enabled) return;
        _trail_enabled = false;
        if (_trail_cleanup) { _trail_cleanup(); _trail_cleanup = null; }
    }

    /* ── activate / deactivate ───────────────────────── */

    function activate() {
        buildLights();
        buildSnow();
        enableTrail();
    }

    function deactivate() {
        ['xmas-lights', 'xmas-snow'].forEach(function (id) {
            var el = document.getElementById(id);
            if (el) el.remove();
        });
        disableTrail();
    }

    function check() {
        isChristmas() ? activate() : deactivate();
    }

    /* ── keyframe injection ──────────────────────────── */

    function injectKeyframes() {
        if (document.getElementById('xmas-kf')) return;
        var style = document.createElement('style');
        style.id  = 'xmas-kf';
        style.textContent = [
            '@keyframes xmas-star-trail{',
            '  0%   { transform:translate(-50%,-50%) scale(1);   opacity:1; }',
            '  100% { transform:translate(-50%,-120%) scale(0.2); opacity:0; }',
            '}',
        ].join('');
        document.head.appendChild(style);
    }

    /* ── init ────────────────────────────────────────── */

    injectKeyframes();

    /* Run once DOM is ready */
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', check);
    } else {
        check();
    }

    /* Watch theme attribute changes (user switches theme in Settings) */
    new MutationObserver(function () { check(); }).observe(
        document.documentElement,
        { attributes: true, attributeFilter: ['data-theme'] }
    );

})();
