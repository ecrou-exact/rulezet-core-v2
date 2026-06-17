/**
 * tag-pill.js — Split-pill tag display component.
 *
 * Props:
 *   tag  : Object  { name, color, icon, source, namespace, is_active, description, meta }
 *   size : String  'sm' | '' | 'lg'
 *
 * Tooltip uses position:fixed (calculated on mouseenter) to escape
 * any parent overflow:hidden (e.g. data-table cells).
 */
import { mapIcon, truncateText } from './tag-utils.js'
const { computed, ref } = Vue

function yiqTextColor(hex) {
    if (!hex) return '#ffffff'
    const h = hex.replace('#', '')
    if (h.length === 3) {
        const r = parseInt(h[0] + h[0], 16)
        const g = parseInt(h[1] + h[1], 16)
        const b = parseInt(h[2] + h[2], 16)
        return (r * 299 + g * 587 + b * 114) / 1000 >= 145 ? '#1a1a1a' : '#ffffff'
    }
    if (h.length >= 6) {
        const r = parseInt(h.slice(0, 2), 16)
        const g = parseInt(h.slice(2, 4), 16)
        const b = parseInt(h.slice(4, 6), 16)
        return (r * 299 + g * 587 + b * 114) / 1000 >= 145 ? '#1a1a1a' : '#ffffff'
    }
    return '#ffffff'
}

function hslTextColor(hsl) {
    const m = hsl.match(/hsl\(\d+\.?\d*,\s*\d+%,\s*(\d+)%\)/)
    if (m) return parseInt(m[1]) >= 65 ? '#1a1a1a' : '#ffffff'
    return '#ffffff'
}

function resolveTextColor(color) {
    if (!color) return '#ffffff'
    if (color.startsWith('#')) return yiqTextColor(color)
    if (color.startsWith('hsl')) return hslTextColor(color)
    return '#ffffff'
}

function parseTagDisplay(tag) {
    if (!tag) return { left: '', right: '' }
    const name = tag.name || ''
    const colonIdx = name.indexOf(':')
    if (colonIdx === -1) return { left: tag.source || 'tag', right: name }
    const ns    = name.slice(0, colonIdx)
    const rest  = name.slice(colonIdx + 1)
    const eqIdx = rest.indexOf('="')
    const label = eqIdx !== -1 ? rest.slice(eqIdx + 2).replace(/"$/, '') : rest
    return { left: ns, right: label }
}

const TagPill = {
    name: 'TagPill',
    template: `
        <span class="tag-pill-wrapper" ref="wrapper_ref"
            @mouseenter="onEnter" @mouseleave="show_tooltip = false">

            <span
                class="tag-pill"
                :class="[size ? 'tag-pill--' + size : '', !tag.is_active ? 'tag-pill--inactive' : '']"
            >
                <span class="tag-pill-left">
                    <span v-html="iconHtml"></span>
                    {{ display.left }}
                </span>
                <span class="tag-pill-right" :style="rightStyle">
                    <span>{{ display.right }}</span>
                </span>
            </span>

            <Teleport to="body">
                <div v-if="show_tooltip"
                    class="tag-pill-tooltip"
                    :class="'tag-pill-tooltip--' + tooltip_pos"
                    :style="tooltip_style">

                    <div class="tag-pill-tooltip-header">
                        <span v-html="iconHtml"></span>
                        <span class="tag-pill-tooltip-name">{{ tag.name }}</span>
                    </div>

                    <p v-if="tag.description" class="tag-pill-tooltip-desc">{{ truncDesc }}</p>

                    <div v-if="galaxy_details.length" class="tag-pill-tooltip-galaxy">
                        <div v-for="row in galaxy_details" :key="row.label" class="tag-pill-tooltip-meta-row">
                            <span class="tag-pill-tooltip-meta-label">{{ row.label }}</span>
                            <span class="tag-pill-tooltip-meta-value">{{ row.value }}</span>
                        </div>
                    </div>

                    <div class="tag-pill-tooltip-footer">
                        <span class="tag-pill-tooltip-badge tag-pill-tooltip-badge--source">{{ tag.source }}</span>
                        <span v-if="tag.namespace" class="tag-pill-tooltip-badge tag-pill-tooltip-badge--ns">{{ tag.namespace }}</span>
                    </div>
                </div>
            </Teleport>
        </span>
    `,
    props: {
        tag:  { type: Object, required: true },
        size: { type: String, default: '' },
    },
    setup(props) {
        const wrapper_ref   = ref(null)
        const show_tooltip  = ref(false)
        const tooltip_pos   = ref('above')
        const tooltip_style = ref({})

        function onEnter() {
            const el = wrapper_ref.value
            if (!el) return
            const rect = el.getBoundingClientRect()
            const cx = rect.left + rect.width / 2

            if (rect.top > 220) {
                tooltip_pos.value   = 'above'
                tooltip_style.value = {
                    position:  'fixed',
                    left:      cx + 'px',
                    top:       (rect.top - 10) + 'px',
                    transform: 'translate(-50%, -100%)',
                    zIndex:    9999,
                }
            } else {
                tooltip_pos.value   = 'below'
                tooltip_style.value = {
                    position:  'fixed',
                    left:      cx + 'px',
                    top:       (rect.bottom + 10) + 'px',
                    transform: 'translateX(-50%)',
                    zIndex:    9999,
                }
            }
            show_tooltip.value = true
        }

        const display   = computed(() => parseTagDisplay(props.tag))
        const truncDesc = computed(() => truncateText(props.tag.description, 200))

        const iconHtml = computed(() => {
            const src = props.tag.source || 'custom'
            const defaults = {
                custom:        'fa-user-tag',
                taxonomy:      'fa-tag',
                galaxy:        'fa-globe',
                vulnerability: 'fa-bug',
            }
            return mapIcon(props.tag.icon || defaults[src] || 'fa-tag')
        })

        const rightStyle = computed(() => {
            const color = props.tag.color || '#6c757d'
            return {
                backgroundColor: color,
                color:           resolveTextColor(color),
            }
        })

        const galaxy_details = computed(() => {
            if (props.tag.source !== 'galaxy') return []
            const gm = props.tag.meta?.galaxy_meta || {}
            const rows = []
            if (gm.country)
                rows.push({ label: 'Country', value: gm.country })
            if (gm['cfr-suspected-state-sponsor'])
                rows.push({ label: 'Sponsor', value: gm['cfr-suspected-state-sponsor'] })
            if (gm.synonyms?.length)
                rows.push({ label: 'Aliases', value: gm.synonyms.slice(0, 5).join(', ') })
            if (gm['cfr-target-category']?.length)
                rows.push({ label: 'Targets', value: gm['cfr-target-category'].slice(0, 3).join(', ') })
            if (gm['targeted-sector']?.length)
                rows.push({ label: 'Sectors', value: gm['targeted-sector'].slice(0, 3).join(', ') })
            if (gm.refs?.length)
                rows.push({ label: 'References', value: gm.refs.length + (gm.refs.length > 1 ? ' links' : ' link') })
            return rows
        })

        return {
            wrapper_ref, show_tooltip, tooltip_pos, tooltip_style, onEnter,
            display, truncDesc, iconHtml, rightStyle, galaxy_details,
        }
    },
}

export { TagPill, yiqTextColor, parseTagDisplay }
export default TagPill
