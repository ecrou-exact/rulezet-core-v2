export default {
    name: 'ErrorPage',
    delimiters: ['[[', ']]'],
    props: {
        code:        { type: String, required: true },
        title:       { type: String, required: true },
        description: { type: String, default: '' },
        homeUrl:     { type: String, default: '/' },
        homeLabel:   { type: String, default: 'Go Home' },
    },
    template: `
    <div class="error-page">
        <div class="error-bg-blob error-bg-blob--1"></div>
        <div class="error-bg-blob error-bg-blob--2"></div>

        <div class="error-card">
            <div class="error-code-wrap">
                <div class="error-code-glow"></div>
                <span class="error-code">[[ code ]]</span>
            </div>

            <h1 class="error-title">[[ title ]]</h1>
            <p v-if="description" class="error-desc">[[ description ]]</p>

            <a :href="homeUrl" class="error-btn">
                <i class="fas fa-arrow-left" style="font-size:.8rem;"></i>
                [[ homeLabel ]]
            </a>
        </div>
    </div>
    `,
}
