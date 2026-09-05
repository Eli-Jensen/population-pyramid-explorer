// "Continue with {last}" memory for the home page — localStorage behind try/catch (PLAN §7).

export const LAST_KEY = 'ppe:last';

export interface Last {
  id: string;
  year: number;
}

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

function storage(): StorageLike | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage;
  } catch {
    return null;
  }
}

export function rememberLast(id: string, year: number, store: StorageLike | null = storage()): void {
  try {
    store?.setItem(LAST_KEY, JSON.stringify({ id, year } satisfies Last));
  } catch {
    /* private mode / quota — ignore */
  }
}

export function readLast(store: StorageLike | null = storage()): Last | null {
  try {
    const raw = store?.getItem(LAST_KEY);
    if (!raw) return null;
    const v = JSON.parse(raw) as Partial<Last>;
    if (typeof v.id !== 'string' || typeof v.year !== 'number' || !Number.isInteger(v.year)) return null;
    return { id: v.id, year: v.year };
  } catch {
    return null;
  }
}
