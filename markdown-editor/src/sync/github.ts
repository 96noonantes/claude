import type { Doc, RemoteFileInfo, RemoteRef, SyncProvider } from '../types';
import { useSettings } from '../store/settings';

const API = 'https://api.github.com';

function creds() {
  return useSettings.getState().credentials;
}

function encodeBase64Utf8(text: string): string {
  const bytes = new TextEncoder().encode(text);
  let binary = '';
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

function decodeBase64Utf8(b64: string): string {
  const binary = atob(b64.replace(/\n/g, ''));
  const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

async function ghFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const { githubToken } = creds();
  if (!githubToken) throw new Error('GitHub トークンが未設定です。設定画面で入力してください。');
  const resp = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      Accept: 'application/vnd.github+json',
      Authorization: `Bearer ${githubToken}`,
      'X-GitHub-Api-Version': '2022-11-28',
      ...init.headers
    }
  });
  return resp;
}

function repoOrThrow(): string {
  const { githubRepo } = creds();
  if (!/^[^/\s]+\/[^/\s]+$/.test(githubRepo)) {
    throw new Error('GitHub リポジトリを「owner/repo」形式で設定してください。');
  }
  return githubRepo;
}

function docPath(doc: Doc): string {
  if (doc.remote?.provider === 'github' && doc.remote.fileId) return doc.remote.fileId;
  const dir = creds().githubDir.replace(/^\/+|\/+$/g, '');
  const name = doc.title.endsWith('.md') ? doc.title : `${doc.title}.md`;
  const safe = name.replace(/[\\:*?"<>|]/g, '_');
  return dir ? `${dir}/${safe}` : safe;
}

export const githubProvider: SyncProvider = {
  id: 'github',
  label: 'GitHub',

  isConfigured() {
    const { githubToken, githubRepo } = creds();
    return Boolean(githubToken && githubRepo);
  },

  isSignedIn() {
    return this.isConfigured();
  },

  async signIn() {
    const resp = await ghFetch('/user');
    if (!resp.ok) {
      throw new Error(`GitHub トークンが無効です (${resp.status})。設定を確認してください。`);
    }
  },

  signOut() {
    useSettings.getState().setCredentials({ githubToken: '' });
  },

  async save(doc: Doc): Promise<RemoteRef> {
    const repo = repoOrThrow();
    const branch = creds().githubBranch || 'main';
    const path = docPath(doc);
    const encodedPath = path.split('/').map(encodeURIComponent).join('/');

    // 既存ファイルなら現在の SHA を取得(上書きに必須)
    let sha: string | undefined;
    const head = await ghFetch(
      `/repos/${repo}/contents/${encodedPath}?ref=${encodeURIComponent(branch)}`
    );
    if (head.ok) {
      sha = ((await head.json()) as { sha: string }).sha;
    } else if (head.status !== 404) {
      throw new Error(`GitHub API エラー (${head.status})`);
    }

    const resp = await ghFetch(`/repos/${repo}/contents/${encodedPath}`, {
      method: 'PUT',
      body: JSON.stringify({
        message: `${sha ? 'Update' : 'Add'} ${path}`,
        content: encodeBase64Utf8(doc.content),
        branch,
        ...(sha ? { sha } : {})
      })
    });
    if (!resp.ok) {
      const body = await resp.text().catch(() => '');
      throw new Error(`GitHub への保存に失敗しました (${resp.status}): ${body.slice(0, 200)}`);
    }
    const json = (await resp.json()) as { content: { sha: string } };
    return {
      provider: 'github',
      fileId: path,
      path: `${repo}/${path}`,
      repo,
      branch,
      sha: json.content.sha
    };
  },

  async list(): Promise<RemoteFileInfo[]> {
    const repo = repoOrThrow();
    const branch = creds().githubBranch || 'main';
    const dir = creds().githubDir.replace(/^\/+|\/+$/g, '');
    const encodedDir = dir ? dir.split('/').map(encodeURIComponent).join('/') : '';
    const resp = await ghFetch(
      `/repos/${repo}/contents/${encodedDir}?ref=${encodeURIComponent(branch)}`
    );
    if (resp.status === 404) return [];
    if (!resp.ok) throw new Error(`GitHub API エラー (${resp.status})`);
    const json = (await resp.json()) as { type: string; name: string; path: string }[];
    if (!Array.isArray(json)) return [];
    return json
      .filter((f) => f.type === 'file' && /\.(md|markdown)$/i.test(f.name))
      .map((f) => ({
        provider: 'github' as const,
        fileId: f.path,
        name: f.name,
        path: `${repo}/${f.path}`
      }));
  },

  async download(file: RemoteFileInfo) {
    const repo = repoOrThrow();
    const branch = creds().githubBranch || 'main';
    const encodedPath = file.fileId.split('/').map(encodeURIComponent).join('/');
    const resp = await ghFetch(
      `/repos/${repo}/contents/${encodedPath}?ref=${encodeURIComponent(branch)}`
    );
    if (!resp.ok) throw new Error(`GitHub API エラー (${resp.status})`);
    const json = (await resp.json()) as { content: string; sha: string };
    return {
      title: file.name.replace(/\.(md|markdown)$/i, ''),
      content: decodeBase64Utf8(json.content),
      remote: {
        provider: 'github',
        fileId: file.fileId,
        path: file.path,
        repo,
        branch,
        sha: json.sha
      } as RemoteRef
    };
  }
};
