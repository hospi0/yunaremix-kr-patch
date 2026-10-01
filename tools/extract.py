# -*- coding: utf-8 -*-
r"""유나 리믹스 번역 TSV 뽑기 (2026-10-01) — YUNA1.DAT(32 KB 블록 26개)
  블록 머리 u16 LE A·B·C·E · 문자열 S=A+6(길이 B, 명령 메뉴·선택지·변수 이름) · 대사 번호표 T=S+B(u16 × C/2, 기준 M=T+C) · 대사(SJIS 00 끝)
  대사 첫 바이트가 ASCII(«B»·«3»·«7»·«2»·«4»·«6») = 얼굴(초상화) 코드 → 번역 칸에 넣지 않고 «얼굴» 열로 뺌.
  ★한 줄 폭(2026-10-01 실기 스샷 실측, 12px 칸): 초상화 대사는 글이 x=87 부터 → 19칸 · 해설(얼굴 없음)은 x=16 부터 → 24칸.
    (원문은 둘 다 최대 19칸 — 줄바꿈은 원문처럼 직접 \n, 엔진 자동 줄바꿈 없음 확인 전)
  행: 대사 = (블록, 대사 번호)마다 한 행(장면 순서 그대로) · 메뉴 = 문자열 영역의 일본어, 같은 글은 한 행(위치 여러 개, 공유 수).
  표기: 줄바꿈 \n (원문은 0x0A) · 띄어쓰기 = 전각 공백(빌더가 바꿈)
  python tools/extract.py → my files/tsv/yunaremix_NNN.tsv (29 KB 단위, 자투리는 앞 파일에 합침)
"""
import collections, os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
DAT = os.path.join(ROOT, 'work', 'disc', 'YUNA1.DAT')
OUT = os.path.join(ROOT, 'my files', 'tsv')
BLK = 0x8000
JP = re.compile('[぀-ヿ一-鿿！-～]')
W_FACE, W_NARR = 19, 24
HEAD = ['ID', '위치', '구분', '얼굴', '줄폭', '공유', '원문', '번역']


def blocks(dat):
    for b0 in range(0, len(dat), BLK):
        d = dat[b0:b0 + BLK]
        A, B, C, E = struct.unpack_from('<HHHH', d, 0)
        S = A + 6; T = S + B; M = T + C
        yield b0, d, S, B, T, C, M


def show(x):
    return x.decode('cp932').replace('\n', '\\n')


def rows(dat):
    msg = []; menu = collections.OrderedDict()
    for b0, d, S, B, T, C, M in blocks(dat):
        offs = struct.unpack_from('<%dH' % (C // 2), d, T)
        for k, o in enumerate(offs):
            if M + o >= BLK:
                continue
            s = d[M + o:d.index(0, M + o)]
            if not s:
                continue
            face = s[:1].decode() if s[:1].isascii() and s[:1] != b'\n' else ''
            body = s[1:] if face else s
            if not JP.search(body.decode('cp932')):
                continue
            msg.append(['%X:%d' % (b0 // BLK, k), '디버그' if b0 == 0 else '대사', face, W_FACE if face else W_NARR, show(body)])
        p = 0
        for x in d[S:S + B].split(b'\0'):
            t = x.decode('cp932', 'replace')
            if JP.search(t):
                key = ('디버그' if b0 == 0 else '메뉴', show(x))
                menu.setdefault(key, []).append('%X@%X' % (b0 // BLK, p))
            p += len(x) + 1
    out = []
    for i, (loc, kind, face, w, text) in enumerate(msg, 1):
        out.append(['M%05d' % i, loc, kind, face, str(w), '1', text, ''])
    for i, ((kind, text), locs) in enumerate(menu.items(), 1):
        out.append(['S%04d' % i, ' '.join(locs), kind, '', '', str(len(locs)), text, ''])
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    dat = open(DAT, 'rb').read()
    rs = rows(dat)
    os.makedirs(OUT, exist_ok=True)
    lines = ['\t'.join(r) + '\n' for r in rs]
    head = '\t'.join(HEAD) + '\n'
    parts = []; cur = []; size = 0
    for ln in lines:
        n = len(ln.encode('utf-8'))
        if cur and size + n > 29 * 1024:
            parts.append(cur); cur = []; size = 0
        cur.append(ln); size += n
    if cur:
        if parts and size < 10 * 1024:
            parts[-1] += cur
        else:
            parts.append(cur)
    for i, p in enumerate(parts, 1):
        open(os.path.join(OUT, 'yunaremix_%03d.tsv' % i), 'w', encoding='utf-8', newline='').write(head + ''.join(p))
    kinds = collections.Counter(r[2] for r in rs)
    chars = sum(len(r[6].replace('\\n', '')) for r in rs)
    print('행 %d (%s) · %d자 · 파일 %d개 → %s' % (len(rs), dict(kinds), chars, len(parts), OUT))


if __name__ == '__main__':
    main()
