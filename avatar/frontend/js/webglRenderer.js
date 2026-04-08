/**
 * WebGL 2.0 mesh renderer for Live2D-style avatar animation.
 *
 * Renders deformable triangle meshes from a texture atlas.
 * Designed for iPhone 15 Safari PWA (60FPS target).
 *
 * Usage:
 *   WebGLRenderer.init(canvas);
 *   WebGLRenderer.loadModel(runtimeData, atlasUrl);
 *   // each frame:
 *   WebGLRenderer.updateParams(AnimEngine.params);
 *   WebGLRenderer.render();
 */

const WebGLRenderer = {
    _gl: null,
    _canvas: null,
    _program: null,
    _atlasTexture: null,
    _parts: [],        // {vao, vertexCount, indexCount, deformers, baseVertices, positionBuffer, depthOrder}
    _modelData: null,
    _canvasW: 0,
    _canvasH: 0,
    _ready: false,

    // Uniform locations
    _loc: {},

    isSupported() {
        try {
            const c = document.createElement('canvas');
            return !!(c.getContext('webgl2'));
        } catch (e) {
            return false;
        }
    },

    init(canvas) {
        this._canvas = canvas;
        const gl = canvas.getContext('webgl2', {
            alpha: true,
            premultipliedAlpha: false,
            antialias: true,
            preserveDrawingBuffer: false,
        });
        if (!gl) return false;
        this._gl = gl;

        // Compile shaders
        const vs = gl.createShader(gl.VERTEX_SHADER);
        gl.shaderSource(vs, VERTEX_SHADER);
        gl.compileShader(vs);
        if (!gl.getShaderParameter(vs, gl.COMPILE_STATUS)) {
            console.error('VS:', gl.getShaderInfoLog(vs));
            return false;
        }

        const fs = gl.createShader(gl.FRAGMENT_SHADER);
        gl.shaderSource(fs, FRAGMENT_SHADER);
        gl.compileShader(fs);
        if (!gl.getShaderParameter(fs, gl.COMPILE_STATUS)) {
            console.error('FS:', gl.getShaderInfoLog(fs));
            return false;
        }

        const prog = gl.createProgram();
        gl.attachShader(prog, vs);
        gl.attachShader(prog, fs);
        gl.linkProgram(prog);
        if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
            console.error('Link:', gl.getProgramInfoLog(prog));
            return false;
        }
        this._program = prog;

        // Cache uniform locations
        this._loc = {
            u_atlas: gl.getUniformLocation(prog, 'u_atlas'),
            u_resolution: gl.getUniformLocation(prog, 'u_resolution'),
            u_partOffset: gl.getUniformLocation(prog, 'u_partOffset'),
        };

        gl.useProgram(prog);
        gl.uniform1i(this._loc.u_atlas, 0);

        return true;
    },

    async loadModel(runtimeData, atlasUrl) {
        const gl = this._gl;
        if (!gl) return;

        this._modelData = runtimeData;
        this._canvasW = runtimeData.canvas.width;
        this._canvasH = runtimeData.canvas.height;
        this._canvas.width = this._canvasW;
        this._canvas.height = this._canvasH;

        gl.viewport(0, 0, this._canvasW, this._canvasH);
        gl.uniform2f(this._loc.u_resolution, this._canvasW, this._canvasH);

        // Load atlas texture
        await this._loadAtlasTexture(atlasUrl);

        // Create VAOs for each part
        this._parts = [];
        const sorted = [...runtimeData.parts].sort((a, b) => a.depth_order - b.depth_order);

        for (const partData of sorted) {
            const mesh = partData.mesh;
            if (!mesh || mesh.vertex_count < 3) continue;

            const vao = gl.createVertexArray();
            gl.bindVertexArray(vao);

            // Base vertices (world space = part position + local vertex)
            const baseVerts = new Float32Array(mesh.vertex_count * 2);
            for (let i = 0; i < mesh.vertex_count; i++) {
                baseVerts[i * 2] = partData.position.x + mesh.vertices[i][0];
                baseVerts[i * 2 + 1] = partData.position.y + mesh.vertices[i][1];
            }

            // Position buffer (will be updated each frame for deformation)
            const posBuf = gl.createBuffer();
            gl.bindBuffer(gl.ARRAY_BUFFER, posBuf);
            gl.bufferData(gl.ARRAY_BUFFER, baseVerts, gl.DYNAMIC_DRAW);
            const aPos = gl.getAttribLocation(this._program, 'a_position');
            gl.enableVertexAttribArray(aPos);
            gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);

            // UV buffer (atlas UVs, static)
            const uvData = new Float32Array(mesh.vertex_count * 2);
            for (let i = 0; i < mesh.vertex_count; i++) {
                uvData[i * 2] = mesh.uvs[i][0];
                uvData[i * 2 + 1] = mesh.uvs[i][1];
            }
            const uvBuf = gl.createBuffer();
            gl.bindBuffer(gl.ARRAY_BUFFER, uvBuf);
            gl.bufferData(gl.ARRAY_BUFFER, uvData, gl.STATIC_DRAW);
            const aUV = gl.getAttribLocation(this._program, 'a_texCoord');
            gl.enableVertexAttribArray(aUV);
            gl.vertexAttribPointer(aUV, 2, gl.FLOAT, false, 0, 0);

            // Index buffer
            const idxData = new Uint16Array(mesh.indices);
            const idxBuf = gl.createBuffer();
            gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, idxBuf);
            gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, idxData, gl.STATIC_DRAW);

            gl.bindVertexArray(null);

            this._parts.push({
                vao,
                positionBuffer: posBuf,
                indexCount: mesh.indices.length,
                vertexCount: mesh.vertex_count,
                baseVertices: baseVerts,
                deformers: partData.deformers || [],
                partData,
            });
        }

        this._ready = true;
    },

    updateParams(params) {
        if (!this._ready) return;
        const gl = this._gl;

        for (const part of this._parts) {
            const deformed = new Float32Array(part.baseVertices);
            const n = part.vertexCount;

            for (const def of part.deformers) {
                const paramVal = params[def.param] || 0;
                if (Math.abs(paramVal) < 0.001) continue;

                const px = part.partData.position.x + def.pivot[0] * part.partData.size.w;
                const py = part.partData.position.y + def.pivot[1] * part.partData.size.h;
                const pw = part.partData.size.w;
                const ph = part.partData.size.h;

                for (let i = 0; i < n; i++) {
                    const w = (def.weights && def.weights[i] !== undefined) ? def.weights[i] : 1.0;
                    if (w < 0.001) continue;

                    const vx = deformed[i * 2];
                    const vy = deformed[i * 2 + 1];
                    const influence = paramVal * def.scale * w;

                    if (def.type === 'rotation') {
                        const rad = influence * Math.PI / 180;
                        const dx = vx - px;
                        const dy = vy - py;
                        const c = Math.cos(rad);
                        const s = Math.sin(rad);
                        deformed[i * 2] = px + dx * c - dy * s;
                        deformed[i * 2 + 1] = py + dx * s + dy * c;
                    } else if (def.type === 'scale_y') {
                        const dy = vy - py;
                        deformed[i * 2 + 1] = py + dy * (1.0 + influence);
                    } else if (def.type === 'scale_x') {
                        const dx = vx - px;
                        deformed[i * 2] = px + dx * (1.0 + influence);
                    } else if (def.type === 'translate_x') {
                        deformed[i * 2] += influence * pw;
                    } else if (def.type === 'translate_y') {
                        deformed[i * 2 + 1] += influence * ph;
                    } else if (def.type === 'chain') {
                        // Chain: rotation from root, weighted by distance
                        const rad = influence * 0.5 * Math.PI / 180;
                        const dx = vx - px;
                        const dy = vy - py;
                        const c = Math.cos(rad);
                        const s = Math.sin(rad);
                        deformed[i * 2] = px + dx * c - dy * s;
                        deformed[i * 2 + 1] = py + dx * s + dy * c;
                        // Additional horizontal sway for chain tip
                        deformed[i * 2] += influence * w * 0.3;
                    }
                }
            }

            // Upload deformed vertices to GPU
            gl.bindBuffer(gl.ARRAY_BUFFER, part.positionBuffer);
            gl.bufferSubData(gl.ARRAY_BUFFER, 0, deformed);
        }
    },

    render() {
        if (!this._ready) return;
        const gl = this._gl;

        gl.clearColor(0, 0, 0, 0);
        gl.clear(gl.COLOR_BUFFER_BIT);

        gl.enable(gl.BLEND);
        gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

        gl.useProgram(this._program);
        gl.activeTexture(gl.TEXTURE0);
        gl.bindTexture(gl.TEXTURE_2D, this._atlasTexture);

        for (const part of this._parts) {
            gl.bindVertexArray(part.vao);
            gl.drawElements(gl.TRIANGLES, part.indexCount, gl.UNSIGNED_SHORT, 0);
        }

        gl.bindVertexArray(null);
    },

    dispose() {
        const gl = this._gl;
        if (!gl) return;
        for (const part of this._parts) {
            gl.deleteVertexArray(part.vao);
        }
        if (this._atlasTexture) gl.deleteTexture(this._atlasTexture);
        if (this._program) gl.deleteProgram(this._program);
        this._parts = [];
        this._ready = false;
    },

    async _loadAtlasTexture(url) {
        const gl = this._gl;
        return new Promise((resolve) => {
            const img = new Image();
            img.crossOrigin = 'anonymous';
            img.onload = () => {
                const tex = gl.createTexture();
                gl.activeTexture(gl.TEXTURE0);
                gl.bindTexture(gl.TEXTURE_2D, tex);
                gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
                gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
                gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
                gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
                gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
                this._atlasTexture = tex;
                resolve();
            };
            img.onerror = resolve;
            img.src = url;
        });
    },
};

// --- GLSL Shaders ---

const VERTEX_SHADER = `#version 300 es
precision highp float;

in vec2 a_position;
in vec2 a_texCoord;

uniform vec2 u_resolution;

out vec2 v_texCoord;

void main() {
    // Convert pixel coords to clip space (-1 to 1)
    vec2 clipSpace = (a_position / u_resolution) * 2.0 - 1.0;
    // Flip Y (canvas Y goes down, GL Y goes up)
    clipSpace.y = -clipSpace.y;
    gl_Position = vec4(clipSpace, 0.0, 1.0);
    v_texCoord = a_texCoord;
}
`;

const FRAGMENT_SHADER = `#version 300 es
precision mediump float;

uniform sampler2D u_atlas;
in vec2 v_texCoord;
out vec4 fragColor;

void main() {
    fragColor = texture(u_atlas, v_texCoord);
    if (fragColor.a < 0.01) discard;
}
`;
