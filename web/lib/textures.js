import { TGALoader } from 'three/addons/loaders/TGALoader.js';
import { DDSLoader } from 'three/addons/loaders/DDSLoader.js';
import {
  DataTexture,
  CompressedTexture,
  RGBAFormat,
  UnsignedByteType,
  SRGBColorSpace,
  LinearFilter,
} from 'three';
import { assert } from './binary.js';
export async function decodeImage(bytes, name) {
  let pixels, width, height;
  if (/\.tga$/i.test(name)) {
    const image = new TGALoader().parse(bytes.slice().buffer);
    pixels = image.data;
    width = image.width;
    height = image.height;
  } else if (/\.dds$/i.test(name)) {
    const image = new DDSLoader().parse(bytes.slice().buffer, false);
    assert(
      image.format === RGBAFormat,
      'DDS source textures must be uncompressed RGBA; use PNG for compressed DDS',
    );
    pixels = image.mipmaps[0].data;
    width = image.width;
    height = image.height;
  } else {
    const bitmap = await createImageBitmap(new Blob([bytes]));
    width = bitmap.width;
    height = bitmap.height;
    assert(width * height <= 64 * 1024 * 1024, 'Texture exceeds 64 megapixels');
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    canvas.getContext('2d').drawImage(bitmap, 0, 0);
    bitmap.close();
    return canvas;
  }
  assert(width * height <= 64 * 1024 * 1024, 'Texture exceeds 64 megapixels');
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  canvas
    .getContext('2d')
    .putImageData(new ImageData(new Uint8ClampedArray(pixels), width, height), 0, 0);
  return canvas;
}
export function encodeDDS(image) {
  const width = Math.min(1024, 2 ** Math.ceil(Math.log2(image.width))),
    height = Math.min(1024, 2 ** Math.ceil(Math.log2(image.height))),
    levels = [];
  let w = width,
    h = height,
    previous = image;
  while (true) {
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(previous, 0, 0, w, h);
    const pixels = ctx.getImageData(0, 0, w, h).data,
      bytes = new Uint8Array(pixels.length);
    for (let i = 0; i < pixels.length; i += 4) {
      bytes[i] = pixels[i + 2];
      bytes[i + 1] = pixels[i + 1];
      bytes[i + 2] = pixels[i];
      bytes[i + 3] = pixels[i + 3];
    }
    levels.push(bytes);
    previous = canvas;
    if (w === 1 && h === 1) break;
    w = Math.max(1, w >> 1);
    h = Math.max(1, h >> 1);
  }
  const data = new Uint8Array(128 + levels.reduce((n, b) => n + b.length, 0)),
    v = new DataView(data.buffer),
    u = (p, n) => v.setUint32(p, n, true);
  u(0, 0x20534444);
  u(4, 124);
  u(8, 0x2100f);
  u(12, height);
  u(16, width);
  u(20, width * 4);
  u(28, levels.length);
  u(76, 32);
  u(80, 0x41);
  u(88, 32);
  u(92, 0xff0000);
  u(96, 0xff00);
  u(100, 0xff);
  u(104, 0xff000000);
  u(108, 0x401008);
  let offset = 128;
  for (const level of levels) {
    data.set(level, offset);
    offset += level.length;
  }
  return data;
}
export function ddsTexture(bytes) {
  const dds = new DDSLoader().parse(bytes.slice().buffer, false);
  assert(dds.width > 0 && dds.mipmaps.length, 'Unsupported DDS texture');
  const texture =
    dds.format === RGBAFormat
      ? new DataTexture(dds.mipmaps[0].data, dds.width, dds.height, RGBAFormat, UnsignedByteType)
      : new CompressedTexture(dds.mipmaps, dds.width, dds.height, dds.format);
  texture.flipY = false;
  texture.colorSpace = SRGBColorSpace;
  texture.minFilter = LinearFilter;
  texture.needsUpdate = true;
  return texture;
}
