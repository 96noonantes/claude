import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type Theme = 'light' | 'dark';
export type ViewMode = 'editor' | 'split' | 'preview';

export interface Credentials {
  googleClientId: string;
  githubToken: string;
  githubRepo: string; // "owner/repo"
  githubBranch: string;
  githubDir: string; // 保存先ディレクトリ(空 = ルート)
  dropboxAppKey: string;
}

interface SettingsState {
  theme: Theme;
  viewMode: ViewMode;
  sidebarOpen: boolean;
  credentials: Credentials;
  setTheme(theme: Theme): void;
  setViewMode(mode: ViewMode): void;
  toggleSidebar(): void;
  setCredentials(patch: Partial<Credentials>): void;
}

export const useSettings = create<SettingsState>()(
  persist(
    (set) => ({
      theme: 'light',
      viewMode: 'split',
      sidebarOpen: true,
      credentials: {
        googleClientId: import.meta.env.VITE_GOOGLE_CLIENT_ID ?? '',
        githubToken: '',
        githubRepo: '',
        githubBranch: 'main',
        githubDir: '',
        dropboxAppKey: import.meta.env.VITE_DROPBOX_APP_KEY ?? ''
      },
      setTheme: (theme) => set({ theme }),
      setViewMode: (viewMode) => set({ viewMode }),
      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
      setCredentials: (patch) =>
        set((s) => ({ credentials: { ...s.credentials, ...patch } }))
    }),
    { name: 'markdown-editor-settings' }
  )
);
