/**
 * Live preview renderer - animates decomposed parts in real-time.
 *
 * Each part is rendered as a sprite on Canvas, with transforms driven
 * by AnimEngine parameters (blink, breath, head sway, hair physics, etc.).
 */

const Preview = {
    _running: false,
    _rafId: null,
    _lastTime: 0,
    _canvas: null,
    _ctx: null,
    _sprites: {},  // label → Image
    _parts: [],
    _canvasW: 0,
    _canvasH: 0,

    init() {
        AnimEngine.init();
    },

    /**
     * Start the live preview animation loop.
     */
    start(parts) {
        this._parts = parts;
        this._canvas = document.getElementById('preview-canvas');
        this._ctx = this._canvas.getContext('2d');

        // Compute canvas size from parts
        let maxX = 0, maxY = 0;
        for (const p of parts) {
            maxX = Math.max(maxX, p.bounds.x + p.bounds.width);
            maxY = Math.max(maxY, p.bounds.y + p.bounds.height);
        }
        this._canvasW = maxX + 20;
        this._canvasH = maxY + 20;
        this._canvas.width = this._canvasW;
        this._canvas.height = this._canvasH;

        // Load all part images
        this._loadSprites(parts).then(() => {
            this._running = true;
            this._lastTime = performance.now();
            this._tick();
        });
    },

    stop() {
        this._running = false;
        if (this._rafId) {
            cancelAnimationFrame(this._rafId);
            this._rafId = null;
        }
    },

    renderParts(parts) {
        // Called by App when parts change — if preview is running, reload
        if (this._running) {
            this._parts = parts;
            this._loadSprites(parts);
        }
    },

    highlightPart() {},

    async _loadSprites(parts) {
        const promises = parts.map(part => {
            return new Promise(resolve => {
                if (this._sprites[part.label]) { resolve(); return; }
                const img = new Image();
                img.onload = () => { this._sprites[part.label] = img; resolve(); };
                img.onerror = resolve;
                img.src = part.image_url;
            });
        });
        await Promise.all(promises);
    },

    _tick() {
        if (!this._running) return;

        const now = performance.now();
        const dt = Math.min((now - this._lastTime) / 1000, 0.05); // cap at 50ms
        this._lastTime = now;

        AnimEngine.update(dt);
        this._render();

        this._rafId = requestAnimationFrame(() => this._tick());
    },

    _render() {
        const ctx = this._ctx;
        const p = AnimEngine.params;

        ctx.clearRect(0, 0, this._canvasW, this._canvasH);

        // Sort parts by depth
        const sorted = [...this._parts]
            .filter(part => part.visible)
            .sort((a, b) => a.depth_order - b.depth_order);

        for (const part of sorted) {
            const img = this._sprites[part.label];
            if (!img) continue;

            const bx = part.bounds.x;
            const by = part.bounds.y;
            const bw = part.bounds.width;
            const bh = part.bounds.height;

            // Compute center of this part
            const cx = bx + bw / 2;
            const cy = by + bh / 2;

            // Compute transform based on part type and animation params
            const t = this._getTransform(part.label, p, cx, cy, bw, bh);

            ctx.save();

            // Apply transform: translate to pivot, rotate, scale, translate back
            ctx.translate(cx + t.tx, cy + t.ty);
            ctx.rotate(t.rotation);
            ctx.scale(t.sx, t.sy);
            ctx.globalAlpha = t.alpha;
            ctx.drawImage(img, -bw / 2, -bh / 2, bw, bh);

            ctx.restore();
        }
    },

    /**
     * Compute per-part transform from animation parameters.
     */
    _getTransform(label, p, cx, cy, bw, bh) {
        const t = { tx: 0, ty: 0, sx: 1.0, sy: 1.0, rotation: 0, alpha: 1.0 };
        const deg = Math.PI / 180;

        // === Head group: face, eyes, eyebrows, nose, mouth, ears ===
        const isHead = label.startsWith('face') || label.startsWith('eye') ||
                       label.startsWith('iris') || label.startsWith('eyebrow') ||
                       label === 'nose' || label === 'mouth' ||
                       label.startsWith('ear') || label === 'neck';

        if (isHead) {
            // Head rotation (parallax effect)
            t.tx += p.angleX * 0.5;
            t.ty += p.angleY * 0.3;
            t.rotation += p.angleZ * 0.3 * deg;
        }

        // === Eyes: blink (scale Y to 0) ===
        if (label === 'eye_left' || label === 'eye_white_left' || label === 'iris_left') {
            t.sy *= p.eyeLOpen;
            if (p.eyeLSmile > 0) {
                t.sy *= (1.0 - p.eyeLSmile * 0.3); // smile narrows eyes
                t.ty += p.eyeLSmile * bh * 0.1;     // eyes curve up when smiling
            }
        }
        if (label === 'eye_right' || label === 'eye_white_right' || label === 'iris_right') {
            t.sy *= p.eyeROpen;
            if (p.eyeRSmile > 0) {
                t.sy *= (1.0 - p.eyeRSmile * 0.3);
                t.ty += p.eyeRSmile * bh * 0.1;
            }
        }

        // === Iris: eye ball tracking ===
        if (label === 'iris_left' || label === 'iris_right') {
            t.tx += p.eyeBallX * bw * 0.15;
            t.ty += p.eyeBallY * bh * 0.1;
        }

        // === Eyebrows ===
        if (label === 'eyebrow_left') {
            t.ty += p.browLY * bh * 0.3;
            t.rotation += p.browLAngle * 5 * deg;
        }
        if (label === 'eyebrow_right') {
            t.ty += p.browRY * bh * 0.3;
            t.rotation += -p.browRAngle * 5 * deg;
        }

        // === Mouth ===
        if (label === 'mouth') {
            t.sy *= (1.0 + p.mouthOpenY * 0.5);
            t.sx *= (1.0 + p.mouthForm * 0.15);
            t.ty += p.mouthOpenY * bh * 0.15;
        }

        // === Body: breathing ===
        if (label === 'body' || label === 'body_skin') {
            t.sy *= (1.0 + p.breath * 0.015);
            t.tx += p.bodyAngleX * 0.3;
        }
        if (label === 'neck') {
            t.tx += p.bodyAngleX * 0.2;
        }

        // === Outerwear follows body ===
        if (label === 'outerwear_upper' || label.startsWith('sleeve')) {
            t.sy *= (1.0 + p.breath * 0.01);
            t.tx += p.bodyAngleX * 0.2;
        }

        // === Hair physics: pendulum sway ===
        if (label === 'hair_front') {
            t.rotation += p.hairFront * 0.5 * deg;
            t.tx += p.hairFront * 0.3;
        }
        if (label === 'hair_back') {
            t.rotation += p.hairBack * 0.4 * deg;
            t.tx += p.hairBack * 0.2;
        }
        if (label === 'hair_side_left') {
            t.rotation += p.hairSideL * 0.6 * deg;
            t.tx += p.hairSideL * 0.4;
        }
        if (label === 'hair_side_right') {
            t.rotation += p.hairSideR * 0.6 * deg;
            t.tx += p.hairSideR * 0.4;
        }

        // === Skirt physics ===
        if (label === 'outerwear_lower') {
            t.rotation += p.skirtCenter * 0.4 * deg;
            t.tx += p.skirtCenter * 0.3;
        }

        // === Arms: subtle body-following sway ===
        if (label.includes('arm') || label.includes('upper_arm') ||
            label.includes('forearm') || label.includes('hand') || label.includes('fingers')) {
            t.tx += p.bodyAngleX * 0.15;
            // Pendulum: arms swing opposite to body
            const armSwing = Math.sin(AnimEngine._time * 0.6) * 1.5;
            if (label.includes('left')) t.rotation += armSwing * deg;
            if (label.includes('right')) t.rotation -= armSwing * deg;
        }

        // === Legs: minimal sway ===
        if (label.includes('thigh') || label.includes('shin') ||
            label.includes('foot') || label.includes('leg')) {
            t.tx += p.bodyAngleX * 0.1;
        }

        // Clamp scale to prevent flip
        t.sy = Math.max(0.01, t.sy);
        t.sx = Math.max(0.01, t.sx);

        return t;
    },
};
