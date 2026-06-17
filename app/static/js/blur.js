// Toggle API key visibility.
(function () {
    document.addEventListener('DOMContentLoaded', function () {
        var btn = document.getElementById('toggle-api-key');
        var key = document.getElementById('api-key');
        if (!btn || !key) return;

        btn.addEventListener('click', function () {
            var visible = btn.getAttribute('data-visible') === 'true';
            if (visible) {
                key.classList.add('blurred');
                btn.setAttribute('data-visible', 'false');
                btn.setAttribute('aria-pressed', 'false');
                btn.setAttribute('aria-label', 'Show API key');
                btn.setAttribute('title', 'Show API key');
                var icon = btn.querySelector('i');
                if (icon) { icon.classList.remove('fa-eye-slash'); icon.classList.add('fa-eye'); }
            } else {
                key.classList.remove('blurred');
                btn.setAttribute('data-visible', 'true');
                btn.setAttribute('aria-pressed', 'true');
                btn.setAttribute('aria-label', 'Hide API key');
                btn.setAttribute('title', 'Hide API key');
                var icon = btn.querySelector('i');
                if (icon) { icon.classList.remove('fa-eye'); icon.classList.add('fa-eye-slash'); }
            }
        });
    });
})();
