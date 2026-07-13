import { create } from 'zustand';
import type { Doc, RemoteRef } from '../types';
import { deleteDoc, getAllDocs, putDoc } from '../lib/db';

const WELCOME_CONTENT = `# ようこそ 👋

これは **StackEdit 風**の Markdown エディタです。ブラウザ内(IndexedDB)に自動保存されるため、オフラインでも安心して編集できます。

## 主な機能

- 左サイドバーでドキュメントを管理
- エディタとプレビューの分割表示(スクロール同期付き)
- ツールバーからワンクリックで書式挿入
- Google Drive / GitHub / Dropbox への保存(右上の同期メニューから)
- \`.md\` ファイルのインポート / エクスポート

## Markdown の例

> 引用文はこのように表示されます。

| 機能 | 対応 |
| --- | --- |
| テーブル | ✅ |
| コードハイライト | ✅ |
| タスクリスト | ✅ |

- [x] ドキュメントを作成する
- [ ] クラウドに保存してみる

\`\`\`js
function hello(name) {
  console.log(\`Hello, \${name}!\`);
}
\`\`\`

---

編集を始めるには、この文章を書き換えるか、サイドバーの「＋」から新しいドキュメントを作成してください。
`;

function makeId(): string {
  return crypto.randomUUID();
}

let saveTimer: ReturnType<typeof setTimeout> | null = null;

interface DocumentsState {
  docs: Doc[];
  currentId: string | null;
  loaded: boolean;
  saveState: 'saved' | 'saving';
  load(): Promise<void>;
  select(id: string): void;
  create(title?: string, content?: string, remote?: RemoteRef | null): Doc;
  remove(id: string): Promise<void>;
  rename(id: string, title: string): void;
  setContent(id: string, content: string): void;
  setRemote(id: string, remote: RemoteRef | null): void;
}

export const useDocuments = create<DocumentsState>((set, get) => {
  function persistDoc(id: string) {
    const doc = get().docs.find((d) => d.id === id);
    if (doc) {
      void putDoc(doc).then(() => {
        set({ saveState: 'saved' });
      });
    }
  }

  function schedulePersist(id: string) {
    set({ saveState: 'saving' });
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(() => persistDoc(id), 400);
  }

  function updateDoc(id: string, patch: Partial<Doc>, touch = true) {
    set((s) => ({
      docs: s.docs.map((d) =>
        d.id === id ? { ...d, ...patch, ...(touch ? { updatedAt: Date.now() } : {}) } : d
      )
    }));
  }

  return {
    docs: [],
    currentId: null,
    loaded: false,
    saveState: 'saved',

    async load() {
      let docs = await getAllDocs();
      if (docs.length === 0) {
        const welcome: Doc = {
          id: makeId(),
          title: 'ようこそ',
          content: WELCOME_CONTENT,
          createdAt: Date.now(),
          updatedAt: Date.now(),
          remote: null
        };
        await putDoc(welcome);
        docs = [welcome];
      }
      set({ docs, currentId: docs[0].id, loaded: true });
    },

    select(id) {
      set({ currentId: id });
    },

    create(title = '無題のドキュメント', content = '', remote = null) {
      const doc: Doc = {
        id: makeId(),
        title,
        content,
        createdAt: Date.now(),
        updatedAt: Date.now(),
        remote
      };
      set((s) => ({ docs: [doc, ...s.docs], currentId: doc.id }));
      void putDoc(doc);
      return doc;
    },

    async remove(id) {
      const { docs, currentId } = get();
      const rest = docs.filter((d) => d.id !== id);
      set({
        docs: rest,
        currentId: currentId === id ? (rest[0]?.id ?? null) : currentId
      });
      await deleteDoc(id);
    },

    rename(id, title) {
      updateDoc(id, { title });
      schedulePersist(id);
    },

    setContent(id, content) {
      updateDoc(id, { content });
      schedulePersist(id);
    },

    setRemote(id, remote) {
      updateDoc(id, { remote }, false);
      persistDoc(id);
    }
  };
});
