import { EditorSelection } from '@codemirror/state';
import { getEditorView } from './editorRef';

/** 選択範囲を before/after で囲む(選択なしなら placeholder を挿入して選択) */
export function wrapSelection(before: string, after: string, placeholder = 'テキスト') {
  const view = getEditorView();
  if (!view) return;
  const changes = view.state.changeByRange((range) => {
    const text = range.empty ? placeholder : view.state.sliceDoc(range.from, range.to);
    const insert = before + text + after;
    return {
      changes: { from: range.from, to: range.to, insert },
      range: EditorSelection.range(range.from + before.length, range.from + before.length + text.length)
    };
  });
  view.dispatch(changes, { userEvent: 'input' });
  view.focus();
}

/** 選択範囲の各行の先頭にプレフィックスを付与/除去(トグル) */
export function toggleLinePrefix(prefix: string | ((index: number) => string), togglePattern?: RegExp) {
  const view = getEditorView();
  if (!view) return;
  const { state } = view;
  const range = state.selection.main;
  const fromLine = state.doc.lineAt(range.from).number;
  const toLine = state.doc.lineAt(range.to).number;

  const lines = [];
  for (let n = fromLine; n <= toLine; n++) lines.push(state.doc.line(n));

  const allPrefixed = togglePattern ? lines.every((l) => togglePattern.test(l.text)) : false;

  const changes = lines.map((line, i) => {
    if (allPrefixed && togglePattern) {
      const match = togglePattern.exec(line.text)!;
      return { from: line.from, to: line.from + match[0].length, insert: '' };
    }
    const p = typeof prefix === 'string' ? prefix : prefix(i);
    return { from: line.from, to: line.from, insert: p };
  });
  view.dispatch({ changes, userEvent: 'input' });
  view.focus();
}

/** 見出しレベルを循環(なし → # → ## → ### → なし) */
export function cycleHeading() {
  const view = getEditorView();
  if (!view) return;
  const { state } = view;
  const line = state.doc.lineAt(state.selection.main.from);
  const match = /^(#{1,6})\s/.exec(line.text);
  let insert: string;
  let removeLen = 0;
  if (!match) {
    insert = '# ';
  } else if (match[1].length >= 3) {
    insert = '';
    removeLen = match[0].length;
  } else {
    insert = '#'.repeat(match[1].length + 1) + ' ';
    removeLen = match[0].length;
  }
  view.dispatch({
    changes: { from: line.from, to: line.from + removeLen, insert },
    userEvent: 'input'
  });
  view.focus();
}

/** カーソル位置にブロックを挿入(前後に空行を確保) */
export function insertBlock(block: string) {
  const view = getEditorView();
  if (!view) return;
  const { state } = view;
  const range = state.selection.main;
  const line = state.doc.lineAt(range.from);
  const prefix = line.text.trim() === '' ? '' : '\n\n';
  const insert = `${prefix}${block}\n`;
  view.dispatch({
    changes: { from: line.to, to: line.to, insert },
    selection: { anchor: line.to + insert.length },
    userEvent: 'input'
  });
  view.focus();
}

export const TABLE_TEMPLATE = `| 見出し1 | 見出し2 | 見出し3 |
| --- | --- | --- |
| セル | セル | セル |
| セル | セル | セル |`;

export const CODE_BLOCK_TEMPLATE = '```js\n// コードをここに\n```';
