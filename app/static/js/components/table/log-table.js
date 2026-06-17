/**
 * log-table.js — Specialised table component for application logs.
 *
 * Props:
 *   fetchUrl   String  (required) — API URL, e.g. "/api/log/"
 *   canDelete  Boolean (default: false) — show delete controls
 *
 * Events:
 *   delete(log)           — single-row delete requested
 *   bulk-delete(uuids[])  — bulk delete requested
 *
 * Exposed:
 *   fetchData()           — re-fetch current page (callable via template ref)
 */

import { apiFetch } from '/static/js/constants.js'
import Pagination   from '/static/js/components/pagination/pagination.js'

const { ref, computed, watch, onMounted } = Vue

// ── Static data ──────────────────────────────────────────────────────────────

const CATEGORIES = [
    { value: '',         label: 'All',      icon: 'fa-list'          },
    { value: 'user',     label: 'User',     icon: 'fa-user'          },
    { value: 'system',   label: 'System',   icon: 'fa-gear'          },
    { value: 'security', label: 'Security', icon: 'fa-shield-halved' },
    { value: 'admin',    label: 'Admin',    icon: 'fa-crown'         },
    { value: 'api',      label: 'API',      icon: 'fa-code'          },
]

const LEVELS = [
    { value: '',        label: 'All'     },
    { value: 'info',    label: 'Info'    },
    { value: 'success', label: 'Success' },
    { value: 'warning', label: 'Warning' },
    { value: 'error',   label: 'Error'   },
]

// ── Helpers ──────────────────────────────────────────────────────────────────

function getCategoryIcon(cat) {
    const found = CATEGORIES.find(c => c.value === cat)
    return found ? found.icon : 'fa-circle'
}

function getInitials(name) {
    if (!name) return '?'
    const parts = name.trim().split(/\s+/)
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

function formatRelative(val) {
    if (!val) return '—'
    const now   = Date.now()
    const then  = new Date(val).getTime()
    const diff  = Math.floor((now - then) / 1000)

    if (diff < 60)   return `${diff}s ago`
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
    return `${Math.floor(diff / 86400)}d ago`
}

function formatFull(val) {
    if (!val) return ''
    return new Date(val).toLocaleString(undefined, {
        year:   'numeric', month:  'short', day:    'numeric',
        hour:   '2-digit', minute: '2-digit', second: '2-digit',
    })
}

// ── Component ─────────────────────────────────────────────────────────────────

export default {
    name: 'LogTable',
    components: { Pagination },

    props: {
        fetchUrl:  { type: String,  required: true },
        canDelete: { type: Boolean, default: false },
    },

    emits: ['delete', 'bulk-delete'],

    setup(props, { emit, expose }) {

        // ── State ────────────────────────────────────────────────────────────
        const items         = ref([])
        const total         = ref(0)
        const total_pages   = ref(1)
        const loading       = ref(false)
        const page          = ref(1)
        const per_page      = ref(25)
        const sort_key      = ref('created_at')
        const sort_dir      = ref('desc')
        const search        = ref('')
        const active_cat    = ref('')
        const active_level  = ref('')
        const expanded_id   = ref(null)
        const selected      = ref(new Set())   // Set of uuids

        // ── Fetch ────────────────────────────────────────────────────────────
        async function fetchData() {
            loading.value = true
            try {
                const params = new URLSearchParams({
                    page:     page.value,
                    per_page: per_page.value,
                    sort:     sort_key.value,
                    dir:      sort_dir.value,
                })
                if (search.value)       params.set('search',   search.value)
                if (active_cat.value)   params.set('category', active_cat.value)
                if (active_level.value) params.set('level',    active_level.value)

                const res  = await apiFetch(`${props.fetchUrl}?${params}`)
                const data = await res.json()

                items.value       = data.items       || []
                total.value       = data.total       || 0
                total_pages.value = data.total_pages || 1
                // Clamp selected to items still present
                const currentUuids = new Set(items.value.map(i => i.uuid))
                for (const uuid of [...selected.value]) {
                    if (!currentUuids.has(uuid)) selected.value.delete(uuid)
                }
            } catch (e) {
                // silently keep previous state
            } finally {
                loading.value = false
            }
        }

        // ── Sort ─────────────────────────────────────────────────────────────
        function toggleSort(key) {
            if (sort_key.value === key) {
                sort_dir.value = sort_dir.value === 'asc' ? 'desc' : 'asc'
            } else {
                sort_key.value = key
                sort_dir.value = 'desc'
            }
            page.value = 1
            fetchData()
        }

        function sortIcon(key) {
            if (sort_key.value !== key) return 'fa-sort'
            return sort_dir.value === 'asc' ? 'fa-sort-up' : 'fa-sort-down'
        }

        // ── Filters ──────────────────────────────────────────────────────────
        let _searchTimer = null
        function onSearch() {
            clearTimeout(_searchTimer)
            _searchTimer = setTimeout(() => {
                page.value = 1
                fetchData()
            }, 300)
        }

        function clearSearch() {
            search.value = ''
            page.value = 1
            fetchData()
        }

        function setCategory(val) {
            active_cat.value = val
            page.value = 1
            fetchData()
        }

        function setLevel(val) {
            active_level.value = val
            page.value = 1
            fetchData()
        }

        function onPerPageChange() {
            page.value = 1
            fetchData()
        }

        // ── Pagination ───────────────────────────────────────────────────────
        function handlePageChange(p) {
            page.value = p
            fetchData()
        }

        // ── Expand ───────────────────────────────────────────────────────────
        function toggleExpand(uuid) {
            expanded_id.value = expanded_id.value === uuid ? null : uuid
        }

        // ── Selection ────────────────────────────────────────────────────────
        const all_page_selected = computed(() => {
            if (!items.value.length) return false
            return items.value.every(i => selected.value.has(i.uuid))
        })

        function toggleAll() {
            if (all_page_selected.value) {
                items.value.forEach(i => selected.value.delete(i.uuid))
            } else {
                items.value.forEach(i => selected.value.add(i.uuid))
            }
            // Trigger reactivity on Set
            selected.value = new Set(selected.value)
        }

        function toggleOne(uuid) {
            if (selected.value.has(uuid)) {
                selected.value.delete(uuid)
            } else {
                selected.value.add(uuid)
            }
            selected.value = new Set(selected.value)
        }

        function clearSelection() {
            selected.value = new Set()
        }

        // ── Delete single ────────────────────────────────────────────────────
        function requestDelete(log) {
            emit('delete', log)
        }

        // ── Bulk delete ──────────────────────────────────────────────────────
        function requestBulkDelete() {
            emit('bulk-delete', [...selected.value])
        }

        // ── Lifecycle ────────────────────────────────────────────────────────
        onMounted(() => fetchData())

        // ── Expose ───────────────────────────────────────────────────────────
        expose({ fetchData })

        // ── Template ─────────────────────────────────────────────────────────
        return {
            // state
            items, total, total_pages, loading, page, per_page,
            sort_key, sort_dir, search, active_cat, active_level,
            expanded_id, selected, all_page_selected,
            // data
            CATEGORIES, LEVELS,
            // helpers
            getCategoryIcon, getInitials, formatRelative, formatFull,
            // methods
            fetchData, toggleSort, sortIcon,
            onSearch, clearSearch, setCategory, setLevel, onPerPageChange,
            handlePageChange, toggleExpand,
            toggleAll, toggleOne, clearSelection,
            requestDelete, requestBulkDelete,
        }
    },

    template: `
<div class="lt-wrapper">

    <!-- Loading overlay -->
    <div v-if="loading" class="lt-loading-overlay">
        <div class="lt-spinner"></div>
    </div>

    <!-- Filters bar -->
    <div class="lt-filters">

        <!-- Search -->
        <div class="lt-search">
            <i class="fas fa-magnifying-glass lt-search-icon"></i>
            <input
                class="lt-search-input"
                type="text"
                placeholder="Search title, action…"
                v-model="search"
                @input="onSearch"
            />
            <button v-if="search" class="lt-search-clear" @click="clearSearch" title="Clear search">
                <i class="fas fa-xmark"></i>
            </button>
        </div>

        <div class="lt-filter-sep d-none d-sm-block"></div>

        <!-- Category pills -->
        <div class="lt-filter-group">
            <button
                v-for="cat in CATEGORIES"
                :key="cat.value"
                class="lt-pill"
                :class="{ active: active_cat === cat.value }"
                @click="setCategory(cat.value)">
                <i :class="['fas', cat.icon]" style="font-size:.65rem;"></i>
                {{ cat.label }}
            </button>
        </div>

        <div class="lt-filter-sep d-none d-sm-block"></div>

        <!-- Level pills -->
        <div class="lt-filter-group">
            <button
                v-for="lv in LEVELS"
                :key="lv.value"
                class="lt-level-pill"
                :class="['lt-level-pill--' + (lv.value || 'all'), { active: active_level === lv.value }]"
                @click="setLevel(lv.value)">
                {{ lv.label }}
            </button>
        </div>

    </div>

    <!-- Bulk action bar -->
    <div v-if="selected.size > 0" class="lt-bulk-bar">
        <span class="lt-bulk-bar-count">{{ selected.size }} selected</span>
        <div class="lt-bulk-bar-actions">
            <button v-if="canDelete" class="lt-bulk-btn lt-bulk-btn--danger" @click="requestBulkDelete">
                <i class="fas fa-trash-can"></i> Delete selected
            </button>
            <button class="lt-bulk-btn lt-bulk-btn--clear" @click="clearSelection">
                <i class="fas fa-xmark"></i> Clear
            </button>
        </div>
    </div>

    <!-- Table -->
    <div class="lt-table-wrap">
        <table class="lt-table">
            <thead class="lt-thead">
                <tr>
                    <th class="lt-th lt-th--check" v-if="canDelete">
                        <input type="checkbox" class="lt-checkbox"
                               :checked="all_page_selected"
                               @change="toggleAll" />
                    </th>
                    <th class="lt-th lt-th--level"></th>
                    <th class="lt-th lt-th--cat lt-th--sortable"
                        :class="{ 'lt-th--sorted': sort_key === 'category' }"
                        @click="toggleSort('category')">
                        <span class="lt-th-inner">
                            Category
                            <i :class="['fas', sortIcon('category'), 'lt-th-sort-icon']"></i>
                        </span>
                    </th>
                    <th class="lt-th lt-th--event lt-th--sortable"
                        :class="{ 'lt-th--sorted': sort_key === 'action' }"
                        @click="toggleSort('action')">
                        <span class="lt-th-inner">
                            Event
                            <i :class="['fas', sortIcon('action'), 'lt-th-sort-icon']"></i>
                        </span>
                    </th>
                    <th class="lt-th lt-th--actor">Actor</th>
                    <th class="lt-th lt-th--date lt-th--sortable"
                        :class="{ 'lt-th--sorted': sort_key === 'created_at' }"
                        @click="toggleSort('created_at')">
                        <span class="lt-th-inner">
                            Date
                            <i :class="['fas', sortIcon('created_at'), 'lt-th-sort-icon']"></i>
                        </span>
                    </th>
                    <th class="lt-th lt-th--ua lt-td--ua">Agent</th>
                    <th class="lt-th lt-th--expand"></th>
                </tr>
            </thead>

            <tbody>

                <!-- Empty state -->
                <tr v-if="!items.length && !loading">
                    <td :colspan="canDelete ? 8 : 7" class="lt-empty">
                        <i class="fas fa-scroll lt-empty-icon"></i>
                        <div class="lt-empty-text">No logs found</div>
                    </td>
                </tr>

                <template v-for="log in items" :key="log.uuid">

                    <!-- Main row -->
                    <tr class="lt-row"
                        :class="{
                            'lt-row--selected': selected.has(log.uuid),
                            'lt-row--error':    log.level === 'error',
                            'lt-row--warning':  log.level === 'warning',
                        }">

                        <!-- Checkbox -->
                        <td class="lt-td lt-td--check" v-if="canDelete">
                            <input type="checkbox" class="lt-checkbox"
                                   :checked="selected.has(log.uuid)"
                                   @change="toggleOne(log.uuid)" />
                        </td>

                        <!-- Level bar -->
                        <td class="lt-td lt-td--level" style="padding:0;width:4px;">
                            <span :class="['lt-level-bar', 'lt-level-bar--' + log.level]"></span>
                        </td>

                        <!-- Category -->
                        <td class="lt-td">
                            <span :class="['lt-category-badge', 'lt-category-badge--' + log.category]">
                                <i :class="['fas', getCategoryIcon(log.category)]" style="font-size:.6rem;"></i>
                                {{ log.category }}
                            </span>
                        </td>

                        <!-- Event (title + action) -->
                        <td class="lt-td">
                            <span class="lt-event-title" :title="log.title">{{ log.title }}</span>
                            <span class="lt-event-action">{{ log.action }}</span>
                        </td>

                        <!-- Actor -->
                        <td class="lt-td lt-td--actor">
                            <div v-if="log.actor_name" class="lt-actor">
                                <div class="lt-actor-avatar">
                                    <img v-if="log.actor_avatar"
                                         :src="'/static/uploads/avatars/' + log.actor_avatar"
                                         class="lt-actor-avatar-img"
                                         :alt="log.actor_name" />
                                    <template v-else>{{ getInitials(log.actor_name) }}</template>
                                </div>
                                <span class="lt-actor-name" :title="log.actor_name">{{ log.actor_name }}</span>
                            </div>
                            <span v-else class="lt-actor-none">System</span>
                        </td>

                        <!-- Date -->
                        <td class="lt-td lt-td--date" :title="formatFull(log.created_at)">
                            {{ formatRelative(log.created_at) }}
                        </td>

                        <!-- User agent -->
                        <td class="lt-td lt-td--ua">
                            <span class="lt-ua-text" :title="log.user_agent">
                                {{ log.user_agent || '—' }}
                            </span>
                        </td>

                        <!-- Expand / delete -->
                        <td class="lt-td" style="text-align:center;padding:.4rem .3rem;">
                            <button v-if="canDelete"
                                    class="lt-delete-btn"
                                    @click.stop="requestDelete(log)"
                                    title="Delete">
                                <i class="fas fa-trash-can"></i>
                            </button>
                            <button class="lt-expand-btn"
                                    :class="{ active: expanded_id === log.uuid }"
                                    @click="toggleExpand(log.uuid)"
                                    :title="expanded_id === log.uuid ? 'Collapse' : 'Expand'">
                                <i class="fas fa-chevron-right"></i>
                            </button>
                        </td>

                    </tr>

                    <!-- Expanded detail row -->
                    <tr v-if="expanded_id === log.uuid" class="lt-row-expand">
                        <td :colspan="canDelete ? 8 : 7" class="lt-expand-cell">
                            <div class="lt-expand-content">

                                <div class="lt-expand-grid">
                                    <div class="lt-expand-field">
                                        <span class="lt-expand-label">UUID</span>
                                        <span class="lt-expand-value lt-mono">{{ log.uuid }}</span>
                                    </div>
                                    <div class="lt-expand-field" v-if="log.object_type">
                                        <span class="lt-expand-label">Object type</span>
                                        <span class="lt-expand-value lt-mono">{{ log.object_type }}</span>
                                    </div>
                                    <div class="lt-expand-field" v-if="log.object_id">
                                        <span class="lt-expand-label">Object ID</span>
                                        <span class="lt-expand-value lt-mono">{{ log.object_id }}</span>
                                    </div>
                                    <div class="lt-expand-field" v-if="log.ip_address">
                                        <span class="lt-expand-label">IP Address</span>
                                        <span class="lt-expand-value lt-mono">{{ log.ip_address }}</span>
                                    </div>
                                    <div class="lt-expand-field">
                                        <span class="lt-expand-label">Level</span>
                                        <span class="lt-expand-value" style="text-transform:capitalize;">{{ log.level }}</span>
                                    </div>
                                    <div class="lt-expand-field">
                                        <span class="lt-expand-label">Visibility</span>
                                        <span class="lt-expand-value">{{ log.is_public ? 'Public' : 'Admin only' }}</span>
                                    </div>
                                    <div class="lt-expand-field">
                                        <span class="lt-expand-label">Created at</span>
                                        <span class="lt-expand-value lt-mono">{{ formatFull(log.created_at) }}</span>
                                    </div>
                                </div>

                                <div v-if="log.description" class="lt-expand-field">
                                    <span class="lt-expand-label">Description</span>
                                    <p class="lt-expand-desc">{{ log.description }}</p>
                                </div>

                                <div v-if="log.user_agent" class="lt-expand-field">
                                    <span class="lt-expand-label">User agent</span>
                                    <p class="lt-expand-desc lt-mono" style="font-size:.72rem;">{{ log.user_agent }}</p>
                                </div>

                                <div v-if="log.meta" class="lt-expand-field">
                                    <span class="lt-expand-label">Meta</span>
                                    <pre class="lt-meta-pre">{{ JSON.stringify(log.meta, null, 2) }}</pre>
                                </div>

                            </div>
                        </td>
                    </tr>

                </template>

            </tbody>
        </table>
    </div>

    <!-- Footer -->
    <div class="lt-footer">
        <span class="lt-info">
            {{ total }} log{{ total !== 1 ? 's' : '' }}
            <template v-if="total > per_page">
                — page {{ page }} / {{ total_pages }}
            </template>
        </span>
        <div class="lt-footer-right">
            <div class="lt-per-page">
                <span>Per page</span>
                <select class="lt-per-page-select" v-model.number="per_page" @change="onPerPageChange">
                    <option>10</option>
                    <option>25</option>
                    <option>50</option>
                    <option>100</option>
                </select>
            </div>
            <Pagination
                :current-page="page"
                :total-pages="total_pages"
                @change-page="handlePageChange" />
        </div>
    </div>

</div>
    `,
}
