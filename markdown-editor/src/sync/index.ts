import type { ProviderId, SyncProvider } from '../types';
import { googleDriveProvider } from './googleDrive';
import { githubProvider } from './github';
import { dropboxProvider } from './dropbox';

export const providers: SyncProvider[] = [googleDriveProvider, githubProvider, dropboxProvider];

export function getProvider(id: ProviderId): SyncProvider {
  const provider = providers.find((p) => p.id === id);
  if (!provider) throw new Error(`未知のプロバイダ: ${id}`);
  return provider;
}

export { handleDropboxRedirect } from './dropbox';
