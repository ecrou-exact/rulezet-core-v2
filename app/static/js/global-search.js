let gsActiveIdx = -1;

function gsOpen() {
    document.getElementById('gsPanel').classList.add('is-open');
    document.getElementById('gsBackdrop').classList.add('is-open');
    const input = document.getElementById('gsInput');
    input.value = '';
    input.focus();
    gsRender('');
}

function gsClose() {
    document.getElementById('gsPanel').classList.remove('is-open');
    document.getElementById('gsBackdrop').classList.remove('is-open');
    gsActiveIdx = -1;
}

function gsHighlight(text, query) {
    if (!query) return text;
    const i = text.toLowerCase().indexOf(query.toLowerCase());
    if (i === -1) return text;
    return text.slice(0, i) + '<mark>' + text.slice(i, i + query.length) + '</mark>' + text.slice(i + query.length);
}

function gsRender(query) {
    const body = document.getElementById('gsBody');
    const q = query.trim().toLowerCase();
    const filtered = q ? GS_SECTIONS.filter(s => s.label.toLowerCase().includes(q)) : GS_SECTIONS;

    if (!filtered.length) {
        body.innerHTML = '<div class="gs-empty">No results for "' + query + '"</div>';
        return;
    }

    const groups = {};
    filtered.forEach(s => {
        const g = s.group || 'Navigation';
        if (!groups[g]) groups[g] = [];
        groups[g].push(s);
    });

    let html = '';
    Object.entries(groups).forEach(([group, items]) => {
        html += `<div class="gs-group-label">${group}</div>`;
        items.forEach(item => {
            const ext = item.external ? ' target="_blank" rel="noopener noreferrer"' : '';
            const extIcon = item.external ? '<i class="fas fa-arrow-up-right-from-square gs-item-ext"></i>' : '';
            html += `<a href="${item.href}" class="gs-item"${ext}>
                <span class="gs-item-icon"><i class="fas ${item.icon}"></i></span>
                <span class="gs-item-label">${gsHighlight(item.label, query)}</span>
                ${extIcon}
            </a>`;
        });
    });
    body.innerHTML = html;
    gsActiveIdx = -1;
}

document.addEventListener('DOMContentLoaded', function () {
    const input = document.getElementById('gsInput');
    if (!input) return;

    input.addEventListener('input', function () { gsRender(this.value); });

    input.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') { gsClose(); return; }
        const items = document.querySelectorAll('#gsBody .gs-item');
        if (!items.length) return;
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            gsActiveIdx = Math.min(gsActiveIdx + 1, items.length - 1);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            gsActiveIdx = Math.max(gsActiveIdx - 1, 0);
        } else if (e.key === 'Enter' && gsActiveIdx >= 0) {
            items[gsActiveIdx].click();
            return;
        } else { return; }
        items.forEach((el, i) => el.classList.toggle('is-active', i === gsActiveIdx));
        items[gsActiveIdx]?.scrollIntoView({ block: 'nearest' });
    });

    document.addEventListener('keydown', function (e) {
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
            e.preventDefault();
            document.getElementById('gsPanel').classList.contains('is-open') ? gsClose() : gsOpen();
        }
    });
});
