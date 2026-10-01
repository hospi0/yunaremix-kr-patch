# -*- coding: utf-8 -*-
r"""유나 3 — YUNA1.DAT 스크립트 블록 해석·텍스트 참조 목록 (2026-09-28, docs/01 «대사»)
  블록 = 0x8000(32KB) × 130. [u16 A][u16 B][…] 코드 = +6 ‥ A+2, 문자열 기준점 S = A+6(문자열 영역 길이 B, NUL 종료 SJIS)
  명령 = [u16 op][u16 플래그][u16 인수 × (op >> 12)] — 플래그 비트 15-k 가 서 있으면 인수 k 는 변수(즉값 아님)
  문자열 인수 = S 기준 u16 바이트 오프셋. 텍스트 자리(전수 판정, 일본어 3,352/3,352):
    0x5002 인수2(블록 안 서브루틴 호출 — arg0 = 호출 대상, «모든 호출이 일본어»인 대상만 대사 루틴) ·
    0x50B7 인수3 · 0x2017 인수0 · 0x2013 인수1 · 0x1017 인수0 · 0x60BF 인수1·5 · 0x6094 인수1·4 · 0x1046 인수0 · 0xB08B 인수2 · 0x3017 인수0
  python tools/dat.py → 검사 + work/text/dat_refs.tsv (ID·블록·오프셋·참조 수·원문)
"""
import collections, os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
DAT = os.path.join(ROOT, 'work', 'disc', 'YUNA1.DAT')
BLK = 0x8000
TEXT = {(0x50B7, 3), (0x2017, 0), (0x2013, 1), (0x1017, 0), (0x60BF, 1), (0x60BF, 5), (0x6094, 1), (0x6094, 4),
        (0x1046, 0), (0xB08B, 2), (0x3017, 0)}
JP = re.compile('[\u3040-\u30ff\u4e00-\u9fff\uff01-\uff5e]')


class Block:
    def __init__(self, d, b0):
        self.b0 = b0; self.d = d
        self.A, self.B = struct.unpack_from('<HH', d, 0)
        self.S = self.A + 6
        self.strings = {}; p = 0
        for x in d[self.S:self.S + self.B].split(b'\0'):
            self.strings[p] = x; p += len(x) + 1
        self.ins = []; p = 6
        while p < self.A + 2:
            op, fl = struct.unpack_from('<HH', d, p); n = op >> 12
            self.ins.append((p, op, fl, struct.unpack_from('<%dH' % n, d, p + 4)))
            p += 4 + 2 * n
        if p != self.A + 2:
            raise ValueError('블록 0x%X: 명령이 A+2 에서 안 끝남(%X)' % (b0, p))

    def is_jp(self, o):
        x = self.strings.get(o)
        return bool(o and x is not None and JP.search(x.decode('cp932', 'ignore')) and not x.lower().endswith(b'.acm'))

    def text_refs(self):
        """→ [(인수 바이트 위치, 문자열 오프셋)] — 텍스트 자리만"""
        calls = collections.defaultdict(list)
        for p, op, fl, a in self.ins:
            if op == 0x5002 and not fl & 0x2000:
                calls[a[0]].append((p + 4 + 2 * 2, a[2]))
        out = []
        for tgt, cs in calls.items():
            flags = [self.is_jp(o) for _, o in cs]
            if all(flags):
                out += cs
            elif any(flags):
                raise ValueError('블록 0x%X: 0x5002 대상 %d 에 대사/비대사 섞임' % (self.b0, tgt))
        for p, op, fl, a in self.ins:
            for k, v in enumerate(a):
                if (op, k) in TEXT and not fl >> (15 - k) & 1 and v in self.strings and v:
                    out.append((p + 4 + 2 * k, v))
        return out


ESC = {chr(10): chr(92) + 'n', chr(9): chr(92) + 't', chr(92): chr(92) * 2, '{': chr(92) + '{'}


def text_of(x):
    r"""원문 바이트 → 표기(가역): SJIS 글자, 해석 안 되는 2바이트는 {XXXX}, 줄바꿈 \n, 탭 \t, 역슬래시 \\, 여는 중괄호 \{"""
    out = []; i = 0
    while i < len(x):
        c = x[i]
        if 0x81 <= c <= 0x9F or 0xE0 <= c <= 0xFC:
            try:
                out.append(x[i:i + 2].decode('cp932'))
            except UnicodeDecodeError:
                out.append('{%s}' % x[i:i + 2].hex().upper())
            i += 2
        else:
            ch = chr(c)
            out.append(ESC.get(ch, ch)); i += 1
    return ''.join(out)


def blocks():
    D = open(DAT, 'rb').read()
    for b0 in range(0, len(D), BLK):
        d = D[b0:b0 + BLK]
        if struct.unpack_from('<H', d, 0)[0]:
            yield Block(d, b0)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    rows = []; tot = cov = 0
    for b in blocks():
        refs = collections.Counter(o for _, o in b.text_refs())
        for o, x in b.strings.items():
            if not b.is_jp(o):
                continue
            tot += 1; cov += bool(refs[o])
            if refs[o]:
                rows.append(('D%03X%04X' % (b.b0 >> 15, o), '%X' % b.b0, '%X' % o, str(refs[o]),
                             text_of(x)))
    if cov != tot:
        sys.exit('⛔일본어 문자열 %d 중 %d 만 텍스트 자리로 참조됨' % (tot, cov))
    os.makedirs(os.path.join(ROOT, 'work', 'text'), exist_ok=True)
    p = os.path.join(ROOT, 'work', 'text', 'dat_refs.tsv')
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write('ID\t블록\t오프셋\t참조\t원문\n' + ''.join('\t'.join(r) + '\n' for r in rows))
    print('블록 %d · 일본어 문자열 %d 전부 참조 확인 · 글자 %d → %s' % (
        sum(1 for _ in blocks()), tot, sum(len(r[4]) for r in rows), p))


if __name__ == '__main__':
    main()
