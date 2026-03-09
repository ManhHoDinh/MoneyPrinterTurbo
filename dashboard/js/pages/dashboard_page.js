/**
 * Dashboard Overview Page - Stats and recent activity.
 */

const DashboardPage = {
    async render() {
        const content = document.getElementById('contentArea');
        content.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';

        try {
            const [channelsData, jobsData, uploadsData, schedulerData] = await Promise.allSettled([
                API.channels.list(),
                API.jobs.list({ limit: 10 }),
                API.youtube.history({ limit: 5 }),
                API.scheduler.status(),
            ]);

            const channels = channelsData.status === 'fulfilled' ? channelsData.value : { total: 0, channels: [] };
            const jobs = jobsData.status === 'fulfilled' ? jobsData.value : { total: 0, jobs: [] };
            const uploads = uploadsData.status === 'fulfilled' ? uploadsData.value : { total: 0, uploads: [] };
            const scheduler = schedulerData.status === 'fulfilled' ? schedulerData.value : { total: 0, schedules: [] };

            const completedJobs = jobs.jobs ? jobs.jobs.filter(j => j.status === 'completed').length : 0;
            const failedJobs = jobs.jobs ? jobs.jobs.filter(j => j.status === 'failed').length : 0;
            const activeSchedules = scheduler.schedules ? scheduler.schedules.filter(s => s.is_active).length : 0;

            content.innerHTML = `
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-label">Total Channels</div>
                        <div class="stat-value">${channels.total || 0}</div>
                        <div class="stat-icon">📺</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Total Jobs</div>
                        <div class="stat-value">${jobs.total || 0}</div>
                        <div class="stat-icon">🎬</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Videos Uploaded</div>
                        <div class="stat-value">${uploads.total || 0}</div>
                        <div class="stat-icon">☁️</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Active Schedules</div>
                        <div class="stat-value">${activeSchedules}</div>
                        <div class="stat-icon">⏰</div>
                    </div>
                </div>

                <div class="data-card">
                    <div class="data-card-header">
                        <span class="data-card-title">Recent Video Jobs</span>
                        <a href="#/jobs" class="btn btn-sm btn-secondary">View All →</a>
                    </div>
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Topic</th>
                                <th>Channel</th>
                                <th>Style</th>
                                <th>Status</th>
                                <th>Created</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${(jobs.jobs || []).map(j => `
                                <tr>
                                    <td>${_esc(j.topic.substring(0, 50))}${j.topic.length > 50 ? '…' : ''}</td>
                                    <td>${_esc(j.channel_name)}</td>
                                    <td>${_esc(j.style)}</td>
                                    <td><span class="badge badge-${j.status}">${j.status}</span></td>
                                    <td>${_timeAgo(j.created_at)}</td>
                                </tr>
                            `).join('') || '<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">No jobs yet</td></tr>'}
                        </tbody>
                    </table>
                </div>

                <div class="data-card">
                    <div class="data-card-header">
                        <span class="data-card-title">Channels Overview</span>
                        <a href="#/channels" class="btn btn-sm btn-secondary">Manage →</a>
                    </div>
                    <table class="data-table">
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Niche</th>
                                <th>Style</th>
                                <th>Frequency</th>
                                <th>OAuth</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${(channels.channels || []).map(ch => `
                                <tr>
                                    <td><strong>${_esc(ch.name)}</strong></td>
                                    <td>${_esc(ch.niche_type)}</td>
                                    <td>${_esc(ch.style_preset)}</td>
                                    <td>${_esc(ch.upload_frequency)}</td>
                                    <td>${ch.has_oauth ? '✅' : '❌'}</td>
                                    <td><span class="badge badge-${ch.is_active ? 'active' : 'inactive'}">${ch.is_active ? 'Active' : 'Inactive'}</span></td>
                                </tr>
                            `).join('') || '<tr><td colspan="6" style="text-align:center;color:var(--text-muted)">No channels yet</td></tr>'}
                        </tbody>
                    </table>
                </div>
            `;
        } catch (err) {
            content.innerHTML = `<div class="empty-state">
                <div class="empty-state-icon">⚠️</div>
                <div class="empty-state-text">Failed to load dashboard: ${err.message}</div>
            </div>`;
        }
    }
};
