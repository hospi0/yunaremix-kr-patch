# -*- coding: utf-8 -*-
r"""빌드 결과 검산 (2026-10-01) — 출력 트랙 1 에서 YUNA1.DAT·KANJI.FON 을 디렉터리로 다시 읽어
  · 대사: 번호표 → 바이트 → work/trans/charmap.tsv 로 되돌린 글이 번역과 같은지(얼굴 머리 떼고)
  · 메뉴: 그 문자열을 가리키는 0x200F·0x2013 인수(옮긴 것) 또는 제자리 오프셋의 글이 번역과 같은지
  · 글리프: charmap 의 칸마다 KANJI.FON 그림 = 갈무리11 글리프
  python tools/verify.py
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import iso, build, rules, poc, bdf
import dat as DATP


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    fh = open(build.OUT, 'rb'); T = iso.tree(fh)
    l, s, _, _ = T['YUNA1.DAT']; d = iso.read_user(fh, l, (s + 2047) // 2048)[:s]
    l, s, _, _ = T['KANJI.FON']; fon = iso.read_user(fh, l, (s + 2047) // 2048)[:s]
    orig = open(os.path.join(ROOT, 'work', 'disc', 'YUNA1.DAT'), 'rb').read()
    rev = {}
    for ln in open(os.path.join(ROOT, 'work', 'trans', 'charmap.tsv'), encoding='utf-8').read().split('\n')[1:]:
        if ln:
            ch, h = ln.split('\t'); rev[bytes.fromhex(h)] = ch
    F = bdf.Font(poc.FONT)
    gbad = sum(1 for c, ch in rev.items() if fon[poc.jis_index(c) * 32:poc.jis_index(c) * 32 + 32] != poc.glyph(F, ch))

    def dec(b):
        o = ''; i = 0
        while i < len(b):
            if b[i] == 10:
                o += rules.NL; i += 1
            elif b[i] >= 0x81:
                p = bytes(b[i:i + 2]); o += rev.get(p) or p.decode('cp932'); i += 2
            else:
                o += chr(b[i]); i += 1
        return o
    rows = build.load_tr(); mbad = sbad = mn = sn = 0
    blocks = {}
    for c in rows:
        if c[0][0] == 'M':
            b, k = c[1].split(':'); b0 = int(b, 16) * 0x8000; blk = d[b0:b0 + 0x8000]
            A, B, C, E = struct.unpack_from('<HHHH', blk, 0); S = A + 6; Tt = S + B; M = Tt + C
            o = struct.unpack_from('<H', blk, Tt + 2 * int(k))[0]; x = blk[M + o:blk.index(0, M + o)]
            if c[3]:
                assert x[:1] == c[3].encode(), (c[0], x[:1])
                x = x[1:]
            mn += 1; mbad += dec(x) != c[7]
            if dec(x) != c[7] and mbad < 5:
                print('대사 불일치', c[0], dec(x)[:30], '|', c[7][:30])
        else:
            for loc in c[1].split():
                b, o = loc.split('@'); b0 = int(b, 16) * 0x8000; o = int(o, 16)
                blk = d[b0:b0 + 0x8000]; A, B = struct.unpack_from('<HH', blk, 0); S = A + 6
                if b0 not in blocks:
                    try:
                        blocks[b0] = (DATP.Block(orig[b0:b0 + 0x8000], b0), DATP.Block(blk, b0))
                    except ValueError:
                        blocks[b0] = None
                targets = [o]
                if blocks[b0]:
                    ob, nb = blocks[b0]
                    targets = [na[k] for (p, op, fl, oa), (_, _, _, na) in zip(ob.ins, nb.ins) for k, v in enumerate(oa)
                               if v == o and (op, k) in build.STR_OPS and not fl >> (15 - k) & 1] or [o]
                for t in targets:
                    x = blk[S + t:blk.index(0, S + t)]
                    sn += 1; sbad += dec(x) != c[7]
                    if dec(x) != c[7] and sbad < 5:
                        print('메뉴 불일치', c[0], loc, dec(x), '|', c[7])
    print('대사 %d 불일치 %d · 메뉴 자리 %d 불일치 %d · 글리프 %d 불일치 %d' % (mn, mbad, sn, sbad, len(rev), gbad))
    return mbad + sbad + gbad


if __name__ == '__main__':
    sys.exit(1 if main() else 0)
