import BaseModal from './base-modal.js'
import { apiFetch } from '../../constants.js'
import { create_message } from '../../toaster.js'

const { ref, watch } = Vue

const TOAST = { SUCCESS: 'success', ERROR: 'danger' }

export default {
    name: 'ModalEditUser',
    components: { BaseModal },
    props: {
        visible: { type: Boolean, required: true },
        user:    { type: Object,  default: null },
        roles:   { type: Array,   default: () => [] },
    },
    emits: ['close', 'saved'],
    template: `
        <base-modal
            :visible="visible"
            title="Edit user"
            size="md"
            @close="$emit('close')">

            <form @submit.prevent="submit" id="modal-edit-user-form">
                <div class="row g-3">

                    <div class="col-6">
                        <label class="form-label" style="font-size:.82rem;font-weight:600;">First name</label>
                        <input v-model="form.first_name" type="text" class="form-control form-control-sm"
                               maxlength="64" required>
                    </div>

                    <div class="col-6">
                        <label class="form-label" style="font-size:.82rem;font-weight:600;">Last name</label>
                        <input v-model="form.last_name" type="text" class="form-control form-control-sm"
                               maxlength="64" required>
                    </div>

                    <div class="col-12">
                        <label class="form-label" style="font-size:.82rem;font-weight:600;">Email</label>
                        <input v-model="form.email" type="email" class="form-control form-control-sm"
                               maxlength="128" required>
                    </div>

                    <div class="col-12">
                        <label class="form-label" style="font-size:.82rem;font-weight:600;">Username (handle)</label>
                        <div class="input-group input-group-sm">
                            <span class="input-group-text">@</span>
                            <input v-model="form.username" type="text" class="form-control"
                                   maxlength="50" placeholder="optional">
                        </div>
                    </div>

                    <div class="col-12">
                        <label class="form-label" style="font-size:.82rem;font-weight:600;">Role</label>
                        <select v-model="form.role_id" class="form-select form-select-sm">
                            <option v-for="r in roles" :key="r.id" :value="r.id">{{ r.name }}</option>
                        </select>
                    </div>

                    <div class="col-12">
                        <div class="form-check form-switch">
                            <input v-model="form.is_verified" class="form-check-input" type="checkbox"
                                   id="modal-edit-verified-check">
                            <label class="form-check-label" for="modal-edit-verified-check"
                                   style="font-size:.82rem;">Verified</label>
                        </div>
                    </div>

                </div>
            </form>

            <template #footer>
                <button class="btn btn-sm btn-secondary" type="button" @click="$emit('close')">Cancel</button>
                <button class="btn btn-sm btn-primary" type="submit" form="modal-edit-user-form" :disabled="loading">
                    <span v-if="loading"><i class="fas fa-circle-notch fa-spin me-1"></i>Saving…</span>
                    <span v-else><i class="fas fa-floppy-disk me-1"></i>Save</span>
                </button>
            </template>

        </base-modal>
    `,
    setup(props, { emit }) {
        const loading = ref(false)
        const form    = ref({
            first_name:  '',
            last_name:   '',
            email:       '',
            username:    '',
            role_id:     null,
            is_verified: true,
        })

        // Sync form when user prop changes (modal opens for a new user)
        watch(() => props.user, (u) => {
            if (!u) return
            form.value = {
                first_name:  u.first_name  || '',
                last_name:   u.last_name   || '',
                email:       u.email       || '',
                username:    u.username    || '',
                role_id:     u.role_id     ?? null,
                is_verified: u.is_verified ?? true,
            }
        }, { immediate: true })

        async function submit() {
            if (!props.user) return
            loading.value = true
            try {
                const payload = {
                    first_name:  form.value.first_name,
                    last_name:   form.value.last_name,
                    email:       form.value.email,
                    username:    form.value.username || null,
                    role_id:     form.value.role_id,
                    is_verified: form.value.is_verified,
                }
                const res = await apiFetch(`/api/account/admin/user/${props.user.id}`, 'PUT', payload)
                if (res.ok) {
                    const data = await res.json()
                    await create_message('User updated', TOAST.SUCCESS, false)
                    emit('saved', data)
                    emit('close')
                } else {
                    const err = await res.json().catch(() => ({}))
                    await create_message(err.message || 'Failed to update user', TOAST.ERROR, true)
                }
            } finally {
                loading.value = false
            }
        }

        return { form, loading, submit }
    },
}
