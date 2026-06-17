/**
 * stat-card.js — KPI metric card with optional trend indicator.
 *
 * Props:
 *   value      String|Number  Main metric value (displayed large)
 *   label      String         Card title / metric name
 *   icon       String         FontAwesome class — e.g. 'fa-users'
 *   color      String         Color key: brand | blue | green | red | orange | purple | gray
 *   unit       String         Unit appended to value — e.g. '%', 'ms', '€'
 *   trend      Number|null    Change vs previous period. Positive = up (green), negative = down (red).
 *   trend-inverse Boolean     Invert trend color (e.g. for error counts: up = bad = red)
 *   trend-label String        Override the auto-generated trend text
 *   sub        String         Small detail line below the label
 *   loading    Boolean        Show skeleton state
 *
 * Usage:
 *   <stat-card label="Total Users" :value="1_240" icon="fa-users" color="blue" :trend="12.5"></stat-card>
 *   <stat-card label="Error Rate" :value="errors" unit="%" icon="fa-circle-xmark" color="red" :trend="-3" trend-inverse></stat-card>
 */

const { computed } = Vue

export default {
    name: 'StatCard',
    props: {
        value:         { default: null },
        label:         { type: String,  default: 'Metric' },
        icon:          { type: String,  default: 'fa-chart-simple' },
        color:         { type: String,  default: 'brand' },
        unit:          { type: String,  default: '' },
        trend:         { type: Number,  default: null },
        trendInverse:  { type: Boolean, default: false },
        trendLabel:    { type: String,  default: null },
        sub:           { type: String,  default: null },
        loading:       { type: Boolean, default: false },
    },

    setup(props) {
        const display_value = computed(() => {
            if (props.value === null || props.value === undefined) return '—'
            if (typeof props.value === 'number') {
                return props.value >= 10000
                    ? props.value.toLocaleString()
                    : String(props.value)
            }
            return String(props.value)
        })

        const trend_positive = computed(() => {
            if (props.trend === null) return null
            return props.trendInverse ? props.trend < 0 : props.trend > 0
        })

        const trend_class = computed(() => {
            if (props.trend === null) return ''
            if (trend_positive.value === null) return 'sc-trend--neutral'
            return trend_positive.value ? 'sc-trend--up' : 'sc-trend--down'
        })

        const trend_icon = computed(() => {
            if (props.trend === null) return ''
            if (props.trend === 0) return 'fa-minus'
            return props.trend > 0 ? 'fa-arrow-trend-up' : 'fa-arrow-trend-down'
        })

        const trend_text = computed(() => {
            if (props.trendLabel) return props.trendLabel
            if (props.trend === null) return ''
            const abs = Math.abs(props.trend)
            const sign = props.trend > 0 ? '+' : ''
            return `${sign}${abs}%`
        })

        return { display_value, trend_positive, trend_class, trend_icon, trend_text }
    },

    template: `
    <div :class="['sc', 'sc--' + color, { 'sc--loading': loading }]">
        <div class="sc-icon-wrap">
            <i :class="'fas ' + icon"></i>
        </div>
        <div class="sc-body">
            <div v-if="loading" class="sc-skeleton">
                <div class="sc-skeleton-value"></div>
                <div class="sc-skeleton-label"></div>
            </div>
            <template v-else>
                <div class="sc-value">
                    {{ display_value }}<span v-if="unit" class="sc-unit">{{ unit }}</span>
                </div>
                <div class="sc-label">{{ label }}</div>
                <div v-if="sub" class="sc-sub">{{ sub }}</div>
            </template>
        </div>
        <div v-if="!loading && trend !== null" :class="['sc-trend', trend_class]">
            <i :class="'fas ' + trend_icon"></i>
            <span>{{ trend_text }}</span>
        </div>
    </div>
    `,
}
