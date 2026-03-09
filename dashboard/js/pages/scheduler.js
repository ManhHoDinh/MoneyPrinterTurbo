/**
 * Scheduler Page - bulk schedule control and bulk trigger.
 */

const SchedulerPage = {
    selectedIds: new Set(),
    schedulesCache: [],

    async render() {
        const content = document.getElementById('contentArea');
        content.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';

        try {
            const data = await API.scheduler.status();
            this.schedulesCache = data.schedules || [];

            const schedules = this.schedulesCache;
            const activeCount = schedules.filter(s => s.is_active).length;
            const pausedCount = schedules.length - activeCount;

            content.innerHTML = `
                <div class="data-card-header" style="background:transparent;border:none;padding:0 0 16px 0;">
                    <span class="data-card-title" style="font-size:18px;">Automation Schedules (${schedules.length})</span>
                    <div style="display:flex; gap:8px; flex-wrap:wrap;">
                        <button class="btn btn-secondary" onclick="SchedulerPage.reload()">Reload</button>
                        <button class="btn btn-primary" onclick="SchedulerPage.triggerAllActivePrompt()">Run All Active</button>
                        <button class="btn btn-primary" onclick="SchedulerPage.activateAndRunAllPrompt()">Activate + Run All</button>
                    </div>
                </div>

                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-label">Total Schedules</div>
                        <div class="stat-value">${schedules.length}</div>
                        <div class="stat-icon">SCH</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Active Schedules</div>
                        <div class="stat-value" style="color:var(--success)">${activeCount}</div>
                        <div class="stat-icon">ON</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Paused Schedules</div>
                        <div class="stat-value" style="color:var(--warning)">${pausedCount}</div>
                        <div class="stat-icon">OFF</div>
                    </div>
                </div>

                <div class="data-card" style="margin-bottom:16px;">
                    <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
                        <input id="schedulerSearch" class="form-input" placeholder="Search channel name..." style="max-width:300px;" />
                        <button class="btn btn-secondary" onclick="SchedulerPage.applyFilter()">Filter</button>
                        <span id="schedulerSelectedCount" style="color:var(--text-muted); margin-left:auto;">Selected: 0</span>
                    </div>
                    <div style="display:flex; gap:8px; flex-wrap:wrap; margin-top:12px;">
                        <button class="btn btn-secondary" onclick="SchedulerPage.selectAllVisible()">Select Visible</button>
                        <button class="btn btn-secondary" onclick="SchedulerPage.clearSelection()">Clear Selection</button>
                        <button class="btn btn-primary" onclick="SchedulerPage.bulkToggle(true)">Activate Selected</button>
                        <button class="btn btn-secondary" onclick="SchedulerPage.bulkToggle(false)">Pause Selected</button>
                        <button class="btn btn-primary" onclick="SchedulerPage.bulkTriggerSelected()">Run Selected Now</button>
                    </div>
                </div>

                <div id="schedulerTableWrap"></div>
            `;

            this.renderTable(schedules);
            const searchInput = document.getElementById('schedulerSearch');
            if (searchInput) {
                searchInput.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') this.applyFilter();
                });
            }
        } catch (err) {
            content.innerHTML = `<div class="empty-state"><div class="empty-state-icon">!</div><div class="empty-state-text">${err.message}</div></div>`;
        }
    },

    renderTable(schedules) {
        const wrap = document.getElementById('schedulerTableWrap');
        if (!wrap) return;

        if (!schedules || schedules.length === 0) {
            wrap.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">CLK</div>
                    <div class="empty-state-text">No schedules configured. Create a channel to set up automation.</div>
                </div>
            `;
            this.updateSelectedCount();
            return;
        }

        wrap.innerHTML = `
            <div class="data-card">
                <table class="data-table">
                    <thead>
                        <tr>
                            <th style="width:36px;"><input type="checkbox" id="schedulerSelectAll" onclick="SchedulerPage.toggleAllVisible(this.checked)"></th>
                            <th>Channel</th>
                            <th>Platforms</th>
                            <th>Cron</th>
                            <th>Videos/Run</th>
                            <th>Max Pending</th>
                            <th>Status</th>
                            <th>Last Run</th>
                            <th>Next Run</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${schedules.map(s => {
                            const checked = this.selectedIds.has(s.channel_id) ? 'checked' : '';
                            return `
                                <tr>
                                    <td><input type="checkbox" data-channel-id="${s.channel_id}" ${checked} onchange="SchedulerPage.toggleOne('${s.channel_id}', this.checked)"></td>
                                    <td><strong>${_esc(s.channel_name)}</strong></td>
                                    <td>${_esc(String(s.target_platforms || 'youtube'))}</td>
                                    <td><code style="background:var(--bg-input);padding:2px 8px;border-radius:4px;">${_esc(s.cron_expression)}</code></td>
                                    <td>${s.videos_per_run}</td>
                                    <td>${Number(s.max_pending_jobs || 6)}</td>
                                    <td><span class="badge badge-${s.is_active ? 'active' : 'inactive'}">${s.is_active ? 'Active' : 'Paused'}</span></td>
                                    <td>${s.last_run_at ? _timeAgo(s.last_run_at) : 'Never'}</td>
                                    <td>${s.next_run_at ? new Date(s.next_run_at).toLocaleString() : '-'}</td>
                                    <td>
                                        <div style="display:flex;gap:4px;">
                                            <button class="btn btn-sm ${s.is_active ? 'btn-secondary' : 'btn-primary'}" onclick="SchedulerPage.toggleSchedule('${s.channel_id}', ${!s.is_active})">
                                                ${s.is_active ? 'Pause' : 'Activate'}
                                            </button>
                                            <button class="btn btn-sm btn-secondary" onclick="SchedulerPage.triggerNow('${s.channel_id}', '${_esc(s.channel_name)}')">
                                                Run Now
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
            </div>
        `;

        this.updateSelectedCount();
        this.syncHeaderCheckbox();
    },

    getVisibleSchedules() {
        const term = (document.getElementById('schedulerSearch')?.value || '').trim().toLowerCase();
        if (!term) return [...this.schedulesCache];
        return this.schedulesCache.filter(s => String(s.channel_name || '').toLowerCase().includes(term));
    },

    applyFilter() {
        this.renderTable(this.getVisibleSchedules());
    },

    toggleOne(channelId, checked) {
        if (checked) this.selectedIds.add(channelId);
        else this.selectedIds.delete(channelId);
        this.updateSelectedCount();
        this.syncHeaderCheckbox();
    },

    toggleAllVisible(checked) {
        const visible = this.getVisibleSchedules();
        for (const s of visible) {
            if (checked) this.selectedIds.add(s.channel_id);
            else this.selectedIds.delete(s.channel_id);
        }
        this.renderTable(visible);
    },

    selectAllVisible() {
        const visible = this.getVisibleSchedules();
        for (const s of visible) this.selectedIds.add(s.channel_id);
        this.renderTable(visible);
    },

    clearSelection() {
        this.selectedIds.clear();
        this.renderTable(this.getVisibleSchedules());
    },

    syncHeaderCheckbox() {
        const visible = this.getVisibleSchedules();
        const header = document.getElementById('schedulerSelectAll');
        if (!header) return;
        if (visible.length === 0) {
            header.checked = false;
            return;
        }
        header.checked = visible.every(s => this.selectedIds.has(s.channel_id));
    },

    updateSelectedCount() {
        const el = document.getElementById('schedulerSelectedCount');
        if (el) el.textContent = `Selected: ${this.selectedIds.size}`;
    },

    async reload() {
        await this.render();
    },

    async toggleSchedule(channelId, active) {
        try {
            await API.scheduler.toggle(channelId, active);
            App.toast(`Schedule ${active ? 'activated' : 'paused'}`, 'success');
            await this.reload();
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    async triggerNow(channelId, channelName) {
        if (!confirm(`Run batch generation for "${channelName}" now?`)) return;
        try {
            await API.scheduler.trigger(channelId);
            App.toast(`Batch triggered for ${channelName}`, 'success');
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    async bulkToggle(active) {
        const channelIds = [...this.selectedIds];
        if (channelIds.length === 0) {
            return App.toast('Select at least 1 channel', 'error');
        }
        try {
            const result = await API.scheduler.toggleBulk({ channel_ids: channelIds, active });
            App.toast(`Updated ${result.updated}/${result.requested} schedules`, 'success');
            await this.reload();
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    async bulkTriggerSelected() {
        const channelIds = [...this.selectedIds];
        if (channelIds.length === 0) {
            return App.toast('Select at least 1 channel', 'error');
        }
        if (!confirm(`Trigger ${channelIds.length} selected channels now?`)) return;

        try {
            const result = await API.scheduler.triggerBulk({
                channel_ids: channelIds,
                only_active: true,
                limit: channelIds.length,
            });
            App.toast(`Triggered ${result.triggered}/${result.requested} channels`, 'success');
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    async triggerAllActivePrompt() {
        const raw = prompt('Run all active channels now. Enter max channels (default 200):', '200');
        if (raw === null) return;
        const limit = Math.max(1, Math.min(2000, Number(raw) || 200));

        if (!confirm(`Trigger up to ${limit} active channels now?`)) return;
        try {
            const result = await API.scheduler.triggerAllActive(limit);
            App.toast(`Triggered ${result.triggered}/${result.requested} active channels`, 'success');
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    async activateAndRunAllPrompt() {
        const raw = prompt('Activate schedules and run now. Enter max channels (default 200):', '200');
        if (raw === null) return;
        const limit = Math.max(1, Math.min(2000, Number(raw) || 200));

        if (!confirm(`Activate schedules and trigger up to ${limit} channels now?`)) return;
        try {
            const result = await API.scheduler.activateAndTriggerAll(limit);
            App.toast(
                `Activated ${result.schedules_activated} schedules, triggered ${result.triggered}/${result.requested}`,
                'success',
            );
            await this.reload();
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },
};
