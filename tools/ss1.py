# -*- coding: utf-8 -*-
r"""유나 3 — SS1 그림(16비트 RGB, 반복 압축) 풀기·싸기 (2026-09-28, 스테이트 1 VDP1 텍스처로 검증)
  형식: [u16 폭][u16 높이] + 스트림. 바이트 b < 0x80 → 다음 픽셀(u16) 을 b 번 반복, b ≥ 0x80 → b 부터 u16 픽셀 1개
        (그래서 최상위 비트 0 픽셀(0x0000 투명 등)은 반복으로만 쓴다)
  python tools/ss1.py <파일.SS1> [png]   → 풀어서 PNG
"""
import struct, sys
from PIL import Image


def decode(b):
    w, h = struct.unpack_from('>HH', b, 0)
    px = []; i = 4; n = w * h
    while len(px) < n:
        c = b[i]
        if c < 0x80:
            px += [struct.unpack_from('>H', b, i + 1)[0]] * c; i += 3
        else:
            px.append(struct.unpack_from('>H', b, i)[0]); i += 2
    return w, h, px[:n], i


def encode(w, h, px):
    out = bytearray(struct.pack('>HH', w, h)); i = 0
    while i < len(px):
        j = i
        while j < len(px) and px[j] == px[i] and j - i < 127:
            j += 1
        if j - i >= 2 or not px[i] & 0x8000:
            out += bytes([j - i]) + struct.pack('>H', px[i]); i = j
        else:
            out += struct.pack('>H', px[i]); i += 1
    return bytes(out)


def to_png(w, h, px):
    im = Image.new('RGBA', (w, h))
    im.putdata([((v & 31) << 3, (v >> 5 & 31) << 3, (v >> 10 & 31) << 3, 255 if v & 0x8000 else 0) for v in px])
    return im


if __name__ == '__main__':
    b = open(sys.argv[1], 'rb').read()
    w, h, px, used = decode(b)
    print('%dx%d · 스트림 %d/%d B · 다시 싸기 %s' % (w, h, used, len(b), '같음' if encode(w, h, px) == b[:used] else '다름'))
    if len(sys.argv) > 2:
        to_png(w, h, px).save(sys.argv[2])
