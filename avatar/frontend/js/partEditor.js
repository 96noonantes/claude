/**
 * Part editor - displays decomposed parts list and canvas overlay
 */

const PartEditor = {
    showOverlay: true,
    showOriginal: false,
    partImages: {},

    init() {
        document.getElementById('toggle-overlay').addEventListener('click', () => {
            this.showOverlay = !this.showOverlay;
            this.drawCanvas();
        });

        document.getElementById('toggle-original').addEventListener('click', () => {
            this.showOriginal = !this.showOriginal;
            this.drawCanvas();
        });
    },

    renderParts(parts) {
        const list = document.getElementById('parts-list');
        list.innerHTML = '';

        // Show detected gender badge
        const genderBadge = document.getElementById('gender-badge');
        const genders = parts.map(p => p.gender).filter(g => g && g !== 'unisex');
        if (genders.length > 0) {
            const majorGender = genders.filter(g => g === 'female').length >= genders.filter(g => g === 'male').length ? 'female' : 'male';
            genderBadge.textContent = majorGender === 'female' ? '♀ 女性キャラ' : '♂ 男性キャラ';
            genderBadge.className = `gender-badge ${majorGender}`;
            genderBadge.classList.remove('hidden');
        } else {
            genderBadge.classList.add('hidden');
        }

        // Filter parts by gender
        const filter = App.genderFilter;
        const filteredParts = filter === 'all' ? parts : parts.filter(p =>
            p.gender === filter || p.gender === 'unisex' || !p.gender
        );

        for (const part of filteredParts) {
            const item = document.createElement('div');
            item.className = `part-item${part.id === App.selectedPartId ? ' selected' : ''}${!part.visible ? ' hidden-part' : ''}`;

            const categoryBadge = part.category ? `<span class="category-badge">${_categoryName(part.category)}</span>` : '';
            const genderTag = part.gender && part.gender !== 'unisex'
                ? `<span class="gender-tag ${part.gender}">${part.gender === 'female' ? '♀' : '♂'}</span>`
                : part.gender === 'unisex' ? `<span class="gender-tag unisex">⚥</span>` : '';

            item.innerHTML = `
                <img class="part-thumbnail" src="${part.image_url}" alt="${part.label_ja}">
                <div class="part-info">
                    <div class="part-label">${part.label_ja}</div>
                    <div class="part-badges">${categoryBadge}${genderTag}</div>
                </div>
                <button class="part-toggle ${part.visible ? 'visible' : ''}" data-part-id="${part.id}" title="${part.visible ? '非表示にする' : '表示する'}">
                    ${part.visible ? eyeOpenSVG : eyeClosedSVG}
                </button>
            `;

            item.addEventListener('click', (e) => {
                if (!e.target.closest('.part-toggle')) {
                    App.selectPart(part.id);
                }
            });

            const toggleBtn = item.querySelector('.part-toggle');
            toggleBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                App.togglePartVisibility(part.id);
            });

            list.appendChild(item);
        }

        this.loadPartImages(parts);
    },

    async loadPartImages(parts) {
        const promises = parts.map(part => {
            if (this.partImages[part.id]) return Promise.resolve();
            return new Promise((resolve) => {
                const img = new Image();
                img.onload = () => {
                    this.partImages[part.id] = img;
                    resolve();
                };
                img.onerror = resolve;
                img.src = part.image_url;
            });
        });

        await Promise.all(promises);
        this.drawCanvas();
    },

    drawCanvas() {
        const canvas = document.getElementById('editor-canvas');
        const ctx = canvas.getContext('2d');

        if (App.parts.length === 0) return;

        const visibleParts = App.parts.filter(p => p.visible);
        const allParts = App.parts;
        const maxX = allParts.reduce((m, p) => Math.max(m, p.bounds.x + p.bounds.width), 0);
        const maxY = allParts.reduce((m, p) => Math.max(m, p.bounds.y + p.bounds.height), 0);
        canvas.width = maxX + 20;
        canvas.height = maxY + 20;

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Draw original image if toggled (cached to avoid flicker)
        if (this.showOriginal && App.sessionId) {
            if (!this._originalImage) {
                this._originalImage = new Image();
                this._originalImage.onload = () => this.drawCanvas();
                this._originalImage.src = `/workspace/${App.sessionId}/original.png`;
                return;
            }
            if (!this._originalImage.complete) return;
            canvas.width = this._originalImage.width;
            canvas.height = this._originalImage.height;
            ctx.drawImage(this._originalImage, 0, 0);
            if (this.showOverlay) this._drawOverlay(ctx);
            return;
        }

        // Draw parts in depth order
        const sorted = [...App.parts].sort((a, b) => a.depth_order - b.depth_order);
        for (const part of sorted) {
            if (!part.visible) continue;
            const img = this.partImages[part.id];
            if (!img) continue;
            ctx.drawImage(img, part.bounds.x, part.bounds.y, part.bounds.width, part.bounds.height);
        }

        if (this.showOverlay) this._drawOverlay(ctx);
    },

    _drawOverlay(ctx) {
        const colors = [
            'rgba(99,102,241,0.3)', 'rgba(244,114,182,0.3)', 'rgba(52,211,153,0.3)',
            'rgba(251,191,36,0.3)', 'rgba(248,113,113,0.3)', 'rgba(96,165,250,0.3)',
            'rgba(167,139,250,0.3)', 'rgba(45,212,191,0.3)', 'rgba(251,146,60,0.3)',
        ];

        App.parts.forEach((part, i) => {
            if (!part.visible) return;
            const { x, y, width, height } = part.bounds;
            const isSelected = part.id === App.selectedPartId;

            ctx.fillStyle = colors[i % colors.length];
            ctx.fillRect(x, y, width, height);

            ctx.strokeStyle = isSelected ? '#6366f1' : 'rgba(255,255,255,0.4)';
            ctx.lineWidth = isSelected ? 2 : 1;
            ctx.strokeRect(x, y, width, height);

            ctx.fillStyle = isSelected ? '#6366f1' : 'rgba(0,0,0,0.6)';
            ctx.fillRect(x, y, Math.min(width, 100), 18);
            ctx.fillStyle = '#fff';
            ctx.font = '11px sans-serif';
            ctx.fillText(part.label_ja, x + 3, y + 13);
        });
    },
};

const CATEGORY_NAMES = {
    hair: '髪', body: '体', face: '顔', limb: '四肢',
    tops: 'トップス', bottoms_skirt: 'スカート', bottoms_pants: 'パンツ',
    one_piece: 'ワンピース', outer: 'アウター',
    underwear_top: '下着(上)', underwear_bottom: '下着(下)',
    socks: '靴下', shoes: '靴', hat: '帽子', collar: '襟',
    gloves: '手袋', sleeve: '袖', accessory: 'アクセサリー', costume: '衣装',
};

function _categoryName(cat) {
    return CATEGORY_NAMES[cat] || cat;
}

const eyeOpenSVG = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
    <circle cx="12" cy="12" r="3"/>
</svg>`;

const eyeClosedSVG = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
    <line x1="1" y1="1" x2="23" y2="23"/>
</svg>`;
