/**
 * job-monitor.js — Persistent floating job progress widget.
 *
 * Rules:
 *  - Appears as soon as any job becomes active (even < 1s jobs)
 *  - Stays visible until user presses X  (even after jobs complete, linger 20s)
 *  - X dismisses all currently tracked jobs; re-appears only for NEW jobs
 *  - Each job: title, status badge, progress bar, pause/cancel buttons, log toggle
 *  - Panel header collapses/expands the body
 */

const { createApp, ref, computed, onMounted, onUnmounted } = Vue

const ACTIVE   = ['pending', 'running', 'paused']
const LINGER   = 20_000   // ms to keep completed jobs visible before removing
const POLL_ACT = 2_000    // ms between polls when active jobs exist
const POLL_IDL = 5_000    // ms between polls when idle

const DISMISS_KEY = 'jm_dismissed'   // sessionStorage — comma-sep UUIDs

function _csrf() {
    return document.getElementById('csrf_token')?.value || ''
}

async function _api(url, method = 'GET', body = null) {
    const r = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': _csrf() },
        body: body !== null ? JSON.stringify(body) : undefined,
    })
    return r
}

createApp({
    delimiters: ['[[', ']]'],

    setup() {
        const jobs     = ref([])       // tracked job objects (active + lingering)
        const visible  = ref(false)
        const expanded = ref(true)     // false = only header bar visible
        const logOpen  = ref({})       // { [uuid]: boolean }

        let timer        = null
        let dismissed    = new Set(
            (sessionStorage.getItem(DISMISS_KEY) || '').split(',').filter(Boolean)
        )

        // ── helpers ────────────────────────────────────────────────────────────

        function saveDismissed() {
            sessionStorage.setItem(DISMISS_KEY, [...dismissed].join(','))
        }

        function findJob(uuid) {
            return jobs.value.find(j => j.uuid === uuid)
        }

        // ── polling ─────────────────────────────────────────────────────────

        async function poll() {
            try {
                const res = await _api('/api/jobs/?status=active&per_page=20')
                if (!res.ok) { schedule(POLL_IDL); return }

                const { items } = await res.json()
                const activeSet  = new Set(items.map(j => j.uuid))
                const now        = Date.now()

                // Update or add active jobs
                for (const incoming of items) {
                    const ex = findJob(incoming.uuid)
                    if (ex) {
                        ex.status   = incoming.status
                        ex.progress = incoming.progress
                        ex.logs     = incoming.logs || []
                        ex._done    = false
                        ex._done_at = null
                    } else {
                        jobs.value.push({
                            ...incoming,
                            logs:    incoming.logs || [],
                            _done:   false,
                            _done_at: null,
                        })
                        // Show widget if this job wasn't in a previous dismiss
                        if (!dismissed.has(incoming.uuid)) {
                            visible.value  = true
                            expanded.value = true
                        }
                    }
                }

                // Jobs that left the active list → fetch final state, start linger
                for (const job of jobs.value) {
                    if (!activeSet.has(job.uuid) && !job._done) {
                        job._done    = true
                        job._done_at = now
                        try {
                            const r2 = await _api(`/api/jobs/${job.uuid}`)
                            if (r2.ok) {
                                const d = await r2.json()
                                job.status   = d.status
                                job.progress = d.progress
                                job.logs     = d.logs || []
                            }
                        } catch (_) {}
                    }
                }

                // Purge jobs that have lingered long enough
                jobs.value = jobs.value.filter(j => {
                    if (j._done && (now - j._done_at) > LINGER) {
                        delete logOpen.value[j.uuid]
                        return false
                    }
                    return true
                })

                if (jobs.value.length === 0) visible.value = false

                const hasActive = jobs.value.some(j => !j._done)
                schedule(hasActive ? POLL_ACT : POLL_IDL)

            } catch (_) {
                schedule(POLL_IDL)
            }
        }

        function schedule(ms) {
            clearTimeout(timer)
            timer = setTimeout(poll, ms)
        }

        // ── user actions ───────────────────────────────────────────────────────

        function dismiss() {
            for (const j of jobs.value) dismissed.add(j.uuid)
            saveDismissed()
            jobs.value  = []
            logOpen.value = {}
            visible.value = false
        }

        function togglePanel() {
            expanded.value = !expanded.value
        }

        function toggleLogs(uuid) {
            logOpen.value = { ...logOpen.value, [uuid]: !logOpen.value[uuid] }
        }

        async function pauseResume(job) {
            const action = job.status === 'paused' ? 'resume' : 'pause'
            const res = await _api(`/api/jobs/${job.uuid}/${action}`, 'POST')
            if (res.ok) job.status = action === 'pause' ? 'paused' : 'running'
        }

        async function cancelJob(job) {
            if (!confirm(`Cancel "${job.title}"?`)) return
            const res = await _api(`/api/jobs/${job.uuid}/cancel`, 'POST')
            if (res.ok) {
                job.status   = 'cancelled'
                job._done    = true
                job._done_at = Date.now()
            }
        }

        // ── computed ──────────────────────────────────────────────────────────

        const activeCount = computed(() => jobs.value.filter(j => !j._done).length)

        const headerLabel = computed(() => {
            const total  = jobs.value.length
            const active = activeCount.value
            if (total === 0)   return 'No jobs'
            if (active === 0)  return `${total} job${total > 1 ? 's' : ''} finished`
            return `${active} job${active > 1 ? 's' : ''} active`
        })

        function pct(job) {
            return Math.max(0, Math.min(100, job.progress || 0))
        }

        function lastLogs(job) {
            return (job.logs || []).slice(-8)
        }

        function logCls(entry) {
            const l = (entry.level || '').toLowerCase()
            if (l === 'error')   return 'jm-log--error'
            if (l === 'warning') return 'jm-log--warn'
            if (l === 'success') return 'jm-log--ok'
            return ''
        }

        // ── lifecycle ─────────────────────────────────────────────────────────

        onMounted(poll)
        onUnmounted(() => clearTimeout(timer))

        return {
            jobs, visible, expanded, logOpen, headerLabel, activeCount,
            pct, lastLogs, logCls,
            dismiss, togglePanel, toggleLogs, pauseResume, cancelJob,
        }
    },

    template: `
<transition name="jm-fade">
<div v-if="visible" class="jm-panel">

    <!-- ── Header ── -->
    <div class="jm-header" @click="togglePanel">
        <span class="jm-spinner-wrap">
            <i class="fas fa-gear" :class="activeCount > 0 ? 'jm-spin' : 'jm-spin-idle'"></i>
        </span>
        <span class="jm-header-label">[[ headerLabel ]]</span>
        <button class="jm-hbtn" @click.stop="togglePanel"
                :title="expanded ? 'Collapse' : 'Expand'">
            <i :class="expanded ? 'fas fa-chevron-down' : 'fas fa-chevron-up'"></i>
        </button>
        <button class="jm-hbtn jm-hbtn--close" @click.stop="dismiss" title="Dismiss">
            <i class="fas fa-xmark"></i>
        </button>
    </div>

    <!-- ── Body ── -->
    <div v-if="expanded" class="jm-body">
        <div v-for="job in jobs" :key="job.uuid"
             class="jm-job" :class="'jm-job--' + job.status">

            <!-- title + status + actions -->
            <div class="jm-job-row">
                <span class="jm-job-title" :title="job.title">[[ job.title ]]</span>
                <span class="jm-badge" :class="'jm-badge--' + job.status">[[ job.status ]]</span>
            </div>
            <div class="jm-job-acts">
                <button v-if="job.status === 'running' || job.status === 'paused'"
                        class="jm-abtn"
                        :title="job.status === 'paused' ? 'Resume' : 'Pause'"
                        @click="pauseResume(job)">
                    <i :class="job.status === 'paused' ? 'fas fa-play' : 'fas fa-pause'"></i>
                    [[ job.status === 'paused' ? 'Resume' : 'Pause' ]]
                </button>
                <button v-if="!job._done && job.status !== 'cancelled'"
                        class="jm-abtn jm-abtn--danger"
                        title="Cancel" @click="cancelJob(job)">
                    <i class="fas fa-stop"></i> Cancel
                </button>
                <a :href="'/jobs/' + job.uuid" target="_blank"
                   class="jm-abtn jm-abtn--link" title="View detail">
                    <i class="fas fa-arrow-up-right-from-square"></i> Detail
                </a>
            </div>

            <!-- progress -->
            <div class="jm-track">
                <div class="jm-fill"
                     :class="{ 'jm-fill--indeterminate': job.status === 'pending' }"
                     :style="job.status !== 'pending' ? { width: pct(job) + '%' } : {}">
                </div>
            </div>
            <div v-if="job.status !== 'pending'" class="jm-pct">[[ pct(job) ]]%</div>

            <!-- logs toggle -->
            <button class="jm-log-toggle" @click="toggleLogs(job.uuid)">
                <i :class="logOpen[job.uuid] ? 'fas fa-chevron-up' : 'fas fa-chevron-down'"></i>
                [[ logOpen[job.uuid] ? 'Hide logs' : 'Logs' ]]
            </button>
            <div v-if="logOpen[job.uuid]" class="jm-logs">
                <p v-if="!job.logs || !job.logs.length" class="jm-logline jm-log--muted">No logs yet.</p>
                <p v-for="(e, i) in lastLogs(job)" :key="i"
                   class="jm-logline" :class="logCls(e)">[[ e.msg ]]</p>
            </div>

        </div>
    </div>

</div>
</transition>
`,
}).mount('#job-monitor-widget')
