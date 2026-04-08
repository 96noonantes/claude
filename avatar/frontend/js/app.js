/**
 * Live2D Avatar Generator - Main Application
 */

const App = {
    sessionId: null,
    parts: [],
    selectedPartId: null,

    init() {
        Uploader.init();
        PartEditor.init();
        Preview.init();

        document.getElementById('decompose-btn').addEventListener('click', () => this.startDecompose());
        document.getElementById('reset-btn').addEventListener('click', () => this.reset());
        document.getElementById('export-btn').addEventListener('click', () => this.exportPackage());
        document.getElementById('back-to-upload').addEventListener('click', () => this.showStep('upload'));
    },

    showStep(step) {
        document.querySelectorAll('.step').forEach(el => el.classList.add('hidden'));
        document.getElementById(`${step}-section`).classList.remove('hidden');
    },

    showToast(message, type = 'info') {
        const toast = document.getElementById('toast');
        toast.textContent = message;
        toast.className = `toast ${type}`;
        toast.classList.remove('hidden');
        setTimeout(() => toast.classList.add('hidden'), 3000);
    },

    async startDecompose() {
        if (!this.sessionId) return;

        this.showStep('loading');

        try {
            const res = await fetch(`/api/decompose/${this.sessionId}`, { method: 'POST' });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || '分解に失敗しました');
            }

            await this.pollStatus();
        } catch (e) {
            this.showToast(e.message, 'error');
            this.showStep('upload');
        }
    },

    async pollStatus() {
        const maxAttempts = 120;  // 2 minutes max
        for (let i = 0; i < maxAttempts; i++) {
            await new Promise(r => setTimeout(r, 1000));

            try {
                const res = await fetch(`/api/status/${this.sessionId}`);
                const data = await res.json();

                if (data.status === 'done') {
                    await this.loadParts();
                    this.showStep('editor');
                    this.showToast(`${this.parts.length}個のパーツを検出しました`, 'success');
                    return;
                }

                if (data.status === 'error') {
                    throw new Error(data.error_message || 'パーツ分解に失敗しました');
                }
            } catch (e) {
                if (e.message !== 'Failed to fetch') {
                    this.showToast(e.message, 'error');
                    this.showStep('upload');
                    return;
                }
            }
        }

        this.showToast('タイムアウト: 処理に時間がかかりすぎています', 'error');
        this.showStep('upload');
    },

    async loadParts() {
        const res = await fetch(`/api/parts/${this.sessionId}`);
        const data = await res.json();
        this.parts = data.parts;
        PartEditor.renderParts(this.parts);
        Preview.renderParts(this.parts);
    },

    async togglePartVisibility(partId) {
        const part = this.parts.find(p => p.id === partId);
        if (!part) return;

        part.visible = !part.visible;

        try {
            const res = await fetch(`/api/parts/${this.sessionId}/${partId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ visible: part.visible }),
            });
            if (!res.ok) throw new Error();
            PartEditor.renderParts(this.parts);
            Preview.renderParts(this.parts);
        } catch (e) {
            part.visible = !part.visible;  // revert on failure
            this.showToast('パーツの更新に失敗しました', 'error');
        }
    },

    selectPart(partId) {
        this.selectedPartId = partId;
        PartEditor.renderParts(this.parts);
        Preview.highlightPart(partId);
    },

    async exportPackage() {
        if (!this.sessionId) return;

        this.showToast('エクスポートを準備中...', 'info');

        try {
            const res = await fetch(`/api/export/${this.sessionId}`, { method: 'POST' });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'エクスポートに失敗しました');
            }

            const data = await res.json();

            const link = document.createElement('a');
            link.href = data.download_url;
            link.download = data.filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            this.showToast('ZIPファイルをダウンロードしました', 'success');
        } catch (e) {
            this.showToast(e.message, 'error');
        }
    },

    reset() {
        this.sessionId = null;
        this.parts = [];
        this.selectedPartId = null;
        Uploader.reset();
        this.showStep('upload');
    },
};

document.addEventListener('DOMContentLoaded', () => App.init());
