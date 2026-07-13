/** エディタ⇔プレビューのスクロール同期(比率ベース) */

let editorScroller: HTMLElement | null = null;
let previewScroller: HTMLElement | null = null;
let lockSource: 'editor' | 'preview' | null = null;
let lockTimer: ReturnType<typeof setTimeout> | null = null;

function acquireLock(source: 'editor' | 'preview'): boolean {
  if (lockSource && lockSource !== source) return false;
  lockSource = source;
  if (lockTimer) clearTimeout(lockTimer);
  lockTimer = setTimeout(() => (lockSource = null), 120);
  return true;
}

function ratioOf(el: HTMLElement): number {
  const max = el.scrollHeight - el.clientHeight;
  return max > 0 ? el.scrollTop / max : 0;
}

function applyRatio(el: HTMLElement, ratio: number) {
  const max = el.scrollHeight - el.clientHeight;
  el.scrollTop = ratio * max;
}

export function registerEditorScroller(el: HTMLElement | null) {
  editorScroller = el;
}

export function registerPreviewScroller(el: HTMLElement | null) {
  previewScroller = el;
}

export function onEditorScroll() {
  if (!editorScroller || !previewScroller) return;
  if (!acquireLock('editor')) return;
  applyRatio(previewScroller, ratioOf(editorScroller));
}

export function onPreviewScroll() {
  if (!editorScroller || !previewScroller) return;
  if (!acquireLock('preview')) return;
  applyRatio(editorScroller, ratioOf(previewScroller));
}
