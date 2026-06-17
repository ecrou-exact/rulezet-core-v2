/*
  nav.js — Sidebar open/close/collapse + Bootstrap tooltips
  Loaded with defer in base.html. All functions are global (used by onclick handlers).
*/

// ── Mobile sidebar overlay ────────────────────────────────────

function openSidebar() {
    document.getElementById('appSidebar')?.classList.add('is-open');
    document.getElementById('sidebarBackdrop')?.classList.add('is-open');
    document.body.style.overflow = 'hidden';
}

function closeSidebar() {
    document.getElementById('appSidebar')?.classList.remove('is-open');
    document.getElementById('sidebarBackdrop')?.classList.remove('is-open');
    document.body.style.overflow = '';
}

// ── Desktop sidebar collapse ──────────────────────────────────

function toggleSidebarCollapsed() {
    var wrapper   = document.getElementById('appWrapper');
    var chevron   = document.getElementById('sidebar-chevron');
    var collapsed = wrapper.classList.toggle('sidebar-collapsed');

    if (chevron) {
        chevron.classList.toggle('fa-chevron-left',  !collapsed);
        chevron.classList.toggle('fa-chevron-right',  collapsed);
    }

    _updateTooltips(collapsed);

    var csrf = document.getElementById('csrf_token');
    if (!csrf) return;
    fetch('/config/update', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrf.value,
        },
        body: JSON.stringify({ sidebar_collapsed: collapsed }),
    });
}

// ── Bootstrap tooltips (enabled only when sidebar is collapsed) ─

var _tooltipInstances = [];

function _initTooltips() {
    if (typeof bootstrap === 'undefined') return;
    var els = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    _tooltipInstances = Array.from(els).map(function (el) {
        return new bootstrap.Tooltip(el, { trigger: 'hover' });
    });
}

function _updateTooltips(collapsed) {
    _tooltipInstances.forEach(function (t) {
        collapsed ? t.enable() : t.disable();
        if (!collapsed) t.hide();
    });
}

// ── Init on DOMContentLoaded ──────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
    var wrapper   = document.getElementById('appWrapper');
    var chevron   = document.getElementById('sidebar-chevron');
    var collapsed = wrapper ? wrapper.classList.contains('sidebar-collapsed') : false;

    if (chevron) {
        chevron.classList.toggle('fa-chevron-left',  !collapsed);
        chevron.classList.toggle('fa-chevron-right',  collapsed);
    }

    _initTooltips();
    _updateTooltips(collapsed);
});
