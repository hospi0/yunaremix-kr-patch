# -*- coding: utf-8 -*-
r"""유나 리믹스 111.BIN(실행 파일, 적재 0x06004000) 일본어 문자열 찾기 (2026-10-01)
  후보 = 정렬된 u32 포인터(0x06004000+오프셋)가 가리키는 자리에서 NUL 까지가 SJIS 로 풀리고 일본어(가나·한자)를 담은 것.
  ⚠유나 3 교훈: 문자열 추출이 «코드 리터럴 아래 절반»을 삼킬 수 있음 — 포인터로 가리켜진 시작만 씀(코드 바이트 오인 막기).
  python tools/binx.py → work/text/bin_strings.tsv (오프셋·참조 수·바이트·원문)
"""
import os, re, struct, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
BIN = os.path.join(ROOT, 'work', 'disc', '111.BIN')
BASE = 0x06004000
JP = re.compile('[぀-ヿ一-鿿]')


def scan(b):
    refs = collections.defaultdict(list)
    for i in range(0, len(b) - 3, 4):
        v = struct.unpack_from('>I', b, i)[0]
        if BASE <= v < BASE + len(b):
            refs[v - BASE].append(i)
    out = []
    for o in sorted(refs):
        try:
            e = b.index(0, o)
        except ValueError:
            continue
        s = b[o:e]
        if not s or len(s) > 200:
            continue
        try:
            t = s.decode('cp932')
        except UnicodeDecodeError:
            continue
        if not JP.search(t):
            continue
        if any(ord(ch) < 0x20 and ch not in '\n' for ch in t):
            continue
        out.append((o, refs[o], s, t))
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    b = open(BIN, 'rb').read()
    rows = scan(b)
    os.makedirs(os.path.join(ROOT, 'work', 'text'), exist_ok=True)
    with open(os.path.join(ROOT, 'work', 'text', 'bin_strings.tsv'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('오프셋\t참조\t바이트\t원문\n')
        for o, r, s, t in rows:
            fh.write('%X\t%d\t%d\t%s\n' % (o, len(r), len(s), t.replace('\n', '\n')))
    print(len(rows))
