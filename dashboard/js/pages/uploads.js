/**
 * Uploads Page — YouTube upload history viewer.
 */

const UploadsPage = {
    currentFilter: { channel_id: '' },

    async render() {
        const content = document.getElementById('contentArea');
        content.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';

        try {
            const [uploadsData, channelsData] = await Promise.all([
                API.youtube.history({ channel_id: this.currentFilter.channel_id || undefined }),
                API.channels.list(),
            ]);

            const uploads = uploadsData.uploads || [];
            const channels = channelsData.channels || [];

            content.innerHTML = `
                <div class="data-card-header" style="background:transparent;border:none;padding:0 0 16px 0;">
                    <span class="data-card-title" style="font-size:18px;">Upload History (${uploadsData.total})</span>
                    <div class="filter-group">
                        <select class="form-select" id="uploadFilterChannel" onchange="UploadsPage.filterByChannel()">
                            <option value="">All Channels</option>
                            ${channels.map(ch => `<option value="${ch.id}" ${this.currentFilter.channel_id === ch.id ? 'selected' : ''}>${_esc(ch.name)}</option>`).join('')}
                        </select>
                    </div>
                </div>

                ${uploads.length === 0 ? `
                    <div class="empty-state">
                        <div class="empty-state-icon">☁️</div>
                        <div class="empty-state-text">No uploads yet. Complete a video job and upload it to YouTube.</div>
                    </div>
                ` : `
                    <div class="data-card">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>Title</th>
                                    <th>YouTube ID</th>
                                    <th>Privacy</th>
                                    <th>Tags</th>
                                    <th>Uploaded</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${uploads.map(u => `
                                    <tr>
                                        <td title="${_esc(u.title)}">${_esc(u.title.substring(0, 50))}${u.title.length > 50 ? '…' : ''}</td>
                                        <td><a href="https://www.youtube.com/watch?v=${u.youtube_video_id}" target="_blank" style="color:var(--accent-primary)">${u.youtube_video_id || '—'}</a></td>
                                        <td><span class="badge badge-${u.privacy_status === 'public' ? 'active' : 'inactive'}">${u.privacy_status}</span></td>
                                        <td title="${_esc(u.tags)}">${_esc((u.tags || '').substring(0, 30))}</td>
                                        <td>${u.uploaded_at ? _timeAgo(u.uploaded_at) : '—'}</td>
                                        <td>
                                            ${u.youtube_video_id ? `<a href="https://www.youtube.com/watch?v=${u.youtube_video_id}" target="_blank" class="btn btn-sm btn-secondary">View ↗</a>` : ''}
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

    async filterByChannel() {
        this.currentFilter.channel_id = document.getElementById('uploadFilterChannel').value;
        this.render();
    },
};
