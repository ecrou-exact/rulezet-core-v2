document.addEventListener('DOMContentLoaded', function () {
    const btn = document.getElementById('scrollTopBtn')
    if (!btn) return

    const THRESHOLD = 320

    window.addEventListener('scroll', function () {
        if (window.scrollY > THRESHOLD) {
            btn.classList.add('is-visible')
        } else {
            btn.classList.remove('is-visible')
        }
    }, { passive: true })

    btn.addEventListener('click', function () {
        btn.classList.add('is-clicked')
        window.scrollTo({ top: 0, behavior: 'smooth' })
        setTimeout(() => btn.classList.remove('is-clicked'), 300)
    })
})
