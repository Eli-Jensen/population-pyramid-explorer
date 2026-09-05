import { describe, expect, it } from 'vitest';
import { LAST_KEY, readLast, rememberLast, type StorageLike } from './last.ts';

function mem(): StorageLike & { m: Map<string, string> } {
  const m = new Map<string, string>();
  return { m, getItem: (k) => m.get(k) ?? null, setItem: (k, v) => void m.set(k, v) };
}

describe('last visited', () => {
  it('round-trips', () => {
    const s = mem();
    rememberLast('JPN', 2026, s);
    expect(readLast(s)).toEqual({ id: 'JPN', year: 2026 });
  });
  it('null when empty, corrupt, or malformed', () => {
    const s = mem();
    expect(readLast(s)).toBeNull();
    s.m.set(LAST_KEY, '{not json');
    expect(readLast(s)).toBeNull();
    s.m.set(LAST_KEY, JSON.stringify({ id: 1, year: '2026' }));
    expect(readLast(s)).toBeNull();
    s.m.set(LAST_KEY, JSON.stringify({ id: 'JPN', year: 2026.5 }));
    expect(readLast(s)).toBeNull();
  });
  it('swallows storage errors', () => {
    const boom: StorageLike = {
      getItem: () => {
        throw new Error('denied');
      },
      setItem: () => {
        throw new Error('denied');
      },
    };
    expect(() => rememberLast('JPN', 2026, boom)).not.toThrow();
    expect(readLast(boom)).toBeNull();
    expect(readLast(null)).toBeNull();
  });
});
