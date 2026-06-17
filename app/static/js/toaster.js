const { ref } = Vue

export const message_list = ref([])

const ICONS = {
    success: 'fa-circle-check',
    warning: 'fa-triangle-exclamation',
    danger:  'fa-circle-xmark',
    info:    'fa-circle-info',
}

const TYPE_MAP = {
    'success-subtle': 'success',
    'warning-subtle': 'warning',
    'danger-subtle':  'danger',
    'success': 'success',
    'warning': 'warning',
    'danger':  'danger',
    'error':   'danger',
    'info':    'info',
}

function getDuration() {
    const container = document.getElementById('appToastContainer')
    return parseInt(container?.dataset.duration || '5000')
}

export function dismiss_message(msg) {
    const idx = message_list.value.indexOf(msg)
    if (idx > -1) message_list.value.splice(idx, 1)
}

export async function create_message(message, type, not_hide = false, link = null) {
    const resolved_type = TYPE_MAP[type] || 'info'
    const duration      = getDuration()
    const id            = Math.random()
    const icon          = ICONS[resolved_type] || 'fa-bell'
    const msg           = { message, type: resolved_type, id, icon, duration, not_hide, link }

    message_list.value.push(msg)

    if (!not_hide) {
        setTimeout(() => dismiss_message(msg), duration + 300)
    }
}

export async function display_toast(res, not_hide = false) {
    const loc = await res.json()

    if (typeof loc.message === 'object') {
        for (let i = 0; i < loc.message.length; i++) {
            const t = loc.toast_class ? (loc.toast_class[i] || loc.toast_class) : 'info'
            await create_message(loc.message[i], t, not_hide)
        }
    } else {
        await create_message(loc.message, loc.toast_class || 'info', not_hide)
    }
}

// Delegated close — no Vue binding needed on individual buttons
document.addEventListener('click', (e) => {
    const btn = e.target.closest('.app-toast-close-btn[data-dismiss-id]')
    if (!btn) return
    const id  = parseFloat(btn.dataset.dismissId)
    const msg = message_list.value.find(m => m.id === id)
    if (msg) dismiss_message(msg)
})
