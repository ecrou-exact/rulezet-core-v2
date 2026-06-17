const { computed } = Vue

export default {
    name: 'PasswordStrength',
    props: {
        value: { type: String, default: '' },
    },
    template: `
        <div v-if="value.length > 0" class="password-strength">
            <div class="password-strength-bar">
                <div class="password-strength-fill"
                     :class="'password-strength-fill--' + level"
                     :style="{ width: (score / 4 * 100) + '%' }">
                </div>
            </div>
            <div class="password-strength-criteria">
                <span :class="['password-strength-chip', { met: has_upper }]">
                    <i :class="has_upper ? 'fas fa-check' : 'fas fa-xmark'"></i> Uppercase
                </span>
                <span :class="['password-strength-chip', { met: has_lower }]">
                    <i :class="has_lower ? 'fas fa-check' : 'fas fa-xmark'"></i> Lowercase
                </span>
                <span :class="['password-strength-chip', { met: has_digit }]">
                    <i :class="has_digit ? 'fas fa-check' : 'fas fa-xmark'"></i> Number
                </span>
                <span :class="['password-strength-chip', { met: has_length }]">
                    <i :class="has_length ? 'fas fa-check' : 'fas fa-xmark'"></i> 8+ chars
                </span>
            </div>
        </div>
    `,
    setup(props) {
        const has_upper  = computed(() => /[A-Z]/.test(props.value))
        const has_lower  = computed(() => /[a-z]/.test(props.value))
        const has_digit  = computed(() => /\d/.test(props.value))
        const has_length = computed(() => props.value.length >= 8)

        const score = computed(() =>
            [has_upper.value, has_lower.value, has_digit.value, has_length.value]
                .filter(Boolean).length
        )

        const level = computed(() => {
            if (score.value <= 1) return 'weak'
            if (score.value === 2) return 'fair'
            if (score.value === 3) return 'good'
            return 'strong'
        })

        return { has_upper, has_lower, has_digit, has_length, score, level }
    }
}
