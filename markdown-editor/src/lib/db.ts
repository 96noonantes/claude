import { openDB, type DBSchema, type IDBPDatabase } from 'idb';
import type { Doc } from '../types';

interface EditorDB extends DBSchema {
  documents: {
    key: string;
    value: Doc;
    indexes: { 'by-updated': number };
  };
}

let dbPromise: Promise<IDBPDatabase<EditorDB>> | null = null;

function getDB() {
  if (!dbPromise) {
    dbPromise = openDB<EditorDB>('markdown-editor', 1, {
      upgrade(db) {
        const store = db.createObjectStore('documents', { keyPath: 'id' });
        store.createIndex('by-updated', 'updatedAt');
      }
    });
  }
  return dbPromise;
}

export async function getAllDocs(): Promise<Doc[]> {
  const db = await getDB();
  const docs = await db.getAll('documents');
  return docs.sort((a, b) => b.updatedAt - a.updatedAt);
}

export async function putDoc(doc: Doc): Promise<void> {
  const db = await getDB();
  await db.put('documents', doc);
}

export async function deleteDoc(id: string): Promise<void> {
  const db = await getDB();
  await db.delete('documents', id);
}
