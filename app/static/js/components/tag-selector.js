/**
 * tag-selector.js — Interactive tag picker with inline creation.
 *
 * Props:
 *   modelValue  : Array   Selected tag objects (v-model)
 *   sources     : Array   Allowed sources ['custom','taxonomy','galaxy','vulnerability']
 *   max         : Number  Max selectable tags (0 = unlimited)
 *   placeholder : String
 *   disabled    : Boolean
 *
 * Emits: update:modelValue
 *
 * Exports: TagSelector (default), TagCreateCustom, TagCreateVulnerability, detectCVE
 */
import TagPill from '/static/js/components/tag-pill.js'
import { apiFetch, TOAST } from '/static/js/constants.js'
import { create_message }  from '/static/js/toaster.js'

const { ref, computed, onMounted, onBeforeUnmount, nextTick } = Vue

/*───────────────────────────────────────────────────────────
  CVE / vulnerability syntax detection (mirrors detect_cve.py)
───────────────────────────────────────────────────────────*/
const CVE_PATTERN = (
    '\\b(' +
    'CVE[-\\s]\\d{4}[-\\s]\\d{4,7}' +
    '|GCVE-\\d+-\\d{4}-\\d+' +
    '|GHSA-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{4}' +
    '|PYSEC-\\d{4}-\\d{2,5}' +
    '|GSD-\\d{4}-\\d{4,5}' +
    '|wid-sec-w-\\d{4}-\\d{4}' +
    '|cisco-sa-\\d{8}-[a-zA-Z0-9]+' +
    '|RHSA-\\d{4}:\\d{4}' +
    '|msrc_CVE-\\d{4}-\\d{4,}' +
    '|CERTFR-\\d{4}-[A-Z]{3}-\\d{3}' +
    ')\\b'
)
const CVE_RE = new RegExp(CVE_PATTERN, 'gi')

function detectCVE(text) {
    if (!text) return { valid: false, ids: [] }
    const matches = Array.from(text.matchAll(CVE_RE)).map(function(m) {
        return m[0].replace(/[\s_]/g, '-').toUpperCase()
    })
    const unique = []
    const seen = {}
    matches.forEach(function(id) { if (!seen[id]) { seen[id] = true; unique.push(id) } })
    unique.sort()
    return { valid: true, ids: unique }
}

function normalizeCVE(raw) {
    return raw.trim().replace(/[\s_]/g, '-').toUpperCase()
}

/*───────────────────────────────────────────────────────────
  TagCreateCustom
───────────────────────────────────────────────────────────*/
const TagCreateCustom = {
    name: 'TagCreateCustom',
    emits: ['created', 'close'],
    delimiters: ['[[', ']]'],
    template: `
<div class="ts-modal-backdrop" @mousedown.self="$emit('close')">
    <div class="ts-modal" role="dialog" aria-modal="true">
        <div class="ts-modal-header">
            <span class="ts-modal-title"><i class="fas fa-user-tag me-2"></i>New custom tag</span>
            <button class="ts-modal-close" @click="$emit('close')" aria-label="Close">
                <i class="fas fa-xmark"></i>
            </button>
        </div>
        <div class="ts-modal-body">
            <div class="ts-field">
                <label class="ts-label">Name <span class="ts-required">*</span></label>
                <input ref="name_ref" v-model.trim="name" class="ts-input"
                       placeholder="namespace:value  or  simple-name"
                       @keydown.enter="submit" />
                <p v-if="name_hint" class="ts-hint">[[ name_hint ]]</p>
            </div>
            <div class="ts-field">
                <label class="ts-label">Description</label>
                <textarea v-model.trim="description" class="ts-input ts-textarea"
                          rows="2" placeholder="Optional description"></textarea>
            </div>
            <div class="ts-field-row">
                <div class="ts-field">
                    <label class="ts-label">Color</label>
                    <div class="ts-color-row">
                        <input type="color" v-model="color" class="ts-color-input" />
                        <span class="ts-color-hex">[[ color ]]</span>
                    </div>
                </div>
                <div class="ts-field">
                    <label class="ts-label">Icon <span class="ts-hint-inline">(FA class)</span></label>
                    <input v-model.trim="icon" class="ts-input" placeholder="fa-tag" />
                </div>
            </div>
            <div class="ts-field">
                <label class="ts-label">Visibility</label>
                <label class="ts-toggle">
                    <input type="checkbox" v-model="is_public" />
                    <span class="ts-toggle-label">Public (visible to all users)</span>
                </label>
            </div>
        </div>
        <div class="ts-modal-footer">
            <button class="ts-btn ts-btn-ghost" @click="$emit('close')">Cancel</button>
            <button class="ts-btn ts-btn-primary" :disabled="busy || !name" @click="submit">
                <i v-if="busy" class="fas fa-spinner fa-spin me-1"></i>
                <i v-else class="fas fa-plus me-1"></i>Create tag
            </button>
        </div>
        <p v-if="err" class="ts-error"><i class="fas fa-triangle-exclamation me-1"></i>[[ err ]]</p>
    </div>
</div>`,
    setup(props, { emit }) {
        const name_ref    = ref(null)
        const busy        = ref(false)
        const err         = ref('')
        const name        = ref('')
        const description = ref('')
        const color       = ref('#6c757d')
        const icon        = ref('fa-tag')
        const is_public   = ref(false)

        const name_hint = computed(function() {
            if (!name.value) return ''
            var idx = name.value.indexOf(':')
            if (idx !== -1) return 'Namespace: "' + name.value.slice(0, idx) + '"'
            return ''
        })

        onMounted(function() { nextTick(function() { name_ref.value && name_ref.value.focus() }) })

        async function submit() {
            if (!name.value || busy.value) return
            busy.value = true
            err.value  = ''
            var res = await apiFetch('/api/tags/', 'POST', {
                name:        name.value,
                description: description.value,
                color:       color.value,
                icon:        icon.value,
                is_public:   is_public.value,
                source:      'custom',
            })
            busy.value = false
            if (!res.ok) {
                var d = await res.json().catch(function() { return {} })
                err.value = d.message || 'Error creating tag'
                return
            }
            var data = await res.json()
            create_message('Tag created', TOAST.SUCCESS)
            emit('created', data.tag)
        }

        return { name_ref, busy, err, name, description, color, icon, is_public, name_hint, submit }
    },
}

/*───────────────────────────────────────────────────────────
  TagCreateVulnerability
───────────────────────────────────────────────────────────*/
const TagCreateVulnerability = {
    name: 'TagCreateVulnerability',
    emits: ['created', 'close'],
    delimiters: ['[[', ']]'],
    template: `
<div class="ts-modal-backdrop" @mousedown.self="$emit('close')">
    <div class="ts-modal" role="dialog" aria-modal="true">
        <div class="ts-modal-header">
            <span class="ts-modal-title"><i class="fas fa-bug me-2"></i>New vulnerability tag</span>
            <button class="ts-modal-close" @click="$emit('close')" aria-label="Close">
                <i class="fas fa-xmark"></i>
            </button>
        </div>
        <div class="ts-modal-body">
            <div class="ts-field">
                <label class="ts-label">Identifier <span class="ts-required">*</span></label>
                <input ref="id_ref" v-model.trim="raw_input" class="ts-input ts-input-mono"
                       :class="input_class"
                       placeholder="CVE-2024-12345"
                       @input="on_input" @keydown.enter="submit" />
                <p v-if="raw_input && !is_valid" class="ts-hint ts-hint-error">
                    <i class="fas fa-triangle-exclamation me-1"></i>
                    Unrecognised format. Supported: CVE, GCVE, GHSA, PYSEC, GSD, wid-sec-w, cisco-sa, RHSA, msrc_CVE, CERTFR
                </p>
                <p v-if="normalized" class="ts-hint ts-hint-ok">
                    <i class="fas fa-check me-1"></i>Will be saved as: <code>[[ normalized ]]</code>
                </p>
            </div>
            <div class="ts-field">
                <label class="ts-label">Description <span class="ts-hint-inline">(optional)</span></label>
                <textarea v-model.trim="description" class="ts-input ts-textarea"
                          rows="2" placeholder="Brief description of this vulnerability"></textarea>
            </div>
            <p class="ts-hint ts-hint-formats">
                <i class="fas fa-info-circle me-1"></i>
                Supported: CVE, GCVE, GHSA, PYSEC, GSD, wid-sec-w, cisco-sa, RHSA, msrc_CVE, CERTFR
            </p>
        </div>
        <div class="ts-modal-footer">
            <button class="ts-btn ts-btn-ghost" @click="$emit('close')">Cancel</button>
            <button class="ts-btn ts-btn-danger" :disabled="busy || !is_valid" @click="submit">
                <i v-if="busy" class="fas fa-spinner fa-spin me-1"></i>
                <i v-else class="fas fa-bug me-1"></i>Create
            </button>
        </div>
        <p v-if="err" class="ts-error"><i class="fas fa-triangle-exclamation me-1"></i>[[ err ]]</p>
    </div>
</div>`,
    setup(props, { emit }) {
        const id_ref      = ref(null)
        const raw_input   = ref('')
        const description = ref('')
        const normalized  = ref('')
        const is_valid    = ref(false)
        const busy        = ref(false)
        const err         = ref('')

        const input_class = computed(function() {
            if (!raw_input.value) return ''
            return is_valid.value ? 'ts-input-ok' : 'ts-input-error'
        })

        onMounted(function() { nextTick(function() { id_ref.value && id_ref.value.focus() }) })

        function on_input() {
            var text = raw_input.value
            var result = detectCVE(text)
            if (result.ids.length === 1) {
                is_valid.value   = true
                normalized.value = result.ids[0]
                return
            }
            if (text.length > 3) {
                var n = normalizeCVE(text)
                var r2 = detectCVE(n)
                if (r2.ids.length === 1) {
                    is_valid.value   = true
                    normalized.value = r2.ids[0]
                    return
                }
            }
            is_valid.value   = false
            normalized.value = ''
        }

        async function submit() {
            if (!is_valid.value || busy.value) return
            busy.value = true
            err.value  = ''
            var tag_name = 'vulnerability:' + normalized.value
            var res = await apiFetch('/api/tags/', 'POST', {
                name:        tag_name,
                description: description.value,
                color:       '#dc3545',
                icon:        'fa-bug',
                is_public:   true,
                source:      'vulnerability',
            })
            busy.value = false
            if (!res.ok) {
                var d = await res.json().catch(function() { return {} })
                err.value = d.message || 'Error creating tag'
                return
            }
            var data = await res.json()
            create_message('Vulnerability tag created', TOAST.SUCCESS)
            emit('created', data.tag)
        }

        return { id_ref, raw_input, description, normalized, is_valid, busy, err, input_class, on_input, submit }
    },
}

/*───────────────────────────────────────────────────────────
  TagSelector — main component
───────────────────────────────────────────────────────────*/
const SOURCE_META = {
    custom:        { label: 'Custom',        icon: 'fa-user-tag' },
    taxonomy:      { label: 'Taxonomy',      icon: 'fa-tag'      },
    galaxy:        { label: 'Galaxy',        icon: 'fa-globe'    },
    vulnerability: { label: 'Vulnerability', icon: 'fa-bug'      },
}

const TagSelector = {
    name: 'TagSelector',
    components: { TagPill, TagCreateCustom, TagCreateVulnerability },
    emits: ['update:modelValue'],
    delimiters: ['[[', ']]'],
    props: {
        modelValue:  { type: Array,   default: function() { return [] } },
        sources:     { type: Array,   default: function() { return ['custom', 'taxonomy', 'galaxy', 'vulnerability'] } },
        max:         { type: Number,  default: 0 },
        placeholder: { type: String,  default: 'Search tags…' },
        disabled:    { type: Boolean, default: false },
    },
    template: `
<div class="ts-root" :class="disabled ? 'ts-root--disabled' : ''">

    <div class="ts-selected" v-if="modelValue.length">
        <span v-for="tag in modelValue" :key="tag.id" class="ts-selected-item">
            <tag-pill :tag="tag" size="sm"></tag-pill>
            <button v-if="!disabled" class="ts-remove" @click.stop="remove(tag)">
                <i class="fas fa-xmark"></i>
            </button>
        </span>
    </div>

    <div v-if="!disabled" class="ts-search-bar">
        <div class="ts-search-wrap">
            <i class="fas fa-magnifying-glass ts-search-icon"></i>
            <input
                ref="search_ref"
                v-model="query"
                class="ts-search-input"
                :placeholder="placeholder"
                @focus="open = true"
                @keydown.escape="open = false"
                @keydown.down.prevent="move(1)"
                @keydown.up.prevent="move(-1)"
                @keydown.enter.prevent="selectHighlighted"
                @input="onInput"
            />
            <button v-if="query" class="ts-search-clear" @click="clearQuery">
                <i class="fas fa-xmark"></i>
            </button>
        </div>

        <div class="ts-source-chips">
            <button
                v-for="src in sources"
                :key="src"
                class="ts-source-chip"
                :class="active_source === src ? 'is-active' : ''"
                @click="toggleSource(src)">
                <i :class="'fas ' + getIcon(src)"></i> [[ getLabel(src) ]]
            </button>
            <button
                class="ts-source-chip"
                :class="active_source === null ? 'is-active' : ''"
                @click="clearSource">
                All
            </button>
        </div>
    </div>

    <div v-if="open && !disabled" class="ts-dropdown" ref="dropdown_ref">
        <div v-if="loading" class="ts-dropdown-state">
            <i class="fas fa-spinner fa-spin me-2"></i>Loading...
        </div>
        <div v-else-if="results.length === 0" class="ts-dropdown-state ts-dropdown-empty">
            <i class="fas fa-inbox me-2"></i>No tags found
        </div>
        <template v-else>
            <div
                v-for="(tag, idx) in results"
                :key="tag.id"
                class="ts-dropdown-item"
                :class="rowClass(idx, tag)"
                @mouseenter="highlighted = idx"
                @mousedown.prevent="select(tag)">
                <tag-pill :tag="tag" size="sm"></tag-pill>
                <i v-if="isSelected(tag)" class="fas fa-check ts-dropdown-check"></i>
            </div>
        </template>

        <div class="ts-dropdown-actions">
            <button v-if="canCustom" class="ts-action-btn" @mousedown.prevent="show_custom = true">
                <i class="fas fa-plus"></i> New custom tag
            </button>
            <button v-if="canVuln" class="ts-action-btn ts-action-btn--vuln" @mousedown.prevent="show_vuln = true">
                <i class="fas fa-bug"></i> New vulnerability
            </button>
        </div>
    </div>

    <Teleport to="body">
        <tag-create-custom
            v-if="show_custom"
            @created="onCreated"
            @close="show_custom = false">
        </tag-create-custom>
        <tag-create-vulnerability
            v-if="show_vuln"
            @created="onCreated"
            @close="show_vuln = false">
        </tag-create-vulnerability>
    </Teleport>

</div>`,
    setup(props, { emit }) {
        const search_ref    = ref(null)
        const dropdown_ref  = ref(null)
        const query         = ref('')
        const open          = ref(false)
        const loading       = ref(false)
        const results       = ref([])
        const highlighted   = ref(0)
        const active_source = ref(null)
        const show_custom   = ref(false)
        const show_vuln     = ref(false)
        var   debounce_id   = null

        const canCustom = computed(function() { return props.sources.indexOf('custom') !== -1 })
        const canVuln   = computed(function() { return props.sources.indexOf('vulnerability') !== -1 })

        function getLabel(src) { return (SOURCE_META[src] || {}).label || src }
        function getIcon(src)  { return (SOURCE_META[src] || {}).icon  || 'fa-tag' }

        function isSelected(tag) {
            return props.modelValue.some(function(t) { return t.id === tag.id })
        }

        function rowClass(idx, tag) {
            var cls = []
            if (highlighted.value === idx) cls.push('is-highlighted')
            if (isSelected(tag))           cls.push('is-selected')
            return cls.join(' ')
        }

        async function load() {
            loading.value     = true
            highlighted.value = 0
            var qs = '?search=' + encodeURIComponent(query.value) + '&limit=30'
            if (active_source.value) qs += '&source=' + active_source.value
            var res = await apiFetch('/api/tags/' + qs, 'GET')
            loading.value = false
            if (!res.ok) return
            var d = await res.json()
            var allowed = {}
            props.sources.forEach(function(s) { allowed[s] = true })
            results.value = (d.tags || []).filter(function(t) { return allowed[t.source] })
        }

        function onInput() {
            open.value = true
            clearTimeout(debounce_id)
            debounce_id = setTimeout(load, 250)
        }

        function clearQuery() { query.value = ''; load() }

        function toggleSource(src) {
            active_source.value = active_source.value === src ? null : src
            load()
        }

        function clearSource() { active_source.value = null; load() }

        function select(tag) {
            if (isSelected(tag)) { remove(tag); return }
            if (props.max > 0 && props.modelValue.length >= props.max) {
                create_message('Max ' + props.max + ' tags', TOAST.WARNING)
                return
            }
            emit('update:modelValue', props.modelValue.concat([tag]))
        }

        function remove(tag) {
            emit('update:modelValue', props.modelValue.filter(function(t) { return t.id !== tag.id }))
        }

        function move(dir) {
            var next = highlighted.value + dir
            highlighted.value = Math.max(0, Math.min(results.value.length - 1, next))
        }

        function selectHighlighted() {
            if (results.value[highlighted.value]) select(results.value[highlighted.value])
        }

        function onCreated(tag) {
            show_custom.value = false
            show_vuln.value   = false
            select(tag)
            load()
        }

        function onClickOutside(e) {
            var root = search_ref.value && search_ref.value.closest('.ts-root')
            if (root && !root.contains(e.target)) open.value = false
        }

        onMounted(function() { load(); document.addEventListener('mousedown', onClickOutside) })
        onBeforeUnmount(function() { document.removeEventListener('mousedown', onClickOutside) })

        return {
            search_ref, dropdown_ref, query, open, loading, results, highlighted,
            active_source, show_custom, show_vuln,
            canCustom, canVuln, getLabel, getIcon,
            isSelected, rowClass, load, onInput, clearQuery,
            toggleSource, clearSource, select, remove, move, selectHighlighted, onCreated,
        }
    },
}

export { TagSelector, TagCreateCustom, TagCreateVulnerability, detectCVE }
export default TagSelector
