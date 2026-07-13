import type { Doc, RemoteFileInfo, RemoteRef, SyncProvider } from '../types';
import { useSettings } from '../store/settings';

/* global google */
declare global {
  interface Window {
    google?: {
      accounts: {
        oauth2: {
          initTokenClient(config: {
            client_id: string;
            scope: string;
            callback: (resp: { access_token?: string; expires_in?: number; error?: string }) => void;
          }): { requestAccessToken(opts?: { prompt?: string }) : void };
        };
      };
    };
  }
}

const SCOPE = 'https://www.googleapis.com/auth/drive.file';
const API = 'https://www.googleapis.com/drive/v3';
const UPLOAD_API = 'https://www.googleapis.com/upload/drive/v3';

let accessToken: string | null = null;
let tokenExpiresAt = 0;
let gisPromise: Promise<void> | null = null;

function loadGis(): Promise<void> {
  if (window.google?.accounts) return Promise.resolve();
  if (!gisPromise) {
    gisPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () =>
        reject(new Error('Google のスクリプトを読み込めませんでした。オンラインか確認してください。'));
      document.head.appendChild(script);
    });
  }
  return gisPromise;
}

function requestToken(prompt: '' | 'consent'): Promise<void> {
  const clientId = useSettings.getState().credentials.googleClientId;
  if (!clientId) {
    return Promise.reject(new Error('Google クライアントIDが未設定です。設定画面で入力してください。'));
  }
  return loadGis().then(
    () =>
      new Promise<void>((resolve, reject) => {
        const client = window.google!.accounts.oauth2.initTokenClient({
          client_id: clientId,
          scope: SCOPE,
          callback: (resp) => {
            if (resp.error || !resp.access_token) {
              reject(new Error(`Google 認証に失敗しました: ${resp.error ?? 'unknown'}`));
              return;
            }
            accessToken = resp.access_token;
            tokenExpiresAt = Date.now() + ((resp.expires_in ?? 3600) - 60) * 1000;
            resolve();
          }
        });
        client.requestAccessToken({ prompt });
      })
  );
}

async function ensureToken(): Promise<string> {
  if (!accessToken || Date.now() > tokenExpiresAt) {
    await requestToken(accessToken ? '' : 'consent');
  }
  return accessToken!;
}

async function driveFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const token = await ensureToken();
  const resp = await fetch(url, {
    ...init,
    headers: { ...init.headers, Authorization: `Bearer ${token}` }
  });
  if (!resp.ok) {
    const body = await resp.text().catch(() => '');
    throw new Error(`Google Drive API エラー (${resp.status}): ${body.slice(0, 200)}`);
  }
  return resp;
}

function fileName(doc: Doc): string {
  return doc.title.endsWith('.md') ? doc.title : `${doc.title}.md`;
}

export const googleDriveProvider: SyncProvider = {
  id: 'googleDrive',
  label: 'Google Drive',

  isConfigured() {
    return Boolean(useSettings.getState().credentials.googleClientId);
  },

  isSignedIn() {
    return Boolean(accessToken && Date.now() < tokenExpiresAt);
  },

  async signIn() {
    await requestToken('consent');
  },

  signOut() {
    accessToken = null;
    tokenExpiresAt = 0;
  },

  async save(doc: Doc): Promise<RemoteRef> {
    const metadata: Record<string, string> = { name: fileName(doc), mimeType: 'text/markdown' };
    const boundary = `mdeditor${Date.now()}`;
    const body =
      `--${boundary}\r\n` +
      'Content-Type: application/json; charset=UTF-8\r\n\r\n' +
      `${JSON.stringify(metadata)}\r\n` +
      `--${boundary}\r\n` +
      'Content-Type: text/markdown; charset=UTF-8\r\n\r\n' +
      `${doc.content}\r\n` +
      `--${boundary}--`;

    const existingId = doc.remote?.provider === 'googleDrive' ? doc.remote.fileId : null;
    const url = existingId
      ? `${UPLOAD_API}/files/${existingId}?uploadType=multipart`
      : `${UPLOAD_API}/files?uploadType=multipart`;
    const resp = await driveFetch(url, {
      method: existingId ? 'PATCH' : 'POST',
      headers: { 'Content-Type': `multipart/related; boundary=${boundary}` },
      body
    });
    const json = (await resp.json()) as { id: string; name: string };
    return { provider: 'googleDrive', fileId: json.id, path: json.name };
  },

  async list(): Promise<RemoteFileInfo[]> {
    const q = encodeURIComponent(
      "(mimeType='text/markdown' or name contains '.md') and trashed=false"
    );
    const resp = await driveFetch(
      `${API}/files?q=${q}&fields=files(id,name,modifiedTime)&pageSize=100&orderBy=modifiedTime desc`
    );
    const json = (await resp.json()) as {
      files: { id: string; name: string; modifiedTime: string }[];
    };
    return json.files.map((f) => ({
      provider: 'googleDrive',
      fileId: f.id,
      name: f.name,
      path: f.name,
      modifiedAt: f.modifiedTime
    }));
  },

  async download(file: RemoteFileInfo) {
    const resp = await driveFetch(`${API}/files/${file.fileId}?alt=media`);
    const content = await resp.text();
    return {
      title: file.name.replace(/\.md$/i, ''),
      content,
      remote: { provider: 'googleDrive', fileId: file.fileId, path: file.name } as RemoteRef
    };
  }
};
