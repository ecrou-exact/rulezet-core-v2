import BaseModal from './base-modal.js'

export default {
    name: 'ModalConfirm',
    components: { BaseModal },
    props: {
        visible:       { type: Boolean, required: true },
        title:         { type: String,  default: 'Confirm' },
        message:       { type: String,  default: 'Are you sure?' },
        confirmLabel:  { type: String,  default: 'Confirm' },
        variant:       { type: String,  default: 'danger' },  // danger | warning | primary
        loading:       { type: Boolean, default: false },
    },
    emits: ['confirm', 'cancel'],
    template: `
        <base-modal
            :visible="visible"
            :title="title"
            size="sm"
            @close="$emit('cancel')">

            <p style="margin:0;font-size:.88rem;color:var(--text-secondary);">{{ message }}</p>

            <template #footer>
                <button class="btn btn-sm btn-secondary" type="button"
                        :disabled="loading" @click="$emit('cancel')">
                    Cancel
                </button>
                <button :class="['btn', 'btn-sm', 'btn-' + variant]" type="button"
                        :disabled="loading" @click="$emit('confirm')">
                    <span v-if="loading"><i class="fas fa-circle-notch fa-spin me-1"></i>Please wait…</span>
                    <span v-else>{{ confirmLabel }}</span>
                </button>
            </template>

        </base-modal>
    `,
}
