const { computed } = Vue

export default {
    name: 'UserAvatar',
    props: {
        firstName: { type: String, default: '' },
        lastName:  { type: String, default: '' },
        avatarUrl: { type: String, default: null },
        size:      { type: String, default: 'md' },  // xs sm md lg xl
    },
    template: `
        <div :class="['user-avatar', 'user-avatar--' + size]" :title="fullName">
            <img v-if="avatarUrl" :src="avatarUrl" :alt="initials" class="user-avatar__img">
            <span v-else class="user-avatar__initials">{{ initials }}</span>
        </div>
    `,
    setup(props) {
        const initials = computed(() => {
            const f = (props.firstName || ' ')[0].toUpperCase()
            const l = (props.lastName  || ' ')[0].toUpperCase()
            return f + l
        })
        const fullName = computed(() => `${props.firstName} ${props.lastName}`.trim())
        return { initials, fullName }
    }
}
