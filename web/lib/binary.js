export function assert(value, message) {
  if (!value) throw new Error(message);
}
export class Reader {
  constructor(bytes) {
    this.bytes = bytes;
    this.view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    this.pos = 0;
  }
  check(p, n) {
    assert(
      Number.isInteger(p) && n >= 0 && p >= 0 && p + n <= this.bytes.length,
      'Truncated or invalid binary file',
    );
  }
  u8(p) {
    this.check(p, 1);
    return this.view.getUint8(p);
  }
  u16(p) {
    this.check(p, 2);
    return this.view.getUint16(p, true);
  }
  u32(p) {
    this.check(p, 4);
    return this.view.getUint32(p, true);
  }
  i32(p) {
    this.check(p, 4);
    return this.view.getInt32(p, true);
  }
  f32(p) {
    this.check(p, 4);
    return this.view.getFloat32(p, true);
  }
  floats(p, n) {
    return Array.from({ length: n }, (_, i) => this.f32(p + i * 4));
  }
  string(p) {
    this.check(p, 1);
    let end = p;
    while (end < this.bytes.length && this.bytes[end]) end++;
    assert(end < this.bytes.length, 'Unterminated name');
    return new TextDecoder().decode(this.bytes.subarray(p, end));
  }
  take(method, n) {
    const x = this[method](this.pos);
    this.pos += n;
    return x;
  }
  skip(n) {
    this.check(this.pos, n);
    this.pos += n;
  }
  count() {
    const n = this.take('i32', 4);
    assert(n >= 0 && n <= this.bytes.length, 'Invalid element count');
    return n;
  }
}
export function half(h) {
  const sign = h & 32768 ? -1 : 1,
    e = (h >> 10) & 31,
    m = h & 1023;
  return (
    sign *
    (e === 0 ? m * 2 ** -24 : e === 31 ? (m ? NaN : Infinity) : (1 + m / 1024) * 2 ** (e - 15))
  );
}
export function toHalf(v) {
  const f = new Float32Array([v]),
    b = new Uint32Array(f.buffer)[0],
    s = (b >>> 16) & 32768;
  let e = ((b >>> 23) & 255) - 127 + 15,
    m = b & 0x7fffff;
  if (e <= 0) {
    if (e < -10) return s;
    m = (m | 0x800000) >> (1 - e);
    return s + ((m + 0xfff + ((m >> 13) & 1)) >> 13);
  }
  if (e >= 31) return s | 31744;
  m += 0xfff + ((m >> 13) & 1);
  if (m & 0x800000) {
    m = 0;
    e++;
  }
  return s | (e << 10) | (m >> 13);
}
export function table(bytes) {
  const r = new Reader(bytes);
  assert(r.u32(0) === 0x54493242, 'Invalid bone lookup');
  return Array.from({ length: r.u32(16) }, (_, i) => ({
    name: r.string(r.u32(r.u32(20) + i * 4)),
    index: r.u32(r.u32(24) + i * 4),
  }));
}
