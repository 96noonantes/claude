import { useEffect, useRef } from 'react';
import { EditorState } from '@codemirror/state';
import {
  EditorView,
  keymap,
  lineNumbers,
  highlightActiveLine,
  drawSelection,
  placeholder
} from '@codemirror/view';
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands';
import { markdown, markdownLanguage } from '@codemirror/lang-markdown';
import { languages } from '@codemirror/language-data';
import { syntaxHighlighting, HighlightStyle } from '@codemirror/language';
import { searchKeymap, highlightSelectionMatches } from '@codemirror/search';
import { tags } from '@lezer/highlight';
import { useDocuments } from '../store/documents';
import { setEditorView } from '../lib/editorRef';
import { registerEditorScroller, onEditorScroll } from '../lib/scrollSync';

const markdownHighlight = HighlightStyle.define([
  { tag: tags.heading1, fontSize: '1.5em', fontWeight: 'bold', color: 'var(--md-heading)' },
  { tag: tags.heading2, fontSize: '1.3em', fontWeight: 'bold', color: 'var(--md-heading)' },
  { tag: tags.heading3, fontSize: '1.15em', fontWeight: 'bold', color: 'var(--md-heading)' },
  { tag: [tags.heading4, tags.heading5, tags.heading6], fontWeight: 'bold', color: 'var(--md-heading)' },
  { tag: tags.strong, fontWeight: 'bold' },
  { tag: tags.emphasis, fontStyle: 'italic' },
  { tag: tags.strikethrough, textDecoration: 'line-through' },
  { tag: tags.link, color: 'var(--accent)' },
  { tag: tags.url, color: 'var(--accent)' },
  { tag: tags.monospace, color: 'var(--md-code)' },
  { tag: tags.quote, color: 'var(--md-quote)' },
  { tag: tags.list, color: 'var(--md-list-marker)' },
  { tag: tags.meta, color: 'var(--text-muted)' },
  { tag: tags.processingInstruction, color: 'var(--text-muted)' },
  { tag: tags.comment, color: 'var(--text-muted)', fontStyle: 'italic' }
]);

const editorTheme = EditorView.theme({
  '&': { height: '100%', fontSize: '15px', backgroundColor: 'transparent' },
  '.cm-scroller': {
    fontFamily: "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace",
    lineHeight: '1.7',
    overflow: 'auto'
  },
  '.cm-content': {
    padding: '24px 32px 50vh',
    maxWidth: '860px',
    margin: '0 auto',
    caretColor: 'var(--accent)'
  },
  '&.cm-focused': { outline: 'none' },
  '.cm-line': { padding: '0 2px' },
  '.cm-gutters': {
    backgroundColor: 'transparent',
    color: 'var(--text-muted)',
    border: 'none',
    paddingLeft: '8px'
  },
  '.cm-activeLine': { backgroundColor: 'var(--editor-active-line)' },
  '.cm-cursor': { borderLeftColor: 'var(--accent)' },
  '.cm-selectionBackground, &.cm-focused .cm-selectionBackground': {
    backgroundColor: 'var(--editor-selection) !important'
  }
});

export default function Editor() {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);
  const currentId = useDocuments((s) => s.currentId);
  const currentIdRef = useRef(currentId);
  currentIdRef.current = currentId;

  // EditorView は1度だけ生成する
  useEffect(() => {
    if (!containerRef.current) return;
    const view = new EditorView({
      state: makeState(''),
      parent: containerRef.current
    });
    viewRef.current = view;
    setEditorView(view);
    registerEditorScroller(view.scrollDOM);
    view.scrollDOM.addEventListener('scroll', onEditorScroll, { passive: true });

    return () => {
      view.scrollDOM.removeEventListener('scroll', onEditorScroll);
      registerEditorScroller(null);
      setEditorView(null);
      view.destroy();
      viewRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ドキュメント切替時に内容を差し替える
  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;
    const doc = useDocuments.getState().docs.find((d) => d.id === currentId);
    const content = doc?.content ?? '';
    if (view.state.doc.toString() !== content) {
      view.setState(makeState(content));
      view.scrollDOM.scrollTop = 0;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentId]);

  function makeState(content: string): EditorState {
    return EditorState.create({
      doc: content,
      extensions: [
        lineNumbers(),
        history(),
        drawSelection(),
        highlightActiveLine(),
        highlightSelectionMatches(),
        EditorView.lineWrapping,
        markdown({ base: markdownLanguage, codeLanguages: languages }),
        syntaxHighlighting(markdownHighlight),
        editorTheme,
        placeholder('Markdown を入力...'),
        keymap.of([...defaultKeymap, ...historyKeymap, ...searchKeymap, indentWithTab]),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) {
            const id = currentIdRef.current;
            if (id) {
              useDocuments.getState().setContent(id, update.state.doc.toString());
            }
          }
        })
      ]
    });
  }

  return <div className="editor-pane" ref={containerRef} />;
}
