import { useState } from 'react';
import { useSettings, type Credentials } from '../store/settings';
import { useToasts } from '../store/toasts';

interface Props {
  onClose(): void;
}

export default function SettingsDialog({ onClose }: Props) {
  const credentials = useSettings((s) => s.credentials);
  const setCredentials = useSettings((s) => s.setCredentials);
  const push = useToasts((s) => s.push);
  const [form, setForm] = useState<Credentials>({ ...credentials });

  function field(key: keyof Credentials, label: string, placeholder: string, type = 'text', hint?: string) {
    return (
      <label className="settings-field">
        <span className="settings-label">{label}</span>
        <input
          type={type}
          value={form[key]}
          placeholder={placeholder}
          onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
          autoComplete="off"
          spellCheck={false}
        />
        {hint && <span className="settings-hint">{hint}</span>}
      </label>
    );
  }

  function save() {
    setCredentials(form);
    push('設定を保存しました', 'success');
    onClose();
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal modal-settings" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>クラウド連携の設定</h2>
          <button className="icon-btn" onClick={onClose} title="閉じる">
            ×
          </button>
        </div>

        <p className="settings-warning">
          ⚠ 認証情報はこのブラウザの localStorage にのみ保存されます。共有端末では設定しないでください。
        </p>

        <div className="settings-group">
          <h3>Google Drive</h3>
          {field(
            'googleClientId',
            'OAuth クライアント ID',
            'xxxx.apps.googleusercontent.com',
            'text',
            'Google Cloud Console で「OAuth クライアント ID(ウェブアプリ)」を作成し、このアプリのURLを「承認済みの JavaScript 生成元」に追加してください。'
          )}
        </div>

        <div className="settings-group">
          <h3>GitHub</h3>
          {field(
            'githubToken',
            'Personal Access Token',
            'github_pat_...',
            'password',
            'Fine-grained PAT を推奨(対象リポジトリの Contents: Read and write 権限のみ)。'
          )}
          {field('githubRepo', 'リポジトリ', 'owner/repo')}
          {field('githubBranch', 'ブランチ', 'main')}
          {field('githubDir', '保存先ディレクトリ(任意)', 'docs/notes')}
        </div>

        <div className="settings-group">
          <h3>Dropbox</h3>
          {field(
            'dropboxAppKey',
            'アプリキー (App key)',
            '',
            'text',
            'Dropbox App Console でアプリを作成し、Redirect URI にこのアプリのURLを登録してください。'
          )}
        </div>

        <div className="modal-footer">
          <button className="btn" onClick={onClose}>
            キャンセル
          </button>
          <button className="btn btn-primary" onClick={save}>
            保存
          </button>
        </div>
      </div>
    </div>
  );
}
