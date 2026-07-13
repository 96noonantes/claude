import { create } from 'zustand';

export interface Toast {
  id: number;
  message: string;
  type: 'info' | 'success' | 'error';
}

let nextId = 1;

interface ToastState {
  toasts: Toast[];
  push(message: string, type?: Toast['type']): void;
  dismiss(id: number): void;
}

export const useToasts = create<ToastState>((set) => ({
  toasts: [],
  push(message, type = 'info') {
    const id = nextId++;
    set((s) => ({ toasts: [...s.toasts, { id, message, type }] }));
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
    }, type === 'error' ? 8000 : 4000);
  },
  dismiss(id) {
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
  }
}));
