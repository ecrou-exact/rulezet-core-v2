/**
 * license-selector.js — SPDX license picker.
 *
 * Loads all identifiers from GET /api/licenses/ once, then filters client-side.
 *
 * Props:
 *   modelValue  : String   Selected SPDX identifier (v-model)
 *   placeholder : String
 *   disabled    : Boolean
 *   clearable   : Boolean  Show × to clear selection (default true)
 *
 * Emits: update:modelValue
 */
import { apiFetch } from '/static/js/constants.js'

const { ref, computed, onMounted, onBeforeUnmount } = Vue

const LicenseSelector = {
    name: 'LicenseSelector',
    emits: ['update:modelValue'],
    props: {
        modelValue:  { type: String,  default: '' },
        placeholder: { type: String,  default: 'Search SPDX license…' },
        disabled:    { type: Boolean, default: false },
        clearable:   { type: Boolean, default: true },
    },
    template: `
<div class="ls-root" :class="disabled ? 'ls-root--disabled' : ''" ref="root_ref">

    <div class="ls-input-wrap">
        <i class="fas fa-scale-balanced ls-icon"></i>

        <input
            ref="input_ref"
            v-model="query"
            class="ls-input"
            :placeholder="modelValue || placeholder"
            :class="modelValue ? 'ls-input--has-value' : ''"
            :disabled="disabled"
            @focus="open = true"
            @keydown.escape="close"
            @keydown.down.prevent="move(1)"
            @keydown.up.prevent="move(-1)"
            @keydown.enter.prevent="confirmHighlighted"
            @input="highlighted = 0"
        />

        <span v-if="modelValue && !query" class="ls-current-badge">
            {{ modelValue }}
        </span>

        <button v-if="clearable && modelValue && !disabled"
                class="ls-clear" @mousedown.prevent="clear" type="button" title="Clear">
            <i class="fas fa-xmark"></i>
        </button>
    </div>

    <div v-if="open" class="ls-dropdown" ref="dropdown_ref">
        <div v-if="!ready" class="ls-state">
            <i class="fas fa-spinner fa-spin me-2"></i>Loading licenses…
        </div>
        <div v-else-if="filtered.length === 0" class="ls-state ls-state--empty">
            <i class="fas fa-magnifying-glass me-2"></i>No match for "{{ query }}"
        </div>
        <template v-else>
            <div
                v-for="(lic, idx) in filtered"
                :key="lic"
                class="ls-item"
                :class="itemClass(idx, lic)"
                @mouseenter="highlighted = idx"
                @mousedown.prevent="select(lic)">
                <span class="ls-item-name">{{ lic }}</span>
                <i v-if="lic === modelValue" class="fas fa-check ls-item-check"></i>
            </div>
        </template>
    </div>

</div>`,
    setup(props, { emit }) {
        const root_ref     = ref(null)
        const input_ref    = ref(null)
        const dropdown_ref = ref(null)
        const query        = ref('')
        const open         = ref(false)
        const ready        = ref(false)
        const highlighted  = ref(0)
        const all_licenses = ref([])

        const filtered = computed(function() {
            var q = query.value.trim().toLowerCase()
            if (!q) return all_licenses.value.slice(0, 60)
            var prefix = all_licenses.value.filter(function(l) { return l.toLowerCase().startsWith(q) })
            var rest   = all_licenses.value.filter(function(l) { return !l.toLowerCase().startsWith(q) && l.toLowerCase().indexOf(q) !== -1 })
            return prefix.concat(rest).slice(0, 60)
        })

        function itemClass(idx, lic) {
            var cls = []
            if (highlighted.value === idx) cls.push('is-highlighted')
            if (lic === props.modelValue)  cls.push('is-selected')
            return cls.join(' ')
        }

        function select(lic) {
            emit('update:modelValue', lic === props.modelValue ? '' : lic)
            query.value = ''
            close()
        }

        function clear() {
            emit('update:modelValue', '')
            query.value = ''
        }

        function close() {
            open.value       = false
            query.value      = ''
            highlighted.value = 0
        }

        function move(dir) {
            var next = highlighted.value + dir
            highlighted.value = Math.max(0, Math.min(filtered.value.length - 1, next))
        }

        function confirmHighlighted() {
            if (filtered.value[highlighted.value]) select(filtered.value[highlighted.value])
        }

        function onClickOutside(e) {
            if (root_ref.value && !root_ref.value.contains(e.target)) close()
        }

        onMounted(async function() {
            document.addEventListener('mousedown', onClickOutside)
            var res = await apiFetch('/api/licenses/?limit=200', 'GET')
            if (res.ok) {
                var d = await res.json()
                all_licenses.value = d.licenses || []
                ready.value = true
            }
        })
        onBeforeUnmount(function() {
            document.removeEventListener('mousedown', onClickOutside)
        })

        return {
            root_ref, input_ref, dropdown_ref,
            query, open, ready, highlighted, filtered,
            itemClass, select, clear, close, move, confirmHighlighted,
        }
    },
}

export default LicenseSelector
export { LicenseSelector }
