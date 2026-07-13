import type { Doc, RemoteFileInfo, RemoteRef, SyncProvider } from '../types';
import { useSettings } from '../store/settings';

const TOKEN_KEY = 'markdown-editor-dropbox-token';
const VERIFIER_KEY = 'markdown-editor-dropbox-verifier';

interface StoredToken {
  accessToken: string;
  refreshToken?: string;
  expiresAt: number;
}

function appKey(): string {
  const key = useSettings.getState().credentials.dropboxAppKey;
  if (!key) throw new Error('Dropbox アプリキーが未設定です。設定画面で入力してください。');
  return key;
}

function redirectUri(): string {
  return location.origin + location.pathname;
}

function loadToken(): StoredToken | null {
  try {
    const raw = localStorage.getItem(TOKEN_KEY);
    return raw ? (JSON.parse(raw) as StoredToken) : null;
  } catch {
    return null;
  }
}

function storeToken(token: StoredToken | null) {
  if (token) localStorage.setItem(TOKEN_KEY, JSON.stringify(token));
  else localStorage.removeItem(TOKEN_KEY);
}

function base64UrlEncode(bytes: Uint8Array): string {
  let binary = '';
  bytes.forEach((b) => (binary += String.fromCharCode(b)));
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function sha256(text: string): Promise<Uint8Array> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return new Uint8Array(digest);
}

async function tokenRequest(params: Record<string, string>): Promise<StoredToken> {
  const resp = await fetch('https://api.dropboxapi.com/oauth2/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams(params).toString()
  });
  if (!resp.ok) {
    const body = await resp.text().catch(() => '');
    throw new Error(`Dropbox 認証エラー (${resp.status}): ${body.slice(0, 200)}`);
  }
  const json = (await resp.json()) as {
    access_token: string;
    refresh_token?: string;
    expires_in: number;
  };
  return {
    accessToken: json.access_token,
    refreshToken: json.refresh_token ?? loadToken()?.refreshToken,
    expiresAt: Date.now() + (json.expires_in - 60) * 1000
  };
}

/** アプリ起動時に呼ぶ: OAuth リダイレクトの code をトークンに交換する */
export async function handleDropboxRedirect(): Promise<boolean> {
  const params = new URLSearchParams(location.search);
  const code = params.get('code');
  const verifier = sessionStorage.getItem(VERIFIER_KEY);
  if (!code || !verifier) return false;
  sessionStorage.removeItem(VERIFIER_KEY);
  history.replaceState(null, '', location.pathname);
  const token = await tokenRequest({
    code,
    grant_type: 'authorization_code',
    client_id: appKey(),
    redirect_uri: redirectUri(),
    code_verifier: verifier
  });
  storeToken(token);
  return true;
}

async function ensureToken(): Promise<string> {
  const token = loadToken();
  if (!token) throw new Error('Dropbox にサインインしていません。');
  if (Date.now() < token.expiresAt) return token.accessToken;
  if (!token.refreshToken) {
    storeToken(null);
    throw new Error('Dropbox のセッションが切れました。再度サインインしてください。');
  }
  const refreshed = await tokenRequest({
    grant_type: 'refresh_token',
    refresh_token: token.refreshToken,
    client_id: appKey()
  });
  storeToken(refreshed);
  return refreshed.accessToken;
}

/** HTTPヘッダーに載せるJSONは非ASCII文字を \uXXXX にエスケープする必要がある */
function headerSafeJson(value: unknown): string {
  return JSON.stringify(value).replace(/[\u007f-\uffff]/g, (c) => {
    return '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0');
  });
}

async function rpc<T>(url: string, arg: unknown): Promise<T> {
  const token = await ensureToken();
  const resp = await fetch(url, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(arg)
  });
  if (!resp.ok) {
    const body = await resp.text().catch(() => '');
    throw new Error(`Dropbox API エラー (${resp.status}): ${body.slice(0, 200)}`);
  }
  return (await resp.json()) as T;
}

function docPath(doc: Doc): string {
  if (doc.remote?.provider === 'dropbox' && doc.remote.path) return doc.remote.path;
  const name = doc.title.endsWith('.md') ? doc.title : `${doc.title}.md`;
  return `/${name.replace(/[\\/:*?"<>|]/g, '_')}`;
}

export const dropboxProvider: SyncProvider = {
  id: 'dropbox',
  label: 'Dropbox',

  isConfigured() {
    return Boolean(useSettings.getState().credentials.dropboxAppKey);
  },

  isSignedIn() {
    return loadToken() !== null;
  },

  async signIn() {
    const verifier = base64UrlEncode(crypto.getRandomValues(new Uint8Array(48)));
    sessionStorage.setItem(VERIFIER_KEY, verifier);
    const challenge = base64UrlEncode(await sha256(verifier));
    const url = new URL('https://www.dropbox.com/oauth2/authorize');
    url.searchParams.set('client_id', appKey());
    url.searchParams.set('response_type', 'code');
    url.searchParams.set('code_challenge', challenge);
    url.searchParams.set('code_challenge_method', 'S256');
    url.searchParams.set('redirect_uri', redirectUri());
    url.searchParams.set('token_access_type', 'offline');
    location.href = url.toString(); // 認可ページへ遷移(戻りは handleDropboxRedirect が処理)
  },

  signOut() {
    storeToken(null);
  },

  async save(doc: Doc): Promise<RemoteRef> {
    const token = await ensureToken();
    const path = docPath(doc);
    const resp = await fetch('https://content.dropboxapi.com/2/files/upload', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/octet-stream',
        'Dropbox-API-Arg': headerSafeJson({ path, mode: 'overwrite', mute: true })
      },
      body: new TextEncoder().encode(doc.content)
    });
    if (!resp.ok) {
      const body = await resp.text().catch(() => '');
      throw new Error(`Dropbox への保存に失敗しました (${resp.status}): ${body.slice(0, 200)}`);
    }
    const json = (await resp.json()) as { id: string; path_display: string };
    return { provider: 'dropbox', fileId: json.id, path: json.path_display };
  },

  async list(): Promise<RemoteFileInfo[]> {
    const json = await rpc<{
      entries: { '.tag': string; id: string; name: string; path_display: string; server_modified?: string }[];
    }>('https://api.dropboxapi.com/2/files/list_folder', {
      path: '',
      recursive: true,
      limit: 200
    });
    return json.entries
      .filter((e) => e['.tag'] === 'file' && /\.(md|markdown)$/i.test(e.name))
      .map((e) => ({
        provider: 'dropbox' as const,
        fileId: e.id,
        name: e.name,
        path: e.path_display,
        modifiedAt: e.server_modified
      }));
  },

  async download(file: RemoteFileInfo) {
    const token = await ensureToken();
    const resp = await fetch('https://content.dropboxapi.com/2/files/download', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Dropbox-API-Arg': headerSafeJson({ path: file.fileId })
      }
    });
    if (!resp.ok) throw new Error(`Dropbox からの取得に失敗しました (${resp.status})`);
    const content = await resp.text();
    return {
      title: file.name.replace(/\.(md|markdown)$/i, ''),
      content,
      remote: { provider: 'dropbox', fileId: file.fileId, path: file.path } as RemoteRef
    };
  }
};
