/**
 * Logs Page — System activity log viewer.
 */

const LogsPage = {
    logs: [],

    async render() {
        const content = document.getElementById('contentArea');

        // Collect system status by hitting multiple endpoints
        content.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';

        try {
            const [channelsData, jobsData, schedulerData] = await Promise.allSettled([
                API.channels.list(),
                API.jobs.list({ limit: 200 }),
                API.scheduler.status(),
            ]);

            const channels = channelsData.status === 'fulfilled' ? channelsData.value : { total: 0 };
            const jobs = jobsData.status === 'fulfilled' ? jobsData.value : { total: 0, jobs: [] };
            const scheduler = schedulerData.status === 'fulfilled' ? schedulerData.value : { schedules: [] };

            // Build log entries from job data
            this.logs = [];
            this._addLog('info', `System loaded: ${channels.total || 0} channels, ${jobs.total || 0} jobs`);

            if (jobs.jobs) {
                const failed = jobs.jobs.filter(j => j.status === 'failed');
                const completed = jobs.jobs.filter(j => j.status === 'completed');
                const pending = jobs.jobs.filter(j => j.status === 'pending');
                const generating = jobs.jobs.filter(j => j.status === 'generating');

                this._addLog('success', `${completed.length} jobs completed`);
                if (generating.length) this._addLog('info', `${generating.length} jobs currently generating`);
                if (pending.length) this._addLog('info', `${pending.length} jobs pending`);
                if (failed.length) this._addLog('error', `${failed.length} jobs failed`);

                // Show recent failures
                failed.slice(0, 5).forEach(j => {
                    this._addLog('error', `FAILED: ${j.topic.substring(0, 60)} — ${j.error_message || 'Unknown error'}`);
                });

                // Show recent completions
                completed.slice(0, 5).forEach(j => {
                    this._addLog('success', `COMPLETED: ${j.topic.substring(0, 60)} (score: ${j.viral_score || 0})`);
                });
            }

            if (scheduler.schedules) {
                const active = scheduler.schedules.filter(s => s.is_active);
                this._addLog('info', `${active.length} active schedules running`);
                active.forEach(s => {
                    this._addLog('info', `  → ${s.channel_name}: cron=${s.cron_expression}, last=${s.last_run_at || 'never'}`);
                });
            }

            content.innerHTML = `
                <div class="data-card-header" style="background:transparent;border:none;padding:0 0 16px 0;">
                    <span class="data-card-title" style="font-size:18px;">System Logs</span>
                    <button class="btn btn-secondary" onclick="LogsPage.render()">🔄 Refresh</button>
                </div>

                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-label">API Status</div>
                        <div class="stat-value" style="color:var(--success);font-size:20px;">● Online</div>
                        <div class="stat-icon">🟢</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Log Entries</div>
                        <div class="stat-value">${this.logs.length}</div>
                        <div class="stat-icon">📋</div>
                    </div>
                </div>

                <div class="data-card">
                    <div class="data-card-header">
                        <span class="data-card-title">Activity Log</span>
                    </div>
                    <div class="log-viewer">
                        ${this.logs.map(l => `
                            <div class="log-entry log-${l.level}">
                                <span style="opacity:0.5">[${l.time}]</span>
                                <span style="text-transform:uppercase;font-weight:600;margin:0 6px;">[${l.level}]</span>
                                ${_esc(l.message)}
                            </div>
                        `).join('')}
                        ${this.logs.length === 0 ? '<div style="color:var(--text-muted);text-align:center;padding:20px;">No log entries</div>' : ''}
                    </div>
                </div>
            `;
        } catch (err) {
            content.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><div class="empty-state-text">${err.message}</div></div>`;
        }
    },

    _addLog(level, message) {
        const now = new Date();
        this.logs.push({
            level,
            message,
            time: now.toLocaleTimeString(),
        });
    },
};
