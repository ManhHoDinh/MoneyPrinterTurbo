/**
 * Jobs Page — Video job management with filtering, batch creation, and status updates.
 */

const JobsPage = {
    currentFilter: { channel_id: '', status: '' },

    async render() {
        const content = document.getElementById('contentArea');
        content.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';

        try {
            const [jobsData, channelsData] = await Promise.all([
                API.jobs.list(this.currentFilter),
                API.channels.list(),
            ]);

            const jobs = jobsData.jobs || [];
            const channels = channelsData.channels || [];

            content.innerHTML = `
                <div class="data-card-header" style="background:transparent;border:none;padding:0 0 16px 0;">
                    <div class="action-bar">
                        <span class="data-card-title" style="font-size:18px;">Video Jobs (${jobsData.total})</span>
                        <div class="filter-group">
                            <select class="form-select" id="filterChannel" onchange="JobsPage.applyFilter()">
                                <option value="">All Channels</option>
                                ${channels.map(ch => `<option value="${ch.id}" ${this.currentFilter.channel_id === ch.id ? 'selected' : ''}>${_esc(ch.name)}</option>`).join('')}
                            </select>
                            <select class="form-select" id="filterStatus" onchange="JobsPage.applyFilter()">
                                <option value="">All Status</option>
                                ${['pending', 'generating', 'rendering', 'uploading', 'completed', 'failed'].map(s => `<option value="${s}" ${this.currentFilter.status === s ? 'selected' : ''}>${s}</option>`).join('')}
                            </select>
                        </div>
                    </div>
                    <div style="display:flex;gap:8px;">
                        <button class="btn btn-secondary" onclick="JobsPage.showCreateModal(${JSON.stringify(channels).replace(/"/g, '&quot;')})">+ Single Job</button>
                        <button class="btn btn-primary" onclick="JobsPage.showBatchModal(${JSON.stringify(channels).replace(/"/g, '&quot;')})">⚡ Batch Generate</button>
                    </div>
                </div>

                ${jobs.length === 0 ? `
                    <div class="empty-state">
                        <div class="empty-state-icon">🎬</div>
                        <div class="empty-state-text">No video jobs found. Create one to start generating.</div>
                    </div>
                ` : `
                    <div class="data-card">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>Topic</th>
                                    <th>Channel</th>
                                    <th>Style</th>
                                    <th>Language</th>
                                    <th>Status</th>
                                    <th>Viral Score</th>
                                    <th>Uploads</th>
                                    <th>Created</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${jobs.map(j => `
                                    <tr>
                                        <td title="${_esc(j.topic)}">${_esc(j.topic.substring(0, 45))}${j.topic.length > 45 ? '…' : ''}</td>
                                        <td>${_esc(j.channel_name)}</td>
                                        <td>${_esc(j.style.replace(/_/g, ' '))}</td>
                                        <td><span class="badge" style="background:var(--bg-secondary);color:var(--text-primary); border: 1px solid var(--border-color);">${(j.language || 'en').toUpperCase()}</span></td>
                                        <td><span class="badge badge-${j.status}">${j.status}</span></td>
                                        <td>${j.viral_score ? j.viral_score.toFixed(1) : '—'}</td>
                                        <td>
                                            ${j.youtube_video_id ? '<span title="YouTube" style="color:#ff0000; margin-right:4px;">▶</span>' : ''}
                                            ${j.tiktok_video_id ? '<span title="TikTok" style="color:#00f2fe; margin-right:4px;">♪</span>' : ''}
                                            ${!j.youtube_video_id && !j.tiktok_video_id ? '<span style="color:#6e7681">-</span>' : ''}
                                        </td>
                                        <td>${_timeAgo(j.created_at)}</td>
                                        <td>
                                            <div style="display:flex;gap:4px;">
                                                <button class="btn-icon" onclick="JobsPage.showLogs('${j.id}')" title="View Logs">📋</button>
                                                ${j.status === 'completed' && j.video_path ? `<button class="btn-icon" onclick="JobsPage.uploadJob('${j.id}')" title="Upload to YouTube">☁️</button>` : ''}
                                                ${j.status === 'failed' ? `<button class="btn-icon" onclick="JobsPage.retryJob('${j.id}')" title="Retry">🔄</button>` : ''}
                                                <button class="btn-icon" onclick="JobsPage.deleteJob('${j.id}')" title="Delete" style="color:var(--danger)">🗑️</button>
                                            </div>
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                `}
            `;
        } catch (err) {
            content.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><div class="empty-state-text">${err.message}</div></div>`;
        }
    },

    applyFilter() {
        this.currentFilter.channel_id = document.getElementById('filterChannel').value;
        this.currentFilter.status = document.getElementById('filterStatus').value;
        this.render();
    },

    showCreateModal(channels) {
        App.openModal('Create Video Job', `
            <div class="form-group">
                <label class="form-label">Channel *</label>
                <select class="form-select" id="jobChannel">
                    ${channels.map(ch => `<option value="${ch.id}">${_esc(ch.name)}</option>`).join('')}
                </select>
            </div>
            <div class="form-group">
                <label class="form-label">Topic *</label>
                <input class="form-input" id="jobTopic" placeholder="e.g. 5 Dark Psychology tricks people use on you">
            </div>
            <div class="form-group">
                <label class="form-label">Style Override</label>
                <select class="form-select" id="jobStyle">
                    <option value="">Use channel default</option>
                    <option value="dark_psychology">Dark Psychology</option>
                    <option value="motivation">Motivation</option>
                    <option value="luxury_lifestyle">Luxury Lifestyle</option>
                    <option value="stoic_philosophy">Stoic Philosophy</option>
                    <option value="viral_facts">Viral Facts</option>
                </select>
            </div>
            <div class="modal-actions">
                <button class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
                <button class="btn btn-primary" onclick="JobsPage.submitCreate()">Create Job</button>
            </div>
        `);
    },

    async submitCreate() {
        const data = {
            channel_id: document.getElementById('jobChannel').value,
            topic: document.getElementById('jobTopic').value.trim(),
            style: document.getElementById('jobStyle').value,
        };
        if (!data.topic) return App.toast('Topic is required', 'error');

        try {
            await API.jobs.create(data);
            App.closeModal();
            App.toast('Job created!', 'success');
            this.render();
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    showBatchModal(channels) {
        App.openModal('Batch Generate Videos', `
            <div class="form-group">
                <label class="form-label">Channel *</label>
                <select class="form-select" id="batchChannel">
                    ${channels.map(ch => `<option value="${ch.id}">${_esc(ch.name)}</option>`).join('')}
                </select>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Number of Videos</label>
                    <input class="form-input" id="batchCount" type="number" min="1" max="50" value="5">
                </div>
                <div class="form-group">
                    <label class="form-label">Niche Override</label>
                    <input class="form-input" id="batchNiche" placeholder="Leave empty for channel default">
                </div>
            </div>
            <div class="modal-actions">
                <button class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
                <button class="btn btn-primary" onclick="JobsPage.submitBatch()">⚡ Generate Batch</button>
            </div>
        `);
    },

    async submitBatch() {
        const data = {
            channel_id: document.getElementById('batchChannel').value,
            count: parseInt(document.getElementById('batchCount').value) || 5,
            niche: document.getElementById('batchNiche').value.trim(),
        };

        try {
            const result = await API.jobs.createBatch(data);
            App.closeModal();
            App.toast(`Batch created: ${result.jobs_created} jobs queued!`, 'success');
            this.render();
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    async uploadJob(jobId) {
        try {
            await API.youtube.upload(jobId);
            App.toast('Upload queued!', 'success');
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    async retryJob(jobId) {
        try {
            await API.jobs.updateStatus(jobId, { status: 'pending' });
            App.toast('Job reset to pending', 'success');
            this.render();
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    async deleteJob(jobId) {
        if (!confirm('Delete this job?')) return;
        try {
            await API.jobs.delete(jobId);
            App.toast('Job deleted', 'success');
            this.render();
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    // ── Log Viewer ──────────────────────────────────────────────────────
    _logStream: null,

    async showLogs(jobId) {
        App.openModal('Job Logs', `
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                <span style="font-size:13px;color:var(--text-muted);">Job: ${jobId.substring(0, 12)}…</span>
                <div style="display:flex;gap:8px;align-items:center;">
                    <button class="btn btn-secondary" id="logRefreshBtn" onclick="JobsPage.refreshLogs('${jobId}')" style="font-size:12px;padding:4px 10px;">↻ Refresh</button>
                    <button class="btn btn-primary" id="logStreamBtn" onclick="JobsPage.toggleStream('${jobId}')" style="font-size:12px;padding:4px 10px;">▶ Live Stream</button>
                </div>
            </div>
            <div id="logContainer" style="
                background:#0d1117;border-radius:8px;padding:12px;
                max-height:400px;overflow-y:auto;font-family:'Fira Code',monospace;
                font-size:12px;line-height:1.7;
            ">
                <div style="color:#8b949e;">Loading logs...</div>
            </div>
            <div class="modal-actions" style="margin-top:12px;">
                <button class="btn btn-secondary" onclick="JobsPage.stopStream();App.closeModal()">Close</button>
            </div>
        `);
        this.refreshLogs(jobId);
    },

    async refreshLogs(jobId) {
        try {
            const data = await API.jobs.getLogs(jobId);
            const container = document.getElementById('logContainer');
            if (!data.logs || data.logs.length === 0) {
                container.innerHTML = '<div style="color:#8b949e;">No logs captured yet. Logs appear when the job starts generating.</div>';
                return;
            }
            container.innerHTML = data.logs.map(log => this._formatLogLine(log)).join('');
            container.scrollTop = container.scrollHeight;
        } catch (err) {
            const container = document.getElementById('logContainer');
            if (container) container.innerHTML = `<div style="color:#f85149;">Error: ${err.message}</div>`;
        }
    },

    toggleStream(jobId) {
        if (this._logStream) {
            this.stopStream();
        } else {
            this.startStream(jobId);
        }
    },

    startStream(jobId) {
        this.stopStream();
        const btn = document.getElementById('logStreamBtn');
        if (btn) { btn.textContent = '⏹ Stop'; btn.style.background = 'var(--danger)'; }

        const container = document.getElementById('logContainer');
        this._logStream = new EventSource(`/api/v1/jobs/${jobId}/logs/stream`);

        this._logStream.onmessage = (event) => {
            try {
                const log = JSON.parse(event.data);
                if (log.type === 'done') {
                    this.stopStream();
                    container.innerHTML += '<div style="color:#3fb950;margin-top:8px;">── Stream ended ──</div>';
                    return;
                }
                container.innerHTML += this._formatLogLine(log);
                container.scrollTop = container.scrollHeight;
            } catch (e) { /* ignore parse errors */ }
        };

        this._logStream.onerror = () => {
            this.stopStream();
            if (container) container.innerHTML += '<div style="color:#f85149;margin-top:8px;">── Connection lost ──</div>';
        };
    },

    stopStream() {
        if (this._logStream) {
            this._logStream.close();
            this._logStream = null;
        }
        const btn = document.getElementById('logStreamBtn');
        if (btn) { btn.textContent = '▶ Live Stream'; btn.style.background = ''; }
    },

    _formatLogLine(log) {
        const colors = { INFO: '#3fb950', WARNING: '#d29922', ERROR: '#f85149', DEBUG: '#8b949e' };
        const color = colors[log.level] || '#c9d1d9';
        const stageTag = log.stage ? `<span style="color:#58a6ff;">[${log.stage}]</span> ` : '';
        return `<div style="color:${color};">
            <span style="color:#6e7681;">${log.time || ''}</span>
            <span style="color:${color};font-weight:600;">${log.level.padEnd(7)}</span>
            ${stageTag}${_esc(log.message)}
        </div>`;
    },
};
