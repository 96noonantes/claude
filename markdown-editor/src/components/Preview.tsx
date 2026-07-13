import { useEffect, useMemo, useRef } from 'react';
import { useDocuments } from '../store/documents';
import { renderMarkdown } from '../lib/markdown';
import { registerPreviewScroller, onPreviewScroll } from '../lib/scrollSync';
import 'highlight.js/styles/github.css';

export default function Preview() {
  const containerRef = useRef<HTMLDivElement>(null);
  const content = useDocuments((s) => {
    const doc = s.docs.find((d) => d.id === s.currentId);
    return doc?.content ?? '';
  });

  const html = useMemo(() => renderMarkdown(content), [content]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    registerPreviewScroller(el);
    el.addEventListener('scroll', onPreviewScroll, { passive: true });
    return () => {
      el.removeEventListener('scroll', onPreviewScroll);
      registerPreviewScroller(null);
    };
  }, []);

  return (
    <div className="preview-pane" ref={containerRef}>
      <article className="markdown-body" dangerouslySetInnerHTML={{ __html: html }} />
    </div>
  );
}
