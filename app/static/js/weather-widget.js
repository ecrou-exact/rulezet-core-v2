/*
  weather-widget.js — Topbar weather + local time chip.
  No API key required: uses Open-Meteo (open source) + browser Geolocation.
  Injected only when the admin has enabled the weather_widget_enabled flag.
*/

(function () {
    'use strict';

    /* WMO weather-code → Font Awesome icon class + color + label */
    var WMO = {
        0:  { i: 'fa-sun',                  c: '#F59E0B', l: 'Clear'          },
        1:  { i: 'fa-sun',                  c: '#F59E0B', l: 'Mostly clear'   },
        2:  { i: 'fa-cloud-sun',            c: '#94A3B8', l: 'Partly cloudy'  },
        3:  { i: 'fa-cloud',                c: '#94A3B8', l: 'Overcast'       },
        45: { i: 'fa-smog',                 c: '#94A3B8', l: 'Fog'            },
        48: { i: 'fa-smog',                 c: '#94A3B8', l: 'Freezing fog'   },
        51: { i: 'fa-cloud-rain',           c: '#60A5FA', l: 'Light drizzle'  },
        53: { i: 'fa-cloud-rain',           c: '#60A5FA', l: 'Drizzle'        },
        55: { i: 'fa-cloud-rain',           c: '#3B82F6', l: 'Heavy drizzle'  },
        61: { i: 'fa-cloud-rain',           c: '#60A5FA', l: 'Light rain'     },
        63: { i: 'fa-cloud-rain',           c: '#3B82F6', l: 'Rain'           },
        65: { i: 'fa-cloud-showers-heavy',  c: '#2563EB', l: 'Heavy rain'     },
        71: { i: 'fa-snowflake',            c: '#BAE6FD', l: 'Light snow'     },
        73: { i: 'fa-snowflake',            c: '#BAE6FD', l: 'Snow'           },
        75: { i: 'fa-snowflake',            c: '#93C5FD', l: 'Heavy snow'     },
        77: { i: 'fa-snowflake',            c: '#BAE6FD', l: 'Snow grains'    },
        80: { i: 'fa-cloud-rain',           c: '#60A5FA', l: 'Rain showers'   },
        81: { i: 'fa-cloud-showers-heavy',  c: '#3B82F6', l: 'Showers'        },
        82: { i: 'fa-cloud-showers-heavy',  c: '#2563EB', l: 'Heavy showers'  },
        85: { i: 'fa-snowflake',            c: '#BAE6FD', l: 'Snow showers'   },
        86: { i: 'fa-snowflake',            c: '#93C5FD', l: 'Heavy snow sh.' },
        95: { i: 'fa-cloud-bolt',           c: '#EAB308', l: 'Thunderstorm'   },
        96: { i: 'fa-cloud-bolt',           c: '#EAB308', l: 'Thunderstorm'   },
        99: { i: 'fa-cloud-bolt',           c: '#EAB308', l: 'Thunderstorm'   },
    };

    function wmo(code) {
        return WMO[code] || { i: 'fa-cloud', c: '#94A3B8', l: 'Unknown' };
    }

    function setIcon(el, info) {
        if (!el) return;
        el.innerHTML = '<i class="fas ' + info.i + '" style="color:' + info.c + '"></i>';
    }

    /* ── DOM refs ──────────────────────────────────────── */

    var _chip      = document.getElementById('ww-chip');
    var _icon      = document.getElementById('ww-icon');
    var _icon_lg   = null;
    var _temp      = document.getElementById('ww-temp');
    var _time      = document.getElementById('ww-time');
    var _tooltip   = document.getElementById('ww-tooltip');
    var _city      = document.getElementById('ww-city');
    var _desc      = document.getElementById('ww-desc');
    var _wind      = document.getElementById('ww-wind');
    var _timeLocal = document.getElementById('ww-time-local');

    /* ── State ─────────────────────────────────────────── */

    var _timezone   = null;   /* IANA tz from geolocation response */
    var _lat        = null;
    var _lon        = null;
    var _cityName   = '…';
    var _ticker     = null;

    /* ── Time ticker (updates every 15s) ──────────────── */

    function formatTime(tz) {
        try {
            return new Intl.DateTimeFormat('en-GB', {
                hour:   '2-digit',
                minute: '2-digit',
                timeZone: tz || Intl.DateTimeFormat().resolvedOptions().timeZone,
            }).format(new Date());
        } catch (e) {
            return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }
    }

    function tickTime() {
        var t = formatTime(_timezone);
        if (_time)      _time.textContent      = t;
        if (_timeLocal) _timeLocal.textContent = t;
    }

    function startTicker() {
        tickTime();
        _ticker = setInterval(tickTime, 15000);
    }

    /* ── Reverse geocode with Open-Meteo geocoding ─────── */

    function reverseGeocode(lat, lon, cb) {
        /* Use nominatim (OSM) — free, no key */
        fetch('https://nominatim.openstreetmap.org/reverse?format=json&lat=' + lat + '&lon=' + lon, {
            headers: { 'Accept-Language': 'en' }
        })
        .then(function (r) { return r.json(); })
        .then(function (d) {
            var addr = d.address || {};
            var city = addr.city || addr.town || addr.village || addr.county || addr.state || '';
            cb(city);
        })
        .catch(function () { cb(''); });
    }

    /* ── Fetch weather from Open-Meteo ─────────────────── */

    function fetchWeather(lat, lon) {
        var url = 'https://api.open-meteo.com/v1/forecast'
            + '?latitude=' + lat
            + '&longitude=' + lon
            + '&current=temperature_2m,weather_code,wind_speed_10m'
            + '&wind_speed_unit=kmh'
            + '&timezone=auto';

        fetch(url)
        .then(function (r) { return r.json(); })
        .then(function (d) {
            var cur  = d.current || {};
            var temp = Math.round(cur.temperature_2m);
            var code = cur.weather_code;
            var wind = Math.round(cur.wind_speed_10m);
            _timezone = d.timezone || null;

            var info = wmo(code);

            setIcon(_icon, info);
            setIcon(_icon_lg, info);
            if (_temp) _temp.textContent = temp + '°';
            if (_desc) _desc.textContent = info.l + ' · ' + wind + ' km/h wind';
            if (_wind) _wind.textContent = '';   /* already in desc */

            tickTime();   /* refresh time with correct tz */

            /* Show the chip */
            if (_chip) _chip.classList.add('ww-ready');
        })
        .catch(function () {
            /* Still show time even if weather fails */
            var fallback = { i: 'fa-clock', c: 'var(--text-muted)' };
            setIcon(_icon, fallback);
            setIcon(_icon_lg, fallback);
            if (_chip) _chip.classList.add('ww-ready');
        });
    }

    /* ── Geolocation ────────────────────────────────────── */

    function onPosition(pos) {
        _lat = pos.coords.latitude;
        _lon = pos.coords.longitude;

        reverseGeocode(_lat, _lon, function (city) {
            _cityName = city;
            if (_city) _city.textContent = city || 'Your location';
        });

        fetchWeather(_lat, _lon);
    }

    function onDenied() {
        /* No geolocation — show time only */
        var fallback = { i: 'fa-clock', c: 'var(--text-muted)' };
        setIcon(_icon, fallback);
        setIcon(_icon_lg, fallback);
        if (_city) _city.textContent = 'Location unavailable';
        if (_desc) _desc.textContent = 'Enable location for weather';
        if (_chip) _chip.classList.add('ww-ready');
    }

    /* ── Tooltip toggle ─────────────────────────────────── */

    window.wwToggle = function () {
        if (_tooltip) _tooltip.classList.toggle('ww-open');
    };

    document.addEventListener('click', function (e) {
        if (_chip && !_chip.contains(e.target) && _tooltip) {
            _tooltip.classList.remove('ww-open');
        }
    });

    /* ── Init ───────────────────────────────────────────── */

    document.addEventListener('DOMContentLoaded', function () {
        /* Re-assign DOM refs (script may run before DOM ready) */
        _chip      = document.getElementById('ww-chip');
        _icon      = document.getElementById('ww-icon');
        _icon_lg   = document.getElementById('ww-icon-lg');
        _temp      = document.getElementById('ww-temp');
        _time      = document.getElementById('ww-time');
        _tooltip   = document.getElementById('ww-tooltip');
        _city      = document.getElementById('ww-city');
        _desc      = document.getElementById('ww-desc');
        _wind      = document.getElementById('ww-wind');
        _timeLocal = document.getElementById('ww-time-local');

        startTicker();

        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(onPosition, onDenied, {
                timeout:            8000,
                maximumAge:         600000,   /* cache position 10 min */
                enableHighAccuracy: false,
            });
        } else {
            onDenied();
        }
    });

})();
