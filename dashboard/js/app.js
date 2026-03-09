/**
 * App Router — Hash-based SPA routing, modal management, and utilities.
 */

const App = {
    pages: {
        '': { title: 'Dashboard', render: () => DashboardPage.render() },
        '/': { title: 'Dashboard', render: () => DashboardPage.render() },
        '/channels': { title: 'Channels', render: () => ChannelsPage.render() },
        '/jobs': { title: 'Video Jobs', render: () => JobsPage.render() },
        '/uploads': { title: 'Uploads', render: () => UploadsPage.render() },
        '/scheduler': { title: 'Scheduler', render: () => SchedulerPage.render() },
        '/logs': { title: 'Logs', render: () => LogsPage.render() },
        '/revenue': { title: 'Revenue Estimation', render: () => RevenuePage.render() },
        '/settings': { title: 'Settings', render: () => SettingsPage.render() },
    },

    init() {
        // Route handling
        window.addEventListener('hashchange', () => this.route());

        // Menu toggle
        document.getElementById('menuToggle').addEventListener('click', () => {
            document.getElementById('sidebar').classList.toggle('open');
        });

        // Modal close
        document.getElementById('modalClose').addEventListener('click', () => this.closeModal());
        document.getElementById('modalOverlay').addEventListener('click', (e) => {
            if (e.target.id === 'modalOverlay') this.closeModal();
        });

        // Clock
        this._updateClock();
        setInterval(() => this._updateClock(), 1000);

        // Initial route
        this.route();
    },

    route() {
        const hash = location.hash.replace('#', '') || '/';
        const path = hash.split('?')[0]; // Strip query params
        const page = this.pages[path];

        if (page) {
            document.getElementById('pageTitle').textContent = page.title;

            // Update nav active state
            document.querySelectorAll('.nav-item').forEach(item => {
                const itemPage = item.getAttribute('data-page');
                const isActive = (
                    (path === '/' && itemPage === 'dashboard') ||
                    (path === '' && itemPage === 'dashboard') ||
                    path === '/' + itemPage
                );
                item.classList.toggle('active', isActive);
            });

            // Close mobile sidebar
            document.getElementById('sidebar').classList.remove('open');

            page.render();
        }
    },

    // ── Modal ────────────────────────────────────────────────────────────────

    openModal(title, bodyHtml) {
        document.getElementById('modalTitle').textContent = title;
        document.getElementById('modalBody').innerHTML = bodyHtml;
        document.getElementById('modalOverlay').classList.add('active');
    },

    closeModal() {
        document.getElementById('modalOverlay').classList.remove('active');
    },

    // ── Toast ────────────────────────────────────────────────────────────────

    toast(message, type = 'info') {
        const container = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(20px)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3500);
    },

    // ── Clock ────────────────────────────────────────────────────────────────

    _updateClock() {
        const now = new Date();
        document.getElementById('timeDisplay').textContent = now.toLocaleString();
    },
};

// ── Global Utilities ─────────────────────────────────────────────────────────

function _esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function _timeAgo(dateStr) {
    if (!dateStr) return '—';
    const date = new Date(dateStr);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
}

// ── Bootstrap ────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => App.init());
