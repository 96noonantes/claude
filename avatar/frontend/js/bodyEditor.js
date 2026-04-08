/**
 * Body profile editor - sliders for height, proportions, colors.
 * Sends updates to API and applies real-time preview scaling.
 */

const BodyEditor = {
    _baseProfile: null,  // Original measured profile
    _scales: { height: 1, shoulder: 1, waist: 1, hip: 1, leg: 1 },
    _debounceTimer: null,

    init() {
        const sliders = [
            { id: 'body-height', key: 'height' },
            { id: 'body-shoulder', key: 'shoulder' },
            { id: 'body-waist', key: 'waist' },
            { id: 'body-hip', key: 'hip' },
            { id: 'body-leg', key: 'leg' },
        ];

        for (const { id, key } of sliders) {
            const el = document.getElementById(id);
            const valEl = document.getElementById(`${id}-val`);
            if (!el || !valEl) continue;
            el.addEventListener('input', () => {
                const val = parseFloat(el.value);
                valEl.textContent = val.toFixed(2);
                this._scales[key] = val;
                this._applyToPreview();
                this._debounceSave();
            });
        }

        // Color pickers
        const hairColorEl = document.getElementById('hair-color');
        if (hairColorEl) {
            hairColorEl.addEventListener('input', () => {
                this._applyToPreview();
                this._debounceSave();
            });
        }

        const skinColorEl = document.getElementById('skin-color');
        if (skinColorEl) {
            skinColorEl.addEventListener('input', () => {
                this._applyToPreview();
                this._debounceSave();
            });
        }
    },

    /**
     * Load the measured body profile from the server and set slider defaults.
     */
    async loadProfile() {
        if (!App.sessionId) return;

        try {
            const res = await fetch(`/api/body-profile/${App.sessionId}`);
            if (!res.ok) return;
            this._baseProfile = await res.json();

            // Set color pickers to measured values
            if (this._baseProfile.hair_color) {
                const [r, g, b] = this._baseProfile.hair_color;
                const hex = '#' + [r, g, b].map(c => c.toString(16).padStart(2, '0')).join('');
                const el = document.getElementById('hair-color');
                if (el) el.value = hex;
            }
            if (this._baseProfile.skin_color) {
                const [r, g, b] = this._baseProfile.skin_color;
                const hex = '#' + [r, g, b].map(c => c.toString(16).padStart(2, '0')).join('');
                const el = document.getElementById('skin-color');
                if (el) el.value = hex;
            }
        } catch (e) {
            // Silently fail
        }
    },

    /**
     * Apply current scales to the preview renderer.
     */
    _applyToPreview() {
        if (typeof Preview !== 'undefined' && Preview._running) {
            Preview.bodyScales = { ...this._scales };

            // Parse colors
            const hairHex = document.getElementById('hair-color')?.value || '#808080';
            const skinHex = document.getElementById('skin-color')?.value || '#f0d2b4';
            Preview.hairColor = _hexToRgb(hairHex);
            Preview.skinColor = _hexToRgb(skinHex);
        }
    },

    /**
     * Debounced save to server.
     */
    _debounceSave() {
        clearTimeout(this._debounceTimer);
        this._debounceTimer = setTimeout(() => this._saveToServer(), 500);
    },

    async _saveToServer() {
        if (!App.sessionId || !this._baseProfile) return;

        const hairHex = document.getElementById('hair-color')?.value || '#808080';
        const skinHex = document.getElementById('skin-color')?.value || '#f0d2b4';
        const hairRgb = _hexToRgb(hairHex);
        const skinRgb = _hexToRgb(skinHex);

        const body = {
            height: this._baseProfile.height * this._scales.height,
            shoulder_width: this._baseProfile.shoulder_width * this._scales.shoulder,
            waist_width: this._baseProfile.waist_width * this._scales.waist,
            hip_width: this._baseProfile.hip_width * this._scales.hip,
            leg_ratio: this._baseProfile.leg_ratio * this._scales.leg,
            hair_color: hairRgb,
            skin_color: skinRgb,
        };

        try {
            await fetch(`/api/body-profile/${App.sessionId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
        } catch (e) {
            // Silently fail
        }
    },
};

function _hexToRgb(hex) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return [r, g, b];
}
