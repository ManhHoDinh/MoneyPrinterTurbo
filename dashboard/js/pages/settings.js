/**
 * Settings Page
 */

const SettingsPage = {
    async render() {
        const content = document.getElementById('contentArea');
        content.innerHTML = '<div class="loading-spinner"><div class="spinner"></div></div>';

        try {
            const ytConfig = await API.settings.getYoutube();

            content.innerHTML = `
                <div class="data-card-header" style="background:transparent;border:none;padding:0 0 16px 0;">
                    <span class="data-card-title" style="font-size:18px;">Global Settings</span>
                </div>

                <div class="data-card" style="max-width: 700px; padding: 24px;">
                    <h3 style="margin-top: 0; margin-bottom: 8px; font-size: 16px;">YouTube Integrations</h3>
                    <p style="color: var(--text-muted); font-size: 14px; margin-bottom: 24px; line-height: 1.5;">
                        Configure your Google Cloud OAuth credentials here. These are used globally by Content Farm to authenticate with YouTube and automatically upload generated videos for your channels.
                    </p>

                    <div style="background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: 8px; padding: 16px; margin-bottom: 24px;">
                        <h4 style="margin-top: 0; margin-bottom: 12px; font-size: 14px; color: var(--primary);">🛠 Hướng dẫn chi tiết cách lấy API Key (Client ID / Client Secret):</h4>
                        <ol style="margin: 0; padding-left: 20px; font-size: 13px; color: var(--text-muted); line-height: 1.6;">
                            <li>Truy cập <a href="https://console.cloud.google.com/projectcreate" target="_blank" style="color: var(--primary); text-decoration: none;">Google Cloud Console</a> và tạo một <b>Project mới</b> (dự án).</li>
                            <li>Vào menu tìm <b>APIs & Services</b> (API và Dịch vụ) > <b>Library</b> (Thư viện API). Tra cứu <b>"YouTube Data API v3"</b> và bấm <b>Enable</b> (Bật).</li>
                            <li style="margin-top: 8px; font-weight: 500; color: var(--text-color);">Cấu hình Màn hình chấp thuận (OAuth consent screen):</li>
                            <ul>
                                <li>Vào mục <b>OAuth consent screen</b> ở menu bên trái. Chọn loại người dùng là <b>"External"</b> (Bên ngoài) rồi bấm Create.</li>
                                <li>Ở màn hình <b>App information</b> (Thông tin ứng dụng): 
                                    <br>- <b>App name:</b> Gõ tên gì cũng được (ví dụ: YouTube Auto Uploader).
                                    <br>- <b>User support email:</b> Chọn đúng địa chỉ email Gmail hiện tại của bạn.
                                </li>
                                <li>Kéo tít xuống dưới cùng phần <b>Developer Contact information</b>: Nhập lại địa chỉ email của bạn vào ô đó rồi bấm <b>Save and Continue</b>.</li>
                                <li>Các màn hình tiếp thao (Scopes) thì cứ kệ nó, nhấn <b>Save and Continue</b> tiến tới.</li>
                                <li>Đến màn hình <b>Test users</b> (Người dùng thử nghiệm), bấm nút <b>+ ADD USERS</b> và nhập chính xác <strong style="color: #ef4444;">ĐỊA CHỈ EMAIL CỦA KÊNH YOUTUBE BẠN MUỐN ĐĂNG VIDEO</strong> (rất quan trọng). Cuối cùng bấm Save.</li>
                            </ul>
                            <li style="margin-top: 8px; font-weight: 500; color: var(--text-color);">Tạo Credentials (Thông tin xác thực):</li>
                            <ul>
                                <li>Vào menu <b>Credentials</b> > bấm <b>+ Create Credentials</b> > Chọn <b>OAuth client ID</b>.</li>
                                <li>Mục Application Type chọn: <b>"Web application"</b>. Đặt tên tùy ý.</li>
                                <li>Kéo xuống phần <b>Authorized redirect URIs</b> (URI chuyển hướng...), bạn BẮT BUỘC phải dán đường link này vào ô trống: <code style="background: rgba(0,0,0,0.2); padding: 2px 6px; border-radius: 4px; color: #fff; font-family: monospace;">http://localhost:8080/api/v1/youtube/callback</code></li>
                            </ul>
                            <li style="margin-top: 8px;">Bấm Create xong, một bảng chứa <b>Client ID</b> và <b>Client Secret</b> sẽ hiện ra. Bạn copy và dán 2 dòng đó vào 2 ô bên dưới rồi nhấn <b>Save</b> là xong.</li>
                        </ol>
                    </div>

                    <div class="form-group">
                        <label class="form-label">Client ID</label>
                        <input class="form-input" id="ytClientId" value="${_esc(ytConfig.client_id)}" placeholder="e.g. 123456789-abcdef.apps.googleusercontent.com">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Client Secret</label>
                        <input class="form-input" id="ytClientSecret" type="password" value="${_esc(ytConfig.client_secret)}" placeholder="Leave blank to keep existing secret">
                    </div>
                    
                    <div style="margin-top: 24px;">
                        <button class="btn btn-primary" onclick="SettingsPage.saveYoutubeSettings()">Save Configuration</button>
                    </div>
                </div>
            `;
        } catch (err) {
            content.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><div class="empty-state-text">${err.message}</div></div>`;
        }
    },

    async saveYoutubeSettings() {
        const data = {
            client_id: document.getElementById('ytClientId').value.trim(),
            client_secret: document.getElementById('ytClientSecret').value.trim(),
        };

        if (!data.client_id) {
            return App.toast('Client ID is required', 'error');
        }

        try {
            await API.settings.updateYoutube(data);
            App.toast('YouTube settings saved successfully', 'success');
        } catch (err) {
            App.toast(err.message, 'error');
        }
    }
};
