/**
 * Animation engine for Live2D-style sprite deformation.
 *
 * Controls: blink, breath, head sway, hair physics, skirt physics,
 * mouse tracking, lip sync, and expression blending.
 */

const AnimEngine = {
    // Current parameter values
    params: {},

    // Animation toggles
    enabled: {
        blink: true, breath: true, headSway: true,
        hair: true, skirt: true, mouseTrack: true, lipSync: false,
    },

    // Internal state
    _time: 0,
    _blinkTimer: 0,
    _blinkState: 0,      // 0=open, 1=closing, 2=closed, 3=opening
    _blinkPhase: 0,
    _nextBlink: 2.0,
    _mouseX: 0,
    _mouseY: 0,
    _expression: 'neutral',

    init() {
        this._resetParams();

        // Mouse tracking
        document.addEventListener('mousemove', (e) => {
            const canvas = document.getElementById('preview-canvas');
            if (!canvas) return;
            const rect = canvas.getBoundingClientRect();
            this._mouseX = ((e.clientX - rect.left) / rect.width - 0.5) * 2;  // -1 to 1
            this._mouseY = ((e.clientY - rect.top) / rect.height - 0.5) * 2;
        });

        // Bind UI controls
        const bindings = {
            'anim-blink': 'blink', 'anim-breath': 'breath',
            'anim-head-sway': 'headSway', 'anim-hair': 'hair',
            'anim-skirt': 'skirt', 'anim-mouse-track': 'mouseTrack',
            'anim-lip-sync': 'lipSync',
        };
        for (const [id, key] of Object.entries(bindings)) {
            const el = document.getElementById(id);
            if (el) el.addEventListener('change', () => { this.enabled[key] = el.checked; });
        }

        const exprSelect = document.getElementById('expression-select');
        if (exprSelect) {
            exprSelect.addEventListener('change', () => { this._expression = exprSelect.value; });
        }
    },

    _resetParams() {
        this.params = {
            eyeLOpen: 1.0, eyeROpen: 1.0,
            eyeLSmile: 0.0, eyeRSmile: 0.0,
            eyeBallX: 0.0, eyeBallY: 0.0,
            browLY: 0.0, browRY: 0.0,
            browLAngle: 0.0, browRAngle: 0.0,
            mouthOpenY: 0.0, mouthForm: 0.0,
            angleX: 0.0, angleY: 0.0, angleZ: 0.0,
            bodyAngleX: 0.0, bodyAngleY: 0.0,
            breath: 0.0,
            hairFront: 0.0, hairBack: 0.0, hairSideL: 0.0, hairSideR: 0.0,
            skirtCenter: 0.0, skirtL: 0.0, skirtR: 0.0,
            cheek: 0.0, tear: 0.0,
        };
    },

    /**
     * Update all parameters for the current frame.
     * @param {number} dt - Delta time in seconds
     */
    update(dt) {
        this._time += dt;
        this._resetParams();

        if (this.enabled.blink) this._updateBlink(dt);
        if (this.enabled.breath) this._updateBreath(dt);
        if (this.enabled.headSway) this._updateHeadSway(dt);
        if (this.enabled.hair) this._updateHairPhysics(dt);
        if (this.enabled.skirt) this._updateSkirtPhysics(dt);
        if (this.enabled.mouseTrack) this._updateMouseTracking(dt);
        if (this.enabled.lipSync) this._updateLipSync(dt);

        this._applyExpression();
    },

    _updateBlink(dt) {
        this._blinkTimer += dt;
        const duration = 0.15;

        if (this._blinkState === 0) {
            // Open → wait for next blink
            if (this._blinkTimer >= this._nextBlink) {
                this._blinkState = 1;
                this._blinkPhase = 0;
                this._blinkTimer = 0;
                this._nextBlink = 2.5 + Math.random() * 4.0;
            }
            this.params.eyeLOpen = 1.0;
            this.params.eyeROpen = 1.0;
        } else if (this._blinkState === 1) {
            // Closing
            this._blinkPhase += dt / duration;
            if (this._blinkPhase >= 1.0) {
                this._blinkPhase = 1.0;
                this._blinkState = 2;
                this._blinkTimer = 0;
            }
            const v = 1.0 - this._blinkPhase;
            this.params.eyeLOpen = v;
            this.params.eyeROpen = v;
        } else if (this._blinkState === 2) {
            // Closed briefly
            this.params.eyeLOpen = 0.0;
            this.params.eyeROpen = 0.0;
            if (this._blinkTimer > 0.05) {
                this._blinkState = 3;
                this._blinkPhase = 0;
            }
        } else if (this._blinkState === 3) {
            // Opening
            this._blinkPhase += dt / duration;
            if (this._blinkPhase >= 1.0) {
                this._blinkPhase = 1.0;
                this._blinkState = 0;
                this._blinkTimer = 0;
            }
            this.params.eyeLOpen = this._blinkPhase;
            this.params.eyeROpen = this._blinkPhase;
        }
    },

    _updateBreath(dt) {
        this.params.breath = 0.5 + 0.5 * Math.sin(this._time * 1.8);
    },

    _updateHeadSway(dt) {
        this.params.angleX += 3.0 * Math.sin(this._time * 0.7);
        this.params.angleY += 2.0 * Math.sin(this._time * 0.5 + 1.0);
        this.params.angleZ += 1.5 * Math.sin(this._time * 0.3 + 2.0);
        this.params.bodyAngleX += 1.0 * Math.sin(this._time * 0.7);
    },

    _updateHairPhysics(dt) {
        const headX = this.params.angleX;
        // Hair trails behind head movement with delay
        this.params.hairFront = -headX * 0.15 + 2.0 * Math.sin(this._time * 1.2);
        this.params.hairBack = -headX * 0.2 + 3.0 * Math.sin(this._time * 0.8 + 0.5);
        this.params.hairSideL = -headX * 0.12 + 1.5 * Math.sin(this._time * 1.0 + 1.0);
        this.params.hairSideR = headX * 0.12 + 1.5 * Math.sin(this._time * 1.0 + 1.5);
    },

    _updateSkirtPhysics(dt) {
        const bodyX = this.params.bodyAngleX;
        this.params.skirtCenter = -bodyX * 0.3 + 2.0 * Math.sin(this._time * 0.9);
        this.params.skirtL = -bodyX * 0.25 + 1.5 * Math.sin(this._time * 0.85 + 0.3);
        this.params.skirtR = bodyX * 0.25 + 1.5 * Math.sin(this._time * 0.85 + 0.6);
    },

    _updateMouseTracking(dt) {
        const targetX = this._mouseX * 15.0;
        const targetY = this._mouseY * 10.0;
        // Smooth follow
        this.params.angleX += (targetX - this.params.angleX) * 0.08;
        this.params.angleY += (targetY - this.params.angleY) * 0.08;
        // Eye follow (more responsive than head)
        this.params.eyeBallX = this._mouseX * 0.8;
        this.params.eyeBallY = this._mouseY * 0.5;
    },

    _updateLipSync(dt) {
        // Demo lip sync oscillation
        this.params.mouthOpenY = 0.3 + 0.3 * Math.sin(this._time * 8.0)
                               + 0.15 * Math.sin(this._time * 13.0);
        this.params.mouthOpenY = Math.max(0, Math.min(1, this.params.mouthOpenY));
    },

    _applyExpression() {
        const expr = EXPRESSIONS[this._expression];
        if (!expr) return;

        for (const [key, value] of Object.entries(expr)) {
            if (key in this.params) {
                // Blend: expression overrides base value
                this.params[key] = value;
            }
        }
    },
};

// Expression parameter presets (matching model3_generator.py)
const EXPRESSIONS = {
    neutral: {},
    happy: { eyeLSmile: 1.0, eyeRSmile: 1.0, eyeLOpen: 0.7, eyeROpen: 0.7, mouthForm: 1.0, mouthOpenY: 0.3, browLY: 0.3, browRY: 0.3 },
    sad: { eyeLOpen: 0.6, eyeROpen: 0.6, mouthForm: -0.7, browLY: -0.5, browRY: -0.5, browLAngle: -0.6, browRAngle: -0.6, tear: 0.5 },
    angry: { eyeLOpen: 0.9, eyeROpen: 0.9, mouthForm: -0.5, mouthOpenY: 0.2, browLY: -0.3, browRY: -0.3, browLAngle: 0.8, browRAngle: 0.8 },
    surprised: { eyeLOpen: 1.0, eyeROpen: 1.0, mouthOpenY: 0.8, browLY: 0.8, browRY: 0.8 },
    embarrassed: { eyeLSmile: 0.6, eyeRSmile: 0.6, eyeLOpen: 0.5, eyeROpen: 0.5, mouthForm: 0.4, cheek: 1.0, browLY: 0.2, browRY: 0.2 },
    wink_left: { eyeLOpen: 0.0, eyeROpen: 1.0, eyeLSmile: 0.8, mouthForm: 0.7 },
    sleepy: { eyeLOpen: 0.2, eyeROpen: 0.2, mouthOpenY: 0.5, browLY: -0.3, browRY: -0.3 },
    smug: { eyeLOpen: 0.6, eyeROpen: 0.6, eyeLSmile: 0.5, eyeRSmile: 0.5, mouthForm: 0.8, browLY: 0.2, browRY: -0.2, browLAngle: 0.3 },
};
