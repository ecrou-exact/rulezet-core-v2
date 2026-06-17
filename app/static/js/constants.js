// Toast severity — always use these, never raw strings
export const TOAST = {
    SUCCESS: 'success',
    WARNING: 'warning',
    ERROR:   'danger',
    INFO:    'info',
}

// CSRF token injected by base.html
export const CSRF_TOKEN = document.getElementById('csrf_token')?.value

// Authenticated JSON fetch — use for every API call
export async function apiFetch(url, method = 'GET', body = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.getElementById('csrf_token')?.value,
        },
    }
    if (body) options.body = JSON.stringify(body)
    return fetch(url, options)
}
