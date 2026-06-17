const { onMounted, onUnmounted } = Vue

export default {
    name: 'BaseModal',
    props: {
        visible:  { type: Boolean, required: true },
        title:    { type: String,  default: '' },
        size:     { type: String,  default: 'md' },   // sm | md | lg
        closable: { type: Boolean, default: true },
    },
    emits: ['close'],
    template: `
        <teleport to="body">
            <transition name="modal">
                <div v-if="visible" class="modal-backdrop" @click.self="onBackdropClick">
                    <div :class="['modal-box', 'modal-box--' + size]" role="dialog" aria-modal="true">
                        <div class="modal-header">
                            <span class="modal-title">{{ title }}</span>
                            <button v-if="closable" class="modal-close-btn" @click="$emit('close')" aria-label="Close">
                                <i class="fas fa-xmark"></i>
                            </button>
                        </div>
                        <div class="modal-body">
                            <slot></slot>
                        </div>
                        <div v-if="$slots.footer" class="modal-footer">
                            <slot name="footer"></slot>
                        </div>
                    </div>
                </div>
            </transition>
        </teleport>
    `,
    setup(props, { emit }) {
        function onBackdropClick() {
            if (props.closable) emit('close')
        }

        function onKeydown(e) {
            if (e.key === 'Escape' && props.visible && props.closable) {
                emit('close')
            }
        }

        onMounted(() => document.addEventListener('keydown', onKeydown))
        onUnmounted(() => document.removeEventListener('keydown', onKeydown))

        return { onBackdropClick }
    },
}
