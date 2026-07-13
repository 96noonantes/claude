import {
  wrapSelection,
  toggleLinePrefix,
  cycleHeading,
  insertBlock,
  TABLE_TEMPLATE,
  CODE_BLOCK_TEMPLATE
} from '../lib/editorActions';

interface ToolButton {
  title: string;
  label: string;
  action: () => void;
}

const buttons: (ToolButton | 'sep')[] = [
  { title: '太字', label: 'B', action: () => wrapSelection('**', '**') },
  { title: '斜体', label: 'I', action: () => wrapSelection('*', '*') },
  { title: '打ち消し線', label: 'S', action: () => wrapSelection('~~', '~~') },
  { title: '見出し(クリックでレベル切替)', label: 'H', action: cycleHeading },
  'sep',
  { title: '箇条書き', label: '•', action: () => toggleLinePrefix('- ', /^- /) },
  {
    title: '番号付きリスト',
    label: '1.',
    action: () => toggleLinePrefix((i) => `${i + 1}. `, /^\d+\. /)
  },
  { title: 'タスクリスト', label: '☑', action: () => toggleLinePrefix('- [ ] ', /^- \[[ xX]\] /) },
  { title: '引用', label: '❝', action: () => toggleLinePrefix('> ', /^> /) },
  'sep',
  { title: 'インラインコード', label: '</>', action: () => wrapSelection('`', '`', 'code') },
  { title: 'コードブロック', label: '{ }', action: () => insertBlock(CODE_BLOCK_TEMPLATE) },
  { title: 'リンク', label: '🔗', action: () => wrapSelection('[', '](https://)', 'リンクテキスト') },
  { title: '画像', label: '🖼', action: () => wrapSelection('![', '](https://)', '代替テキスト') },
  { title: '表', label: '⊞', action: () => insertBlock(TABLE_TEMPLATE) },
  { title: '水平線', label: '—', action: () => insertBlock('---') }
];

export default function Toolbar() {
  return (
    <div className="toolbar" role="toolbar" aria-label="書式ツールバー">
      {buttons.map((b, i) =>
        b === 'sep' ? (
          <span className="toolbar-sep" key={`sep-${i}`} />
        ) : (
          <button
            key={b.title}
            className={`toolbar-btn toolbar-btn-${b.label === 'B' ? 'bold' : b.label === 'I' ? 'italic' : b.label === 'S' ? 'strike' : 'plain'}`}
            title={b.title}
            aria-label={b.title}
            onMouseDown={(e) => e.preventDefault()}
            onClick={b.action}
          >
            {b.label}
          </button>
        )
      )}
    </div>
  );
}
