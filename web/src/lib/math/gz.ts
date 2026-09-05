// gzip magic-byte sniff + inflate through `DecompressionStream` — shared by the corpus loader (data.ts) and the econ
// decoder (econ.ts) so neither imports the other (a static back-edge from a lazy chunk into an entry module makes
// Rollup split the entry; PLAN §8 first-paint budget).

export function isGzip(bytes: Uint8Array): boolean {
  return bytes.length >= 2 && bytes[0] === 0x1f && bytes[1] === 0x8b;
}

/** Inflate a gzip buffer through `DecompressionStream('gzip')`. */
export async function gunzip(buf: ArrayBuffer): Promise<Uint8Array> {
  const stream = new Blob([buf]).stream().pipeThrough(new DecompressionStream('gzip'));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}
