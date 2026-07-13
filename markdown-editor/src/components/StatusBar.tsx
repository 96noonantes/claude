import { useDocuments } from '../store/documents';

const PROVIDER_LABEL: Record<string, string> = {
  googleDrive: 'Google Drive',
  github: 'GitHub',
  dropbox: 'Dropbox'
};

export default function StatusBar() {
  const doc = useDocuments((s) => s.docs.find((d) => d.id === s.currentId));
  const saveState = useDocuments((s) => s.saveState);

  const content = doc?.content ?? '';
  const chars = content.length;
  const lines = content === '' ? 0 : content.split('\n').length;
  const words = content.trim() === '' ? 0 : content.trim().split(/\s+/).length;

  return (
    <div className="statusbar">
      <span>{chars.toLocaleString()} 文字</span>
      <span>{words.toLocaleString()} 語</span>
      <span>{lines.toLocaleString()} 行</span>
      <span className="statusbar-spacer" />
      {doc?.remote && (
        <span className="statusbar-remote" title={doc.remote.path}>
          {PROVIDER_LABEL[doc.remote.provider]}: {doc.remote.path}
        </span>
      )}
      <span className={`statusbar-save ${saveState}`}>
        {saveState === 'saving' ? '保存中…' : '✓ 保存済み'}
      </span>
    </div>
  );
}
