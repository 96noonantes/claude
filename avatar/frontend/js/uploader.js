/**
 * Image upload handler - drag & drop, file select, clipboard paste
 */

const Uploader = {
    init() {
        const dropZone = document.getElementById('drop-zone');
        const fileInput = document.getElementById('file-input');
        const fileSelectBtn = document.getElementById('file-select-btn');

        // File select button
        fileSelectBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            fileInput.click();
        });

        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleFile(e.target.files[0]);
            }
        });

        // Drop zone click
        dropZone.addEventListener('click', () => fileInput.click());

        // Drag & Drop
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('drag-over');
        });

        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('drag-over');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
            if (e.dataTransfer.files.length > 0) {
                this.handleFile(e.dataTransfer.files[0]);
            }
        });

        // Clipboard paste
        document.addEventListener('paste', (e) => {
            const items = e.clipboardData?.items;
            if (!items) return;
            for (const item of items) {
                if (item.type.startsWith('image/')) {
                    const file = item.getAsFile();
                    if (file) this.handleFile(file);
                    break;
                }
            }
        });
    },

    async handleFile(file) {
        const validTypes = ['image/png', 'image/jpeg', 'image/webp'];
        if (!validTypes.includes(file.type)) {
            App.showToast('PNG、JPG、またはWebP画像を選択してください', 'error');
            return;
        }

        if (file.size > 10 * 1024 * 1024) {
            App.showToast('ファイルサイズは10MB以下にしてください', 'error');
            return;
        }

        // Show preview
        const previewImg = document.getElementById('preview-img');
        previewImg.src = URL.createObjectURL(file);
        document.getElementById('drop-zone').classList.add('hidden');
        document.getElementById('upload-preview').classList.remove('hidden');

        // Upload
        try {
            const formData = new FormData();
            formData.append('file', file);

            const res = await fetch('/api/upload', { method: 'POST', body: formData });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'アップロードに失敗しました');
            }

            const data = await res.json();
            App.sessionId = data.session_id;
            App.showToast('画像をアップロードしました', 'success');
        } catch (e) {
            App.showToast(e.message, 'error');
            this.reset();
        }
    },

    reset() {
        document.getElementById('drop-zone').classList.remove('hidden');
        document.getElementById('upload-preview').classList.add('hidden');
        document.getElementById('file-input').value = '';
        const previewImg = document.getElementById('preview-img');
        if (previewImg.src.startsWith('blob:')) {
            URL.revokeObjectURL(previewImg.src);
        }
        previewImg.src = '';
    },
};
