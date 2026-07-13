import type { EditorView } from '@codemirror/view';

/** Toolbar などから現在の CodeMirror インスタンスへアクセスするための参照 */
let currentView: EditorView | null = null;

export function setEditorView(view: EditorView | null) {
  currentView = view;
}

export function getEditorView(): EditorView | null {
  return currentView;
}
