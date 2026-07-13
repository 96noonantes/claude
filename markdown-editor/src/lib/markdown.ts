import MarkdownIt from 'markdown-it';
import DOMPurify from 'dompurify';
import hljs from 'highlight.js/lib/common';

const md: MarkdownIt = new MarkdownIt({
  html: true,
  linkify: true,
  breaks: false,
  highlight(code: string, lang: string): string {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<pre class="hljs"><code>${hljs.highlight(code, { language: lang }).value}</code></pre>`;
      } catch {
        /* フォールバックへ */
      }
    }
    return `<pre class="hljs"><code>${md.utils.escapeHtml(code)}</code></pre>`;
  }
});

// GFM風タスクリスト: リスト項目先頭の [ ] / [x] をチェックボックスに変換
md.core.ruler.after('inline', 'task-lists', (state) => {
  const tokens = state.tokens;
  for (let i = 2; i < tokens.length; i++) {
    if (
      tokens[i].type !== 'inline' ||
      tokens[i - 1].type !== 'paragraph_open' ||
      tokens[i - 2].type !== 'list_item_open'
    ) {
      continue;
    }
    const first = tokens[i].children?.[0];
    if (!first || first.type !== 'text') continue;
    const match = /^\[( |x|X)\] /.exec(first.content);
    if (!match) continue;
    const checked = match[1].toLowerCase() === 'x';
    first.content = first.content.slice(4);
    const checkbox = new state.Token('html_inline', '', 0);
    checkbox.content = `<input type="checkbox" disabled${checked ? ' checked' : ''} class="task-checkbox"> `;
    tokens[i].children!.unshift(checkbox);
  }
});

export function renderMarkdown(source: string): string {
  const html = md.render(source);
  return DOMPurify.sanitize(html, {
    ADD_ATTR: ['target'],
    // checkbox の disabled/checked を残す
    ADD_TAGS: ['input']
  });
}
