/**
 * Channels Page - CRUD with multi-platform + multilingual config.
 */

const CHANNEL_PLATFORM_OPTIONS = [
    'youtube',
    'tiktok',
    'instagram',
    'facebook',
    'x',
    'linkedin',
    'pinterest',
    'snapchat',
    'telegram',
];

const CHANNEL_LANGUAGE_OPTIONS = [
    'en', 'vi', 'es', 'pt', 'fr', 'de', 'it', 'id', 'th', 'ja', 'ko', 'hi', 'ar', 'ru'
];

const ChannelsPage = {
    _checkedValues(containerId) {
        const root = document.getElementById(containerId);
        if (!root) return [];
        return Array.from(root.querySelectorAll('input[type="checkbox"]:checked')).map((el) => el.value);
    },

    _checkboxGroupHtml({ id, options, selected = [] }) {
        const picked = new Set((selected || []).map((x) => String(x).toLowerCase()));
        return `
            <div id="${id}" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px;">
                ${options.map((opt) => {
                    const checked = picked.has(String(opt).toLowerCase()) ? 'checked' : '';
                    return `
                        <label style="display:flex;align-items:center;gap:6px;padding:6px 8px;border:1px solid var(--border-color);border-radius:6px;">
                            <input type="checkbox" value="${opt}" ${checked}>
                            <span>${opt}</span>
                        </label>
                    `;
                }).join('')}
            </div>
        `;
    },

    async render() {
        const content = document.getElementById('contentArea');
        content.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';

        try {
            const data = await API.channels.list();
            const channels = data.channels || [];

            content.innerHTML = `
                <div class="data-card-header" style="background:transparent;border:none;padding:0 0 16px 0;">
                    <span class="data-card-title" style="font-size:18px;">All Channels (${data.total})</span>
                    <button class="btn btn-primary" onclick="ChannelsPage.showCreateModal()">+ Add Channel</button>
                </div>

                ${channels.length === 0 ? `
                    <div class="empty-state">
                        <div class="empty-state-icon">CH</div>
                        <div class="empty-state-text">No channels yet. Create your first channel to get started.</div>
                        <button class="btn btn-primary" onclick="ChannelsPage.showCreateModal()">+ Create Channel</button>
                    </div>
                ` : `
                    <div class="data-card">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>YouTube Account</th>
                                    <th>Niche</th>
                                    <th>Style</th>
                                    <th>Platforms</th>
                                    <th>Languages</th>
                                    <th>Daily Limit</th>
                                    <th>Max Pending</th>
                                    <th>OAuth</th>
                                    <th>Status</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${channels.map((ch) => `
                                    <tr>
                                        <td><strong>${_esc(ch.name)}</strong></td>
                                        <td>${_esc(ch.youtube_account || '-')}</td>
                                        <td>${_esc(ch.niche_type)}</td>
                                        <td>${_esc(String(ch.style_preset || '').replace(/_/g, ' '))}</td>
                                        <td>${_esc((ch.target_platforms || []).join(', ') || 'youtube')}</td>
                                        <td>${_esc((ch.target_languages || []).join(', ') || 'en')}</td>
                                        <td>${Number(ch.daily_video_limit || 0)}</td>
                                        <td>${Number(ch.max_pending_jobs || 6)}</td>
                                        <td>${ch.has_oauth ? '<span style="color:var(--success)">Connected</span>' : `<button class="btn btn-sm btn-secondary" onclick="ChannelsPage.connectOAuth('${ch.id}')">Connect</button>`}</td>
                                        <td><span class="badge badge-${ch.is_active ? 'active' : 'inactive'}">${ch.is_active ? 'Active' : 'Inactive'}</span></td>
                                        <td>
                                            <div style="display:flex;gap:4px;">
                                                <button class="btn-icon" onclick="ChannelsPage.showEditModal('${ch.id}')" title="Edit">Edit</button>
                                                <button class="btn-icon" onclick="ChannelsPage.deleteChannel('${ch.id}','${_esc(ch.name)}')" title="Delete" style="color:var(--danger)">Del</button>
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
            content.innerHTML = `<div class="empty-state"><div class="empty-state-icon">!</div><div class="empty-state-text">${err.message}</div></div>`;
        }
    },

    showCreateModal() {
        App.openModal('Create Channel', `
            <div class="form-group">
                <label class="form-label">Channel Name *</label>
                <input class="form-input" id="chName" placeholder="e.g. DarkMind Psychology" required>
            </div>
            <div class="form-group">
                <label class="form-label">YouTube Account</label>
                <input class="form-input" id="chYoutube" placeholder="e.g. @darkmindpsych">
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Niche Type</label>
                    <select class="form-select" id="chNiche">
                        <option value="general">General</option>
                        <option value="psychology">Psychology</option>
                        <option value="motivation">Motivation</option>
                        <option value="luxury">Luxury Lifestyle</option>
                        <option value="philosophy">Philosophy</option>
                        <option value="facts">Viral Facts</option>
                        <option value="finance">Finance</option>
                        <option value="tech">Technology</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Style Preset</label>
                    <select class="form-select" id="chStyle">
                        <option value="dark_psychology">Dark Psychology</option>
                        <option value="motivation">Motivation</option>
                        <option value="luxury_lifestyle">Luxury Lifestyle</option>
                        <option value="stoic_philosophy">Stoic Philosophy</option>
                        <option value="viral_facts">Viral Facts</option>
                    </select>
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Upload Frequency</label>
                    <select class="form-select" id="chFrequency">
                        <option value="daily">Daily</option>
                        <option value="twice_daily">Twice Daily</option>
                        <option value="weekly">Weekly</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">Daily Video Limit</label>
                    <input class="form-input" id="chLimit" type="number" min="1" max="50" value="3">
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">Schedule (Cron)</label>
                    <input class="form-input" id="chCron" value="0 9 * * *" placeholder="minute hour day month weekday">
                </div>
                <div class="form-group">
                    <label class="form-label">Videos Per Run</label>
                    <input class="form-input" id="chPerRun" type="number" min="1" max="20" value="3">
                </div>
            </div>
            <div class="form-group">
                <label class="form-label">Max Pending Jobs</label>
                <input class="form-input" id="chMaxPending" type="number" min="1" max="200" value="6">
            </div>
            <div class="form-group">
                <label class="form-label">Target Platforms</label>
                ${this._checkboxGroupHtml({ id: 'chPlatforms', options: CHANNEL_PLATFORM_OPTIONS, selected: ['youtube'] })}
            </div>
            <div class="form-group">
                <label class="form-label">Target Languages</label>
                ${this._checkboxGroupHtml({ id: 'chLanguages', options: CHANNEL_LANGUAGE_OPTIONS, selected: ['en'] })}
            </div>
            <div class="modal-actions">
                <button class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
                <button class="btn btn-primary" onclick="ChannelsPage.submitCreate()">Create Channel</button>
            </div>
        `);
    },

    async submitCreate() {
        const target_platforms = this._checkedValues('chPlatforms');
        const target_languages = this._checkedValues('chLanguages');
        const data = {
            name: document.getElementById('chName').value.trim(),
            youtube_account: document.getElementById('chYoutube').value.trim(),
            niche_type: document.getElementById('chNiche').value,
            style_preset: document.getElementById('chStyle').value,
            upload_frequency: document.getElementById('chFrequency').value,
            daily_video_limit: parseInt(document.getElementById('chLimit').value, 10) || 3,
            max_pending_jobs: parseInt(document.getElementById('chMaxPending').value, 10) || 6,
            target_platforms: target_platforms.length ? target_platforms : ['youtube'],
            target_languages: target_languages.length ? target_languages : ['en'],
            cron_expression: document.getElementById('chCron').value.trim(),
            videos_per_run: parseInt(document.getElementById('chPerRun').value, 10) || 3,
        };
        if (!data.name) return App.toast('Channel name is required', 'error');

        try {
            await API.channels.create(data);
            App.closeModal();
            App.toast('Channel created successfully', 'success');
            await this.render();
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    async showEditModal(id) {
        try {
            const ch = await API.channels.get(id);
            App.openModal('Edit Channel', `
                <div class="form-group">
                    <label class="form-label">Channel Name</label>
                    <input class="form-input" id="editName" value="${_esc(ch.name)}">
                </div>
                <div class="form-group">
                    <label class="form-label">YouTube Account</label>
                    <input class="form-input" id="editYoutube" value="${_esc(ch.youtube_account)}">
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Niche Type</label>
                        <select class="form-select" id="editNiche">
                            ${['general', 'psychology', 'motivation', 'luxury', 'philosophy', 'facts', 'finance', 'tech'].map((n) => `<option value="${n}" ${ch.niche_type === n ? 'selected' : ''}>${n}</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Style Preset</label>
                        <select class="form-select" id="editStyle">
                            ${['dark_psychology', 'motivation', 'luxury_lifestyle', 'stoic_philosophy', 'viral_facts'].map((s) => `<option value="${s}" ${ch.style_preset === s ? 'selected' : ''}>${s.replace(/_/g, ' ')}</option>`).join('')}
                        </select>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Upload Frequency</label>
                        <select class="form-select" id="editFrequency">
                            ${['daily', 'twice_daily', 'weekly'].map((f) => `<option value="${f}" ${ch.upload_frequency === f ? 'selected' : ''}>${f}</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Daily Limit</label>
                        <input class="form-input" id="editLimit" type="number" min="1" max="50" value="${ch.daily_video_limit}">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Max Pending Jobs</label>
                        <input class="form-input" id="editMaxPending" type="number" min="1" max="200" value="${Number(ch.max_pending_jobs || 6)}">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Schedule (Cron)</label>
                        <input class="form-input" id="editCron" value="${ch.schedule ? _esc(ch.schedule.cron_expression) : '0 9 * * *'}">
                    </div>
                </div>
                <div class="form-group">
                    <label class="form-label">Target Platforms</label>
                    ${this._checkboxGroupHtml({ id: 'editPlatforms', options: CHANNEL_PLATFORM_OPTIONS, selected: ch.target_platforms || ['youtube'] })}
                </div>
                <div class="form-group">
                    <label class="form-label">Target Languages</label>
                    ${this._checkboxGroupHtml({ id: 'editLanguages', options: CHANNEL_LANGUAGE_OPTIONS, selected: ch.target_languages || ['en'] })}
                </div>
                <div class="form-group">
                    <label class="form-label">Active</label>
                    <select class="form-select" id="editActive">
                        <option value="true" ${ch.is_active ? 'selected' : ''}>Active</option>
                        <option value="false" ${!ch.is_active ? 'selected' : ''}>Inactive</option>
                    </select>
                </div>
                <div class="modal-actions">
                    <button class="btn btn-secondary" onclick="App.closeModal()">Cancel</button>
                    <button class="btn btn-primary" onclick="ChannelsPage.submitEdit('${id}')">Save Changes</button>
                </div>
            `);
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    async submitEdit(id) {
        const target_platforms = this._checkedValues('editPlatforms');
        const target_languages = this._checkedValues('editLanguages');
        const data = {
            name: document.getElementById('editName').value.trim(),
            youtube_account: document.getElementById('editYoutube').value.trim(),
            niche_type: document.getElementById('editNiche').value,
            style_preset: document.getElementById('editStyle').value,
            upload_frequency: document.getElementById('editFrequency').value,
            daily_video_limit: parseInt(document.getElementById('editLimit').value, 10) || 3,
            max_pending_jobs: parseInt(document.getElementById('editMaxPending').value, 10) || 6,
            target_platforms: target_platforms.length ? target_platforms : ['youtube'],
            target_languages: target_languages.length ? target_languages : ['en'],
            is_active: document.getElementById('editActive').value === 'true',
            cron_expression: document.getElementById('editCron').value.trim(),
        };

        try {
            await API.channels.update(id, data);
            App.closeModal();
            App.toast('Channel updated', 'success');
            await this.render();
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    async deleteChannel(id, name) {
        if (!confirm(`Delete channel "${name}"? This will also delete all jobs and uploads.`)) return;
        try {
            await API.channels.delete(id);
            App.toast('Channel deleted', 'success');
            await this.render();
        } catch (err) {
            App.toast(err.message, 'error');
        }
    },

    async connectOAuth(channelId) {
        try {
            const data = await API.youtube.getAuthUrl(channelId);
            window.open(data.auth_url, '_blank');
        } catch (_err) {
            App.toast('OAuth setup requires YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET env vars', 'error');
        }
    },
};
