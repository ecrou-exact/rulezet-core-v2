/**
 * tag-selector.js — Interactive tag picker with inline creation.
 *
 * Exports:
 *   TagSelector (default) — searchable tag picker, v-model: Array of tag objects
 *   TagCreate             — unified create modal (custom or vulnerability)
 *   detectCVE             — CVE identifier detection utility
 *
 * Props (TagSelector):
 *   modelValue  : Array   Selected tag objects (v-model)
 *   sources     : Array   Allowed sources ['custom','taxonomy','galaxy','vulnerability']
 *   max         : Number  Max selectable tags (0 = unlimited)
 *   placeholder : String
 *   disabled    : Boolean
 *
 * API used: GET /api/tags/select  — lightweight search endpoint
 */
import TagPill from '/static/js/components/tag-pill.js'
import { apiFetch, TOAST } from '/static/js/constants.js'
import { create_message }  from '/static/js/toaster.js'

const { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } = Vue

/*───────────────────────────────────────────────────────────
  CVE syntax detection (mirrors detect_cve.py)
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
    const unique = [], seen = {}
    matches.forEach(function(id) { if (!seen[id]) { seen[id] = true; unique.push(id) } })
    unique.sort()
    return { valid: unique.length > 0, ids: unique }
}

function normalizeCVE(raw) {
    return raw.trim().replace(/[\s_]/g, '-').toUpperCase()
}

/*───────────────────────────────────────────────────────────
  TagCreate — unified modal: choose type then fill form
  Emits: created(tag), close
───────────────────────────────────────────────────────────*/
const TagCreate = {
    name: 'TagCreate',
    emits: ['created', 'close'],
    props: {
        initial: { type: String, default: '' },   // '' = show chooser | 'custom' | 'vuln'
    },
    template: `
<div class="ts-modal-backdrop" @mousedown.self="$emit('close')">
  <div class="ts-modal" role="dialog" aria-modal="true">

    <!-- header -->
    <div class="ts-modal-header">
      <span class="ts-modal-title">
        <i v-if="!step" class="fas fa-tag me-2"></i>
        <i v-else-if="step === 'custom'" class="fas fa-user-tag me-2"></i>
        <i v-else class="fas fa-bug me-2"></i>
        {{ step ? (step === 'custom' ? 'New custom tag' : 'New vulnerability tag') : 'New tag' }}
      </span>
      <button class="ts-modal-close" @click="$emit('close')" aria-label="Close">
        <i class="fas fa-xmark"></i>
      </button>
    </div>

    <!-- step 0: choose type -->
    <div v-if="!step" class="ts-modal-body">
      <p class="ts-hint mb-3">What kind of tag do you want to create?</p>
      <div class="ts-type-grid">
        <button class="ts-type-card" @click="step = 'custom'">
          <i class="fas fa-user-tag ts-type-icon"></i>
          <span class="ts-type-label">Custom</span>
          <span class="ts-type-desc">A tag you define with a name, color and icon.</span>
        </button>
        <button class="ts-type-card ts-type-card--vuln" @click="step = 'vuln'">
          <i class="fas fa-bug ts-type-icon"></i>
          <span class="ts-type-label">Vulnerability</span>
          <span class="ts-type-desc">A CVE, GHSA, PYSEC or other identifier.</span>
        </button>
      </div>
    </div>

    <!-- step: custom form -->
    <div v-else-if="step === 'custom'" class="ts-modal-body">
      <div class="ts-field">
        <label class="ts-label">Name <span class="ts-required">*</span></label>
        <input ref="name_ref" v-model.trim="c_name" class="ts-input"
               placeholder="namespace:value  or  simple-name"
               @keydown.enter="submit_custom" />
        <p v-if="c_name_hint" class="ts-hint">{{ c_name_hint }}</p>
      </div>
      <div class="ts-field">
        <label class="ts-label">Description</label>
        <textarea v-model.trim="c_desc" class="ts-input ts-textarea"
                  rows="2" placeholder="Optional description"></textarea>
      </div>
      <div class="ts-field-row">
        <div class="ts-field">
          <label class="ts-label">Color</label>
          <div class="ts-color-row">
            <input type="color" v-model="c_color" class="ts-color-input" />
            <span class="ts-color-hex">{{ c_color }}</span>
          </div>
        </div>
        <div class="ts-field">
          <label class="ts-label">Icon <span class="ts-hint-inline">FA class</span></label>
          <input v-model.trim="c_icon" class="ts-input" placeholder="fa-tag" />
        </div>
      </div>
    </div>

    <!-- step: vulnerability form -->
    <div v-else class="ts-modal-body">
      <div class="ts-field">
        <label class="ts-label">Identifier <span class="ts-required">*</span></label>
        <input ref="vuln_ref" v-model.trim="v_raw" class="ts-input ts-input-mono"
               :class="v_input_class"
               placeholder="CVE-2024-12345"
               @input="on_vuln_input" @keydown.enter="submit_vuln" />
        <p v-if="v_raw && !v_valid" class="ts-hint ts-hint-error">
          <i class="fas fa-triangle-exclamation me-1"></i>
          Unrecognised format. Supported: CVE, GCVE, GHSA, PYSEC, GSD, wid-sec-w, cisco-sa, RHSA, msrc_CVE, CERTFR
        </p>
        <p v-if="v_norm" class="ts-hint ts-hint-ok">
          <i class="fas fa-check me-1"></i>Will be saved as: <code>{{ v_norm }}</code>
        </p>
      </div>
      <div class="ts-field">
        <label class="ts-label">Description <span class="ts-hint-inline">optional</span></label>
        <textarea v-model.trim="v_desc" class="ts-input ts-textarea"
                  rows="2" placeholder="Brief description"></textarea>
      </div>
      <p class="ts-hint ts-hint-formats">
        <i class="fas fa-info-circle me-1"></i>
        Supported: CVE, GCVE, GHSA, PYSEC, GSD, wid-sec-w, cisco-sa, RHSA, msrc_CVE, CERTFR
      </p>
    </div>

    <!-- footer -->
    <div class="ts-modal-footer">
      <button class="ts-btn ts-btn-ghost" @click="(step && !initial) ? step = '' : $emit('close')">
        {{ (step && !initial) ? 'Back' : 'Cancel' }}
      </button>
      <button v-if="step === 'custom'"
              class="ts-btn ts-btn-primary"
              :disabled="busy || !c_name"
              @click="submit_custom">
        <i v-if="busy" class="fas fa-spinner fa-spin me-1"></i>
        <i v-else class="fas fa-plus me-1"></i>Create tag
      </button>
      <button v-else-if="step === 'vuln'"
              class="ts-btn ts-btn-danger"
              :disabled="busy || !v_valid"
              @click="submit_vuln">
        <i v-if="busy" class="fas fa-spinner fa-spin me-1"></i>
        <i v-else class="fas fa-bug me-1"></i>Create
      </button>
    </div>

    <p v-if="err" class="ts-error">
      <i class="fas fa-triangle-exclamation me-1"></i>{{ err }}
    </p>

  </div>
</div>`,
    setup(props, { emit }) {
        const step     = ref(props.initial || '')   // '' | 'custom' | 'vuln'
        const busy     = ref(false)
        const err      = ref('')
        const name_ref = ref(null)
        const vuln_ref = ref(null)

        // custom form
        const c_name  = ref('')
        const c_desc  = ref('')
        const c_color = ref('#6c757d')
        const c_icon  = ref('fa-tag')

        const c_name_hint = computed(function() {
            if (!c_name.value) return ''
            var idx = c_name.value.indexOf(':')
            return idx !== -1 ? 'Namespace: "' + c_name.value.slice(0, idx) + '"' : ''
        })

        // vuln form
        const v_raw   = ref('')
        const v_desc  = ref('')
        const v_norm  = ref('')
        const v_valid = ref(false)

        const v_input_class = computed(function() {
            if (!v_raw.value) return ''
            return v_valid.value ? 'ts-input-ok' : 'ts-input-error'
        })

        watch(step, function(val) {
            err.value = ''
            nextTick(function() {
                if (val === 'custom' && name_ref.value) name_ref.value.focus()
                if (val === 'vuln'   && vuln_ref.value) vuln_ref.value.focus()
            })
        })

        function on_vuln_input() {
            var text = v_raw.value
            var r = detectCVE(text)
            if (r.ids.length === 1) { v_valid.value = true; v_norm.value = r.ids[0]; return }
            if (text.length > 3) {
                var r2 = detectCVE(normalizeCVE(text))
                if (r2.ids.length === 1) { v_valid.value = true; v_norm.value = r2.ids[0]; return }
            }
            v_valid.value = false
            v_norm.value  = ''
        }

        async function submit_custom() {
            if (!c_name.value || busy.value) return
            busy.value = true; err.value = ''
            var res = await apiFetch('/api/tags/', 'POST', {
                name: c_name.value, description: c_desc.value,
                color: c_color.value, icon: c_icon.value,
                is_public: false, source: 'custom',
            })
            busy.value = false
            if (!res.ok) {
                var d = await res.json().catch(function() { return {} })
                err.value = d.message || 'Error creating tag'; return
            }
            var data = await res.json()
            create_message('Tag created', TOAST.SUCCESS)
            emit('created', data)
        }

        async function submit_vuln() {
            if (!v_valid.value || busy.value) return
            busy.value = true; err.value = ''
            var res = await apiFetch('/api/tags/', 'POST', {
                name: 'vulnerability:' + v_norm.value,
                description: v_desc.value,
                color: '#dc3545', icon: 'fa-bug',
                is_public: true, source: 'vulnerability',
            })
            busy.value = false
            if (!res.ok) {
                var d = await res.json().catch(function() { return {} })
                err.value = d.message || 'Error creating tag'; return
            }
            var data = await res.json()
            create_message('Vulnerability tag created', TOAST.SUCCESS)
            emit('created', data)
        }

        return {
            step, busy, err, name_ref, vuln_ref,
            c_name, c_desc, c_color, c_icon, c_name_hint,
            v_raw, v_desc, v_norm, v_valid, v_input_class,
            on_vuln_input, submit_custom, submit_vuln,
        }
    },
}

/*───────────────────────────────────────────────────────────
  TagSelector — main picker component
───────────────────────────────────────────────────────────*/
const SOURCE_META = {
    custom:        { label: 'Custom',        icon: 'fa-user-tag' },
    taxonomy:      { label: 'Taxonomy',      icon: 'fa-tag'      },
    galaxy:        { label: 'Galaxy',        icon: 'fa-globe'    },
    vulnerability: { label: 'Vulnerability', icon: 'fa-bug'      },
}

const TagSelector = {
    name: 'TagSelector',
    components: { TagPill, TagCreate },
    emits: ['update:modelValue'],
    props: {
        modelValue:  { type: Array,   default: function() { return [] } },
        sources:     { type: Array,   default: function() { return ['custom', 'taxonomy', 'galaxy', 'vulnerability'] } },
        max:         { type: Number,  default: 0 },
        placeholder: { type: String,  default: 'Search tags…' },
        disabled:    { type: Boolean, default: false },
        createType:  { type: String,  default: '' },  // '' = chooser | 'custom' | 'vuln'
    },
    template: `
<div class="ts-root" :class="disabled ? 'ts-root--disabled' : ''">

    <!-- Selected tags + create button -->
    <div class="ts-selected">
        <span v-if="!modelValue.length && disabled" class="ts-selected-empty">No tags</span>
        <span v-else-if="!modelValue.length" class="ts-selected-empty">No tags selected</span>
        <span v-for="tag in modelValue" :key="tag.id" class="ts-selected-item">
            <tag-pill :tag="tag" size="sm"></tag-pill>
            <button v-if="!disabled" class="ts-remove" @click.stop="remove(tag)" type="button">
                <i class="fas fa-xmark"></i>
            </button>
        </span>
        <button v-if="!disabled" class="ts-selected-add" @mousedown.prevent="show_create = true" type="button" title="Create new tag">
            <i class="fas fa-plus"></i>
        </button>
    </div>

    <div v-if="!disabled" class="ts-search-bar">
        <!-- Search row: input + create button -->
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
            <button v-if="query" class="ts-search-clear" @click="clearQuery" type="button">
                <i class="fas fa-xmark"></i>
            </button>
            <button class="ts-create-btn" @mousedown.prevent="show_create = true" type="button" title="Create new tag">
                <i class="fas fa-plus"></i>
            </button>
        </div>

        <!-- Source filter chips -->
        <div class="ts-source-chips">
            <button
                v-for="src in sources"
                :key="src"
                class="ts-source-chip"
                :class="active_source === src ? 'is-active' : ''"
                @click="toggleSource(src)"
                type="button">
                <i :class="'fas ' + getIcon(src)"></i> {{ getLabel(src) }}
            </button>
            <button
                class="ts-source-chip"
                :class="active_source === null ? 'is-active' : ''"
                @click="clearSource"
                type="button">
                All
            </button>
        </div>
    </div>

    <!-- Dropdown results -->
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
    </div>

    <!-- Create modal -->
    <Teleport to="body">
        <tag-create
            v-if="show_create"
            :initial="createType"
            @created="onCreated"
            @close="show_create = false">
        </tag-create>
    </Teleport>

</div>`,
    setup(props, { emit }) {
        const search_ref   = ref(null)
        const dropdown_ref = ref(null)
        const query        = ref('')
        const open         = ref(false)
        const loading      = ref(false)
        const results      = ref([])
        const highlighted  = ref(0)
        const active_source = ref(null)
        const show_create  = ref(false)
        var   debounce_id  = null

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

            // Build sources param: use active_source filter if set,
            // otherwise send the full allowed list from props
            var src_param = active_source.value
                ? active_source.value
                : props.sources.join(',')

            var qs = '?limit=40'
                + '&sources=' + encodeURIComponent(src_param)
            if (query.value) qs += '&search=' + encodeURIComponent(query.value)

            var res = await apiFetch('/api/tags/select' + qs, 'GET')
            loading.value = false
            if (!res.ok) return
            var d = await res.json()
            results.value = d.tags || []
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
            show_create.value = false
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
            active_source, show_create,
            getLabel, getIcon, isSelected, rowClass,
            load, onInput, clearQuery, toggleSource, clearSource,
            select, remove, move, selectHighlighted, onCreated,
        }
    },
}

export { TagSelector, TagCreate, detectCVE }
export default TagSelector
