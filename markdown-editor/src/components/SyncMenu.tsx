import { useState } from 'react';
import { providers } from '../sync';
import type { RemoteFileInfo, SyncProvider } from '../types';
import { useDocuments } from '../store/documents';
import { useToasts } from '../store/toasts';
import { renderMarkdown } from '../lib/markdown';

interface Props {
  onClose(): void;
  onOpenSettings(): void;
}

export default function SyncMenu({ onClose, onOpenSettings }: Props) {
  const doc = useDocuments((s) => s.docs.find((d) => d.id === s.currentId));
  const push = useToasts((s) => s.push);
  const [busy, setBusy] = useState<string | null>(null);
  const [, forceUpdate] = useState(0);
  const [picker, setPicker] = useState<{ provider: SyncProvider; files: RemoteFileInfo[] } | null>(
    null
  );

  const refresh = () => forceUpdate((n) => n + 1);

  async function run(key: string, fn: () => Promise<void>) {
    setBusy(key);
    try {
      await fn();
    } catch (err) {
      push(err instanceof Error ? err.message : String(err), 'error');
    } finally {
      setBusy(null);
      refresh();
    }
  }

  function handleSignIn(p: SyncProvider) {
    if (!p.isConfigured()) {
      push(`${p.label} を使うには設定が必要です`, 'info');
      onOpenSettings();
      return;
    }
    void run(`signin-${p.id}`, async () => {
      await p.signIn();
      push(`${p.label} にサインインしました`, 'success');
    });
  }

  function handleSave(p: SyncProvider) {
    if (!doc) return;
    if (!p.isConfigured()) {
      push(`${p.label} を使うには設定が必要です`, 'info');
      onOpenSettings();
      return;
    }
    void run(`save-${p.id}`, async () => {
      const remote = await p.save(doc);
      useDocuments.getState().setRemote(doc.id, remote);
      push(`${p.label} に保存しました: ${remote.path}`, 'success');
    });
  }

  function handleList(p: SyncProvider) {
    if (!p.isConfigured()) {
      push(`${p.label} を使うには設定が必要です`, 'info');
      onOpenSettings();
      return;
    }
    void run(`list-${p.id}`, async () => {
      const files = await p.list();
      if (files.length === 0) {
        push(`${p.label} に Markdown ファイルが見つかりませんでした`, 'info');
        return;
      }
      setPicker({ provider: p, files });
    });
  }

  function handleOpenFile(p: SyncProvider, file: RemoteFileInfo) {
    void run(`open-${file.fileId}`, async () => {
      const { title, content, remote } = await p.download(file);
      useDocuments.getState().create(title, content, remote);
      push(`「${title}」を開きました`, 'success');
      setPicker(null);
      onClose();
    });
  }

  function exportMarkdown() {
    if (!doc) return;
    downloadBlob(new Blob([doc.content], { type: 'text/markdown' }), `${doc.title}.md`);
  }

  function exportHtml() {
    if (!doc) return;
    const body = renderMarkdown(doc.content);
    const html = `<!doctype html>\n<html lang="ja"><head><meta charset="utf-8"><title>${escapeHtml(
      doc.title
    )}</title></head><body>\n${body}\n</body></html>`;
    downloadBlob(new Blob([html], { type: 'text/html' }), `${doc.title}.html`);
  }

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <div className="drawer" role="dialog" aria-label="同期とエクスポート">
        <div className="drawer-header">
          <h2>同期・エクスポート</h2>
          <button className="icon-btn" onClick={onClose} title="閉じる">
            ×
          </button>
        </div>

        <div className="drawer-section">
          <h3>クラウドに保存 / 開く</h3>
          {doc && <p className="drawer-note">対象: {doc.title}</p>}
          {providers.map((p) => {
            const configured = p.isConfigured();
            const signedIn = configured && p.isSignedIn();
            return (
              <div className="provider-card" key={p.id}>
                <div className="provider-head">
                  <span className={`provider-dot ${signedIn ? 'on' : configured ? 'ready' : 'off'}`} />
                  <span className="provider-name">{p.label}</span>
                  <span className="provider-status">
                    {!configured ? '未設定' : signedIn ? '接続済み' : '未接続'}
                  </span>
                </div>
                <div className="provider-actions">
                  {!configured ? (
                    <button className="btn" onClick={onOpenSettings}>
                      設定する
                    </button>
                  ) : (
                    <>
                      {!signedIn && (
                        <button
                          className="btn"
                          disabled={busy !== null}
                          onClick={() => handleSignIn(p)}
                        >
                          {busy === `signin-${p.id}` ? '接続中…' : 'サインイン'}
                        </button>
                      )}
                      <button
                        className="btn btn-primary"
                        disabled={busy !== null || !doc}
                        onClick={() => handleSave(p)}
                      >
                        {busy === `save-${p.id}` ? '保存中…' : '保存'}
                      </button>
                      <button
                        className="btn"
                        disabled={busy !== null}
                        onClick={() => handleList(p)}
                      >
                        {busy === `list-${p.id}` ? '取得中…' : '開く…'}
                      </button>
                      {signedIn && (
                        <button
                          className="btn btn-ghost"
                          onClick={() => {
                            p.signOut();
                            refresh();
                          }}
                        >
                          切断
                        </button>
                      )}
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <div className="drawer-section">
          <h3>エクスポート</h3>
          <div className="provider-actions">
            <button className="btn" disabled={!doc} onClick={exportMarkdown}>
              Markdown (.md)
            </button>
            <button className="btn" disabled={!doc} onClick={exportHtml}>
              HTML (.html)
            </button>
          </div>
        </div>
      </div>

      {picker && (
        <div className="modal-backdrop" onClick={() => setPicker(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{picker.provider.label} のファイル</h2>
              <button className="icon-btn" onClick={() => setPicker(null)} title="閉じる">
                ×
              </button>
            </div>
            <ul className="remote-file-list">
              {picker.files.map((f) => (
                <li key={f.fileId}>
                  <button
                    className="remote-file"
                    disabled={busy !== null}
                    onClick={() => handleOpenFile(picker.provider, f)}
                  >
                    <span className="remote-file-name">{f.name}</span>
                    <span className="remote-file-path">{f.path}</span>
                    {f.modifiedAt && (
                      <span className="remote-file-date">
                        {new Date(f.modifiedAt).toLocaleString('ja-JP')}
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </>
  );
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
