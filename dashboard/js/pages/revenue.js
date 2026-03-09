/**
 * Revenue dashboard backed by real DB metrics.
 */

const RevenuePage = {
    selectedDays: 30,

    async render() {
        const container = document.getElementById('contentArea');
        container.innerHTML = `
            <div class="row" style="margin-bottom:20px;">
                <div class="col-12">
                    <div class="card" style="background: linear-gradient(145deg, #111b21, #0d1117); border: 1px solid #1f6b32;">
                        <div style="display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;align-items:center;">
                            <div>
                                <h3 style="color:#2ea043; margin-top:0;">Revenue Snapshot</h3>
                                <p style="color:var(--text-muted); margin-bottom:0;">
                                    Real tracked revenue, views, clicks, conversions, and multi-platform upload counts.
                                </p>
                            </div>
                            <div style="display:flex;gap:8px;align-items:center;">
                                <label for="revDaysInput" style="color:var(--text-muted);font-size:13px;">Window (days)</label>
                                <input id="revDaysInput" class="form-input" type="number" min="1" max="365" value="30" style="width:90px;">
                                <button class="btn btn-secondary" onclick="RevenuePage.refreshData()">Refresh</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row" style="margin-bottom:20px;">
                <div class="col-8">
                    <div class="card">
                        <h3>Channel Performance</h3>
                        <div class="table-responsive">
                            <table class="table" id="revenueTable">
                                <thead>
                                    <tr>
                                        <th>Channel</th>
                                        <th>Niche</th>
                                        <th>Uploads</th>
                                        <th>Views</th>
                                        <th>Revenue</th>
                                        <th>Monthly Run Rate</th>
                                        <th>Status</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr><td colspan="7" class="text-center" style="color:var(--text-muted)">Loading revenue data...</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
                <div class="col-4">
                    <div class="card">
                        <h3>Summary (<span id="revWindowLabel">30</span> Days)</h3>
                        <div id="revRevenueTotal" style="font-size:36px; font-weight:700; color:#2ea043; margin:20px 0;">$0.00</div>
                        <p style="color:var(--text-muted); font-size:13px;">Tracked revenue across all connected channels.</p>

                        <div style="margin-top:20px; border-top:1px solid var(--border-color); padding-top:20px;">
                            <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                                <span style="color:var(--text-muted)">Views</span>
                                <span id="revViewsTotal">0</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                                <span style="color:var(--text-muted)">Clicks</span>
                                <span id="revClicksTotal">0</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                                <span style="color:var(--text-muted)">Conversions</span>
                                <span id="revConversionsTotal">0</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                                <span style="color:var(--text-muted)">EPMV</span>
                                <span id="revEpmv">$0.00</span>
                            </div>
                            <div style="display:flex; justify-content:space-between;">
                                <span style="color:var(--text-muted)">Revenue Events</span>
                                <span id="revEventsTotal">0</span>
                            </div>
                        </div>
                    </div>

                    <div class="card" style="margin-top:20px;">
                        <h3>Scale Readiness</h3>
                        <div style="font-size:13px; color:var(--text-muted);">
                            <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                                <span>Active Channels</span> <span id="revChannels">0</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                                <span>YouTube Uploads</span> <span id="revYoutubeUploads">0</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                                <span>TikTok Uploads</span> <span id="revTiktokUploads">0</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                                <span>Instagram Uploads</span> <span id="revInstagramUploads">0</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                                <span>Facebook Uploads</span> <span id="revFacebookUploads">0</span>
                            </div>
                            <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                                <span>Tagged Channels</span> <span id="revTaggedChannels">0</span>
                            </div>
                            <div style="display:flex; justify-content:space-between;">
                                <span>Projected 30-Day Run Rate</span> <span id="revRunRate">$0.00</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row">
                <div class="col-12">
                    <div class="card" style="max-width: 900px;">
                        <h3>Revenue Optimization Config</h3>
                        <p style="color:var(--text-muted);font-size:13px;line-height:1.5;">
                            Adjust runtime optimization knobs for offer exploration and winner promotion.
                        </p>

                        <div class="form-group">
                            <label class="form-label">Offer Explore Rate (0 - 1)</label>
                            <input class="form-input" type="number" min="0" max="1" step="0.01" id="cfgOfferExploreRate" />
                        </div>
                        <div class="form-group">
                            <label class="form-label">Winner Promote Share (0 - 1)</label>
                            <input class="form-input" type="number" min="0" max="1" step="0.01" id="cfgWinnerPromoteShare" />
                        </div>
                        <div class="form-group">
                            <label class="form-label">Winner Minimum Impressions</label>
                            <input class="form-input" type="number" min="1" step="1" id="cfgWinnerMinImpressions" />
                        </div>
                        <div class="form-group">
                            <label class="form-label">Winner Minimum Lift Ratio</label>
                            <input class="form-input" type="number" min="0" step="0.01" id="cfgWinnerMinLiftRatio" />
                        </div>

                        <div style="margin-top: 16px; display:flex; gap:8px; flex-wrap:wrap;">
                            <button class="btn btn-primary" onclick="RevenuePage.saveConfig()">Save Revenue Config</button>
                            <button class="btn btn-secondary" onclick="RevenuePage.loadConfig()">Reload Config</button>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row" style="margin-top:20px;">
                <div class="col-12">
                    <div class="card" style="max-width: 900px;">
                        <h3>Test Revenue Update</h3>
                        <p style="color:var(--text-muted);font-size:13px;line-height:1.5;">
                            Send a test revenue update to an existing revenue tag. Use one selector only.
                        </p>

                        <div class="form-group">
                            <label class="form-label">Selector Type</label>
                            <select class="form-input" id="revTestSelectorType">
                                <option value="tag_id">tag_id</option>
                                <option value="job_id">job_id</option>
                                <option value="youtube_video_id">youtube_video_id</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Selector Value</label>
                            <input class="form-input" id="revTestSelectorValue" placeholder="Paste tag_id or job_id or youtube_video_id">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Views</label>
                            <input class="form-input" id="revTestViews" type="number" min="0" step="1" value="1000">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Clicks</label>
                            <input class="form-input" id="revTestClicks" type="number" min="0" step="1" value="120">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Conversions</label>
                            <input class="form-input" id="revTestConversions" type="number" min="0" step="1" value="12">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Revenue Generated (USD)</label>
                            <input class="form-input" id="revTestRevenue" type="number" min="0" step="0.01" value="35.5">
                        </div>

                        <div style="margin-top: 16px; display:flex; gap:8px; flex-wrap:wrap;">
                            <button class="btn btn-primary" onclick="RevenuePage.sendTestUpdate()">Test Update Revenue</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        await Promise.all([this.loadConfig(), this.loadData(this.selectedDays)]);
    },

    refreshData() {
        const raw = Number(document.getElementById('revDaysInput')?.value || 30);
        const normalizedDays = Math.max(1, Math.min(365, Number.isFinite(raw) ? raw : 30));
        this.selectedDays = normalizedDays;
        const input = document.getElementById('revDaysInput');
        if (input) input.value = String(normalizedDays);
        this.loadData(normalizedDays);
    },

    async loadConfig() {
        try {
            const cfg = await window.api.settings.getRevenue();
            const exploreEl = document.getElementById('cfgOfferExploreRate');
            const promoteEl = document.getElementById('cfgWinnerPromoteShare');
            const minImpEl = document.getElementById('cfgWinnerMinImpressions');
            const minLiftEl = document.getElementById('cfgWinnerMinLiftRatio');

            if (exploreEl) exploreEl.value = Number(cfg.offer_explore_rate || 0.2).toFixed(2);
            if (promoteEl) promoteEl.value = Number(cfg.offer_winner_promote_share || 0.75).toFixed(2);
            if (minImpEl) minImpEl.value = String(Number(cfg.offer_winner_min_impressions || 50));
            if (minLiftEl) minLiftEl.value = Number(cfg.offer_winner_min_lift_ratio || 0.15).toFixed(2);
        } catch (error) {
            console.error(error);
            App.toast('Failed to load revenue config', 'error');
        }
    },

    async saveConfig() {
        const data = {
            offer_explore_rate: Number(document.getElementById('cfgOfferExploreRate')?.value || 0),
            offer_winner_promote_share: Number(document.getElementById('cfgWinnerPromoteShare')?.value || 0),
            offer_winner_min_impressions: Number(document.getElementById('cfgWinnerMinImpressions')?.value || 1),
            offer_winner_min_lift_ratio: Number(document.getElementById('cfgWinnerMinLiftRatio')?.value || 0),
        };

        if (data.offer_explore_rate < 0 || data.offer_explore_rate > 1) {
            return App.toast('Offer explore rate must be between 0 and 1', 'error');
        }
        if (data.offer_winner_promote_share < 0 || data.offer_winner_promote_share > 1) {
            return App.toast('Winner promote share must be between 0 and 1', 'error');
        }
        if (!Number.isInteger(data.offer_winner_min_impressions) || data.offer_winner_min_impressions < 1) {
            return App.toast('Winner minimum impressions must be an integer >= 1', 'error');
        }
        if (data.offer_winner_min_lift_ratio < 0) {
            return App.toast('Winner minimum lift ratio must be >= 0', 'error');
        }

        try {
            await window.api.settings.updateRevenue(data);
            App.toast('Revenue config saved successfully', 'success');
            await this.loadConfig();
        } catch (error) {
            console.error(error);
            App.toast(error.message || 'Failed to save revenue config', 'error');
        }
    },

    async sendTestUpdate() {
        const selectorType = document.getElementById('revTestSelectorType')?.value || 'tag_id';
        const selectorValue = (document.getElementById('revTestSelectorValue')?.value || '').trim();
        const views = Number(document.getElementById('revTestViews')?.value || 0);
        const clicks = Number(document.getElementById('revTestClicks')?.value || 0);
        const conversions = Number(document.getElementById('revTestConversions')?.value || 0);
        const revenueGenerated = Number(document.getElementById('revTestRevenue')?.value || 0);

        if (!selectorValue) {
            return App.toast('Selector value is required', 'error');
        }
        if (![views, clicks, conversions, revenueGenerated].every(Number.isFinite)) {
            return App.toast('Invalid numeric values', 'error');
        }
        if (views < 0 || clicks < 0 || conversions < 0 || revenueGenerated < 0) {
            return App.toast('Metrics must be >= 0', 'error');
        }

        const payload = {
            tag_id: '',
            job_id: '',
            youtube_video_id: '',
            views,
            clicks,
            conversions,
            revenue_generated: revenueGenerated,
        };
        payload[selectorType] = selectorValue;

        try {
            const result = await window.api.intelligence.updateRevenueMetrics(payload);
            if (!result?.success) {
                return App.toast(result?.message || 'Revenue update failed', 'error');
            }
            App.toast(`Revenue updated. EPMV: $${Number(result.epmv || 0).toFixed(2)}`, 'success');
            await this.loadData(this.selectedDays);
        } catch (error) {
            console.error(error);
            App.toast(error.message || 'Revenue update failed', 'error');
        }
    },

    async loadData(days = 30) {
        try {
            const labelEl = document.getElementById('revWindowLabel');
            if (labelEl) labelEl.textContent = String(days);

            const data = await window.api.intelligence.revenueDashboard(days);
            const summary = data.summary || {};
            const channels = data.channels || [];
            const tbody = document.querySelector('#revenueTable tbody');
            tbody.innerHTML = '';

            if (channels.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="text-center">No revenue records found.</td></tr>';
            } else {
                for (const ch of channels) {
                    const uploadsLabel = `${ch.uploads} (YT ${ch.youtube_uploads} / TT ${ch.tiktok_uploads} / IG ${ch.instagram_uploads} / FB ${ch.facebook_uploads})`;
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td><strong>${_esc(ch.channel_name)}</strong></td>
                        <td><span class="badge" style="background:var(--bg-card);border:1px solid var(--border-color)">${_esc(ch.niche)}</span></td>
                        <td>${uploadsLabel}</td>
                        <td>${Number(ch.views || 0).toLocaleString()}</td>
                        <td style="color:#2ea043;font-weight:600;">$${Number(ch.revenue || 0).toFixed(2)}</td>
                        <td style="color:#e3b341">$${Number(ch.monthly_projection || 0).toFixed(2)}</td>
                        <td>${ch.is_active ? '<span style="color:#2ea043">Active</span>' : '<span style="color:#ff7b72">Inactive</span>'}</td>
                    `;
                    tbody.appendChild(tr);
                }
            }

            const revenueEl = document.getElementById('revRevenueTotal');
            if (revenueEl) {
                revenueEl.textContent = `$${Number(summary.revenue_total || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            }
            const viewsEl = document.getElementById('revViewsTotal');
            if (viewsEl) viewsEl.textContent = Number(summary.views_total || 0).toLocaleString();
            const clicksEl = document.getElementById('revClicksTotal');
            if (clicksEl) clicksEl.textContent = Number(summary.clicks_total || 0).toLocaleString();
            const convEl = document.getElementById('revConversionsTotal');
            if (convEl) convEl.textContent = Number(summary.conversions_total || 0).toLocaleString();
            const epmvEl = document.getElementById('revEpmv');
            if (epmvEl) epmvEl.textContent = `$${Number(summary.epmv || 0).toFixed(2)}`;
            const eventsEl = document.getElementById('revEventsTotal');
            if (eventsEl) eventsEl.textContent = Number(summary.revenue_events_total || 0).toLocaleString();
            const channelsEl = document.getElementById('revChannels');
            if (channelsEl) channelsEl.textContent = `${Number(summary.channels_active || 0)}/${Number(summary.channels_total || 0)}`;
            const taggedEl = document.getElementById('revTaggedChannels');
            if (taggedEl) taggedEl.textContent = Number(summary.revenue_tagged_channels || 0).toLocaleString();
            const ytEl = document.getElementById('revYoutubeUploads');
            if (ytEl) ytEl.textContent = Number((summary.platform_uploads || {}).youtube || 0).toLocaleString();
            const ttEl = document.getElementById('revTiktokUploads');
            if (ttEl) ttEl.textContent = Number((summary.platform_uploads || {}).tiktok || 0).toLocaleString();
            const igEl = document.getElementById('revInstagramUploads');
            if (igEl) igEl.textContent = Number((summary.platform_uploads || {}).instagram || 0).toLocaleString();
            const fbEl = document.getElementById('revFacebookUploads');
            if (fbEl) fbEl.textContent = Number((summary.platform_uploads || {}).facebook || 0).toLocaleString();
            const runRateEl = document.getElementById('revRunRate');
            if (runRateEl) runRateEl.textContent = `$${Number(summary.monthly_projection || 0).toFixed(2)}`;
        } catch (error) {
            console.error(error);
            App.toast('Failed to load revenue data', 'error');
        }
    }
};
