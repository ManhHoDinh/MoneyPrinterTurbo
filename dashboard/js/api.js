/**
 * API client wrapper for dashboard requests.
 */

const API = {
    BASE: '',

    async _fetch(url, options = {}) {
        try {
            const resp = await fetch(url, {
                headers: { 'Content-Type': 'application/json', ...options.headers },
                ...options,
            });
            if (resp.status === 204) return null;
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.detail || data.message || `HTTP ${resp.status}`);
            return data;
        } catch (err) {
            console.error(`API Error: ${err.message}`);
            throw err;
        }
    },

    channels: {
        list: (skip = 0, limit = 100) =>
            API._fetch(`/api/v1/channels?skip=${skip}&limit=${limit}`),
        get: (id) =>
            API._fetch(`/api/v1/channels/${id}`),
        create: (data) =>
            API._fetch('/api/v1/channels', { method: 'POST', body: JSON.stringify(data) }),
        update: (id, data) =>
            API._fetch(`/api/v1/channels/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
        delete: (id) =>
            API._fetch(`/api/v1/channels/${id}`, { method: 'DELETE' }),
    },

    jobs: {
        list: (params = {}) => {
            const qs = new URLSearchParams();
            if (params.channel_id) qs.set('channel_id', params.channel_id);
            if (params.status) qs.set('status', params.status);
            qs.set('skip', params.skip || 0);
            qs.set('limit', params.limit || 50);
            return API._fetch(`/api/v1/jobs?${qs}`);
        },
        get: (id) =>
            API._fetch(`/api/v1/jobs/${id}`),
        create: (data) =>
            API._fetch('/api/v1/jobs', { method: 'POST', body: JSON.stringify(data) }),
        createBatch: (data) =>
            API._fetch('/api/v1/jobs/batch', { method: 'POST', body: JSON.stringify(data) }),
        updateStatus: (id, data) =>
            API._fetch(`/api/v1/jobs/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
        delete: (id) =>
            API._fetch(`/api/v1/jobs/${id}`, { method: 'DELETE' }),
        getLogs: (id) =>
            API._fetch(`/api/v1/jobs/${id}/logs`),
        getActiveLogs: () =>
            API._fetch('/api/v1/jobs/logs/active'),
    },

    scheduler: {
        status: () =>
            API._fetch('/api/v1/scheduler/status'),
        trigger: (channelId) =>
            API._fetch(`/api/v1/scheduler/${channelId}/trigger`, { method: 'POST' }),
        toggle: (channelId, active) =>
            API._fetch(`/api/v1/scheduler/${channelId}/toggle?active=${active}`, { method: 'POST' }),
        toggleBulk: (data) =>
            API._fetch('/api/v1/scheduler/toggle/bulk', {
                method: 'POST',
                body: JSON.stringify(data),
            }),
        triggerBulk: (data) =>
            API._fetch('/api/v1/scheduler/trigger/bulk', {
                method: 'POST',
                body: JSON.stringify(data),
            }),
        triggerAllActive: (limit = 200) =>
            API._fetch(`/api/v1/scheduler/trigger/all-active?limit=${limit}`, { method: 'POST' }),
        activateAndTriggerAll: (limit = 200) =>
            API._fetch('/api/v1/scheduler/activate-and-trigger-all', {
                method: 'POST',
                body: JSON.stringify({ limit }),
            }),
    },

    youtube: {
        getAuthUrl: (channelId) =>
            API._fetch(`/api/v1/youtube/auth/${channelId}`),
        upload: (jobId) =>
            API._fetch(`/api/v1/youtube/upload/${jobId}`, { method: 'POST' }),
        history: (params = {}) => {
            const qs = new URLSearchParams();
            if (params.channel_id) qs.set('channel_id', params.channel_id);
            qs.set('skip', params.skip || 0);
            qs.set('limit', params.limit || 50);
            return API._fetch(`/api/v1/youtube/history?${qs}`);
        },
    },

    intelligence: {
        revenueDashboard: (days = 30) =>
            API._fetch(`/api/v1/intelligence/revenue/dashboard?days=${days}`),
        updateRevenueMetrics: (data) =>
            API._fetch('/api/v1/intelligence/revenue/update', {
                method: 'POST',
                body: JSON.stringify(data),
            }),
    },

    settings: {
        getYoutube: () => API._fetch('/api/v1/config/youtube'),
        updateYoutube: (data) => API._fetch('/api/v1/config/youtube', {
            method: 'PUT',
            body: JSON.stringify(data),
        }),
        getRevenue: () => API._fetch('/api/v1/config/revenue'),
        updateRevenue: (data) => API._fetch('/api/v1/config/revenue', {
            method: 'PUT',
            body: JSON.stringify(data),
        }),
    },
};

window.api = API;
