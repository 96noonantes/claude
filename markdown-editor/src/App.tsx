import { useEffect, useState } from 'react';
import Sidebar from './components/Sidebar';
import Toolbar from './components/Toolbar';
import Editor from './components/Editor';
import Preview from './components/Preview';
import StatusBar from './components/StatusBar';
import SyncMenu from './components/SyncMenu';
import SettingsDialog from './components/SettingsDialog';
import { useDocuments } from './store/documents';
import { useSettings, type ViewMode } from './store/settings';
import { useToasts } from './store/toasts';
import { handleDropboxRedirect } from './sync';

const VIEW_MODES: { id: ViewMode; label: string; title: string }[] = [
  { id: 'editor', label: '✎', title: 'エディタのみ' },
  { id: 'split', label: '◫', title: '分割表示' },
  { id: 'preview', label: '👁', title: 'プレビューのみ' }
];

export default function App() {
  const loaded = useDocuments((s) => s.loaded);
  const doc = useDocuments((s) => s.docs.find((d) => d.id === s.currentId));
  const theme = useSettings((s) => s.theme);
  const viewMode = useSettings((s) => s.viewMode);
  const sidebarOpen = useSettings((s) => s.sidebarOpen);
  const toasts = useToasts((s) => s.toasts);
  const push = useToasts((s) => s.push);

  const [syncOpen, setSyncOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  useEffect(() => {
    void useDocuments.getState().load();
    handleDropboxRedirect()
      .then((connected) => {
        if (connected) {
          push('Dropbox に接続しました', 'success');
          setSyncOpen(true);
        }
      })
      .catch((err) => push(err instanceof Error ? err.message : String(err), 'error'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  if (!loaded) {
    return <div className="app-loading">読み込み中…</div>;
  }

  return (
    <div className="app">
      <header className="topbar">
        <button
          className="icon-btn topbar-btn"
          title="サイドバーを開閉"
          onClick={() => useSettings.getState().toggleSidebar()}
        >
          ☰
        </button>
        <span className="app-logo" aria-hidden="true">
          M↓
        </span>
        <input
          className="doc-title-input"
          value={doc?.title ?? ''}
          placeholder="無題のドキュメント"
          onChange={(e) => doc && useDocuments.getState().rename(doc.id, e.target.value)}
          disabled={!doc}
        />
        <div className="topbar-spacer" />
        <div className="view-switch" role="group" aria-label="表示モード">
          {VIEW_MODES.map((m) => (
            <button
              key={m.id}
              className={`view-btn ${viewMode === m.id ? 'active' : ''}`}
              title={m.title}
              onClick={() => useSettings.getState().setViewMode(m.id)}
            >
              {m.label}
            </button>
          ))}
        </div>
        <button
          className="icon-btn topbar-btn"
          title={theme === 'light' ? 'ダークテーマに切替' : 'ライトテーマに切替'}
          onClick={() => useSettings.getState().setTheme(theme === 'light' ? 'dark' : 'light')}
        >
          {theme === 'light' ? '🌙' : '☀'}
        </button>
        <button
          className="icon-btn topbar-btn"
          title="同期・エクスポート"
          onClick={() => setSyncOpen(true)}
        >
          ☁
        </button>
        <button
          className="icon-btn topbar-btn"
          title="設定"
          onClick={() => setSettingsOpen(true)}
        >
          ⚙
        </button>
      </header>

      <div className="main">
        {sidebarOpen && <Sidebar />}
        <div className="content">
          <Toolbar />
          <div className={`panes mode-${viewMode}`}>
            {viewMode !== 'preview' && <Editor />}
            {viewMode === 'split' && <div className="pane-divider" />}
            {viewMode !== 'editor' && <Preview />}
          </div>
          <StatusBar />
        </div>
      </div>

      {syncOpen && (
        <SyncMenu
          onClose={() => setSyncOpen(false)}
          onOpenSettings={() => {
            setSyncOpen(false);
            setSettingsOpen(true);
          }}
        />
      )}
      {settingsOpen && <SettingsDialog onClose={() => setSettingsOpen(false)} />}

      <div className="toast-container">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.type}`} onClick={() => useToasts.getState().dismiss(t.id)}>
            {t.message}
          </div>
        ))}
      </div>
    </div>
  );
}
