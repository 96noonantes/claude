export type ProviderId = 'googleDrive' | 'github' | 'dropbox';

/** クラウド上のファイルとの紐付け情報 */
export interface RemoteRef {
  provider: ProviderId;
  /** Google Drive / Dropbox のファイルID、GitHub はリポジトリ内パス */
  fileId: string;
  /** 表示用のパスやファイル名 */
  path: string;
  /** GitHub: owner/repo */
  repo?: string;
  /** GitHub: ブランチ名 */
  branch?: string;
  /** GitHub: 最終コミット時の blob SHA(上書き更新に必要) */
  sha?: string;
}

export interface Doc {
  id: string;
  title: string;
  content: string;
  createdAt: number;
  updatedAt: number;
  remote?: RemoteRef | null;
}

/** クラウド上のファイル一覧の1件 */
export interface RemoteFileInfo {
  provider: ProviderId;
  fileId: string;
  name: string;
  path: string;
  modifiedAt?: string;
}

export interface SyncProvider {
  id: ProviderId;
  label: string;
  /** APIキー等の設定が済んでいるか */
  isConfigured(): boolean;
  isSignedIn(): boolean;
  signIn(): Promise<void>;
  signOut(): void;
  /** ドキュメントを保存し、紐付け情報を返す(既存の remote があれば上書き) */
  save(doc: Doc): Promise<RemoteRef>;
  /** クラウド上の Markdown ファイル一覧 */
  list(): Promise<RemoteFileInfo[]>;
  /** ファイルの内容を取得 */
  download(file: RemoteFileInfo): Promise<{ title: string; content: string; remote: RemoteRef }>;
}
