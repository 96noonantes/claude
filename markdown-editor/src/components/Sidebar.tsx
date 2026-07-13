import { useRef, useState } from 'react';
import { useDocuments } from '../store/documents';
import { useToasts } from '../store/toasts';

const PROVIDER_BADGE: Record<string, string> = {
  googleDrive: 'Drive',
  github: 'GitHub',
  dropbox: 'Dropbox'
};

export default function Sidebar() {
  const docs = useDocuments((s) => s.docs);
  const currentId = useDocuments((s) => s.currentId);
  const { select, create, remove, rename } = useDocuments.getState();
  const push = useToasts((s) => s.push);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const sorted = [...docs].sort((a, b) => b.updatedAt - a.updatedAt);

  function commitRename() {
    if (editingId && editingTitle.trim()) {
      rename(editingId, editingTitle.trim());
    }
    setEditingId(null);
  }

  async function handleImport(files: FileList | null) {
    if (!files) return;
    for (const file of Array.from(files)) {
      const content = await file.text();
      create(file.name.replace(/\.(md|markdown|txt)$/i, ''), content);
    }
    if (files.length > 0) push(`${files.length} 件のファイルをインポートしました`, 'success');
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <span className="sidebar-title">ドキュメント</span>
        <div className="sidebar-actions">
          <button
            className="icon-btn"
            title="ファイルをインポート"
            onClick={() => fileInputRef.current?.click()}
          >
            ⬆
          </button>
          <button
            className="icon-btn"
            title="新規ドキュメント"
            onClick={() => create()}
          >
            ＋
          </button>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".md,.markdown,.txt"
          multiple
          hidden
          onChange={(e) => {
            void handleImport(e.target.files);
            e.target.value = '';
          }}
        />
      </div>
      <ul className="doc-list">
        {sorted.map((doc) => (
          <li
            key={doc.id}
            className={`doc-item ${doc.id === currentId ? 'active' : ''}`}
            onClick={() => select(doc.id)}
            onDoubleClick={() => {
              setEditingId(doc.id);
              setEditingTitle(doc.title);
            }}
          >
            {editingId === doc.id ? (
              <input
                className="doc-rename-input"
                value={editingTitle}
                autoFocus
                onChange={(e) => setEditingTitle(e.target.value)}
                onBlur={commitRename}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') commitRename();
                  if (e.key === 'Escape') setEditingId(null);
                }}
                onClick={(e) => e.stopPropagation()}
              />
            ) : (
              <>
                <div className="doc-item-main">
                  <span className="doc-item-title">{doc.title}</span>
                  {doc.remote && (
                    <span className={`doc-badge badge-${doc.remote.provider}`}>
                      {PROVIDER_BADGE[doc.remote.provider]}
                    </span>
                  )}
                </div>
                <button
                  className="doc-delete"
                  title="削除"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm(`「${doc.title}」を削除しますか?この操作は取り消せません。`)) {
                      void remove(doc.id);
                    }
                  }}
                >
                  ×
                </button>
              </>
            )}
          </li>
        ))}
      </ul>
      <div className="sidebar-footer">
        ダブルクリックで名前を変更
      </div>
    </aside>
  );
}
