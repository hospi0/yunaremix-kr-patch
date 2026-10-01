# -*- coding: utf-8 -*-
r"""유나 리믹스 제목 화면 TBG00‥12.SS1 = 달력 그림 CALDATA/CAL00‥12S.SS1(옅은 판) + 로고 덧그림 (2026-10-01 확인)
  디코더는 끝 픽셀이 모자란 SS1 을 0 으로 채움(리믹스 SS1 596장)."""
import os, struct
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'work', 'gsrc')


def dec(b):
    w, h = struct.unpack_from('>HH', b, 0); px = []; i = 4; n = w * h
    while len(px) < n and i < len(b):
        c = b[i]
        if c < 0x80:
            if i + 3 > len(b):
                break
            px += [struct.unpack_from('>H', b, i + 1)[0]] * c; i += 3
        else:
            if i + 2 > len(b):
                break
            px.append(struct.unpack_from('>H', b, i)[0]); i += 2
    return w, h, (px + [0] * n)[:n]


def load(name):
    return dec(open(os.path.join(SRC, name), 'rb').read())
