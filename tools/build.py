# -*- coding: utf-8 -*-
r"""유나 리믹스 한글 빌드 (2026-10-01) — 원본 트랙 1 → work/out/…(Track 1).bin
  ① 번역 = my files/tsv/yunaremix_*.tsv «번역» 열(trmerge 로 병합·정규화된 것). 빌드 전에 rules.check 로 다시 전수 검사(걸리면 중단).
  ② 글꼴 KANJI.FON(16×16 1bpp × 7,806, 칸 = JIS (구−1)×94+(점−1)): 한글 음절을 JIS 한자 칸 16구부터 차례로 «전부» 덮어씀
     (사용자 «글자칸은 장난하지 말고 전부 써라» — 안 쓰는 칸 고르기 금지). 글리프 = 갈무리11, 게임이 찍는 x 4‥15 안(poc.glyph).
  ③ YUNA1.DAT 블록(32 KB)마다:
     · 대사: 번호표(T=S+B, u16, 기준 M) 순서대로 대사 영역을 M 부터 새로 이어 씀(얼굴 머리 1바이트 보존, \n → 0x0A, 00 끝) — 코드는 번호로 부르니 안 건드림.
     · 메뉴(문자열 영역, S 기준 오프셋): 원래 길이 안이면 제자리(남는 바이트 0). 길면 대사 영역 뒤 빈 곳으로 옮기고
       그 문자열을 가리키는 명령 인수만 고침 — 0x200F·0x2013 의 인수 1(전수 확인: 옮길 46개 모두 이 두 자리, 나머지 일치는 숫자 우연).
     · 블록 ≤ 0x8000 검사.
  ④ 그림: 옵션 TITPS.CSA·달력 CALDATA/CLTES3.GS8(gfx.py) · 제목 TBG00‥12.SS1(gfx_title.py)
  ⑤ 동영상: work/kr/*.CPK(moviesub.py 자막 16 · moviecap.py 지명 캡션 7) 제자리
  python tools/build.py → work/out/Ginga Ojousama Densetsu Yuna Remix (Japan) (Track 1).bin
"""
import glob, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, r'C:\claude\project\anearth-kr-patch\tools')
import bdf, iso, rules, gfx, gfx_title, poc
import dat as DATP

ROM = poc.ROM
OUT = poc.OUT
BLK = 0x8000
NL = rules.NL
STR_OPS = {(0x200F, 1), (0x2013, 1)}


def load_tr():
    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'my files', 'tsv', 'yunaremix_*.tsv'))):
        for ln in open(f, encoding='utf-8').read().split('\n')[1:]:
            c = ln.split('\t')
            if len(c) == 8:
                rows.append(c)
    return rows


def ku_ten_code(ku, ten):
    """JIS 구·점 → SJIS 2바이트"""
    j1, j2 = ku + 0x20, ten + 0x20
    s1 = (j1 + 1) // 2 + (0x70 if j1 <= 0x5E else 0xB0)
    s2 = j2 + (0x1F if j1 % 2 else 0x7E)
    if s2 >= 0x7F and j1 % 2:
        s2 += 1
    return bytes([s1, s2])


class Font:
    def __init__(self, fon, F):
        self.fon = fon; self.F = F; self.map = {}
        self.slots = [(ku, ten) for ku in range(16, 84) for ten in range(1, 95) if ((ku - 1) * 94 + ten - 1) * 32 + 32 <= len(fon)]

    def code(self, ch):
        if ch not in self.map:
            if len(self.map) >= len(self.slots):
                raise SystemExit('⛔글꼴 칸 모자람')
            ku, ten = self.slots[len(self.map)]
            c = ku_ten_code(ku, ten)
            assert poc.jis_index(c) == (ku - 1) * 94 + ten - 1, (ku, ten, c.hex())
            i = poc.jis_index(c)
            self.fon[i * 32:i * 32 + 32] = poc.glyph(self.F, ch)
            self.map[ch] = c
        return self.map[ch]

    def enc(self, t):
        out = bytearray()
        for k, line in enumerate(t.split(NL)):
            if k:
                out.append(0x0A)
            for ch in line:
                if '가' <= ch <= '힣':
                    out += self.code(ch)
                else:
                    out += ch.encode('cp932')
        return bytes(out)


BIN_BASE = 0x06004000
BIN_FREE = (0x38C00, 0x3C400)        # 111.BIN 안 0 영역(RAM 0x0603CC00‥0x06040400): 리터럴 참조 0 · 스테이트 3개(대사·옵션·달력) 모두 0
                                     # (0x06040404‥0x06040607 은 쓰이는 버퍼라 그 앞에서 끊음)


def patch_bin(font):
    """111.BIN 시스템 메시지(work/trans/bin_ko.tsv, 오프셋 = tools/binx.py 의 포인터 참조 시작) —
       원래 바이트 안이면 제자리(남는 바이트 0), 길면 BIN_FREE 로 옮기고 그 문자열을 가리키는 4바이트 정렬 포인터(전부)를 고침"""
    import binx
    b = bytearray(open(os.path.join(ROOT, 'work', 'disc', '111.BIN'), 'rb').read())
    found = {o: (refs, s) for o, refs, s, t in binx.scan(bytes(b))}
    spans = sorted((o, o + len(s)) for o, (r, s) in found.items())
    for (a0, a1), (b0_, b1) in zip(spans, spans[1:]):
        assert b0_ >= a1, ('문자열 겹침', hex(a0), hex(b0_))
    assert not any(b[BIN_FREE[0]:BIN_FREE[1]]), '옮길 자리가 0 이 아님'
    cur = BIN_FREE[0]; nin = nmv = 0; errs = []
    for ln in open(os.path.join(ROOT, 'work', 'trans', 'bin_ko.tsv'), encoding='utf-8').read().split('\n')[1:]:
        if not ln.strip():
            continue
        o, t = ln.split('\t'); o = int(o, 16)
        if o not in found:
            errs.append('%X 원문 문자열 아님' % o); continue
        refs, s = found[o]
        t = rules.norm(t)
        if rules.JP.search(t):
            errs.append('%X 가나·한자 남음' % o); continue
        enc = font.enc(t)
        if len(enc) <= len(s):
            b[o:o + len(s)] = enc + bytes(len(s) - len(enc)); nin += 1
            continue
        if cur + len(enc) + 1 > BIN_FREE[1]:
            errs.append('옮길 자리 모자람'); break
        b[cur:cur + len(enc) + 1] = enc + b'\0'
        for r in refs:
            struct.pack_into('>I', b, r, BIN_BASE + cur)
        cur = (cur + len(enc) + 1 + 1) & ~1; nmv += 1
    if errs:
        raise SystemExit('⛔111.BIN ' + ' · '.join(errs[:10]))
    print('111.BIN 시스템 메시지 제자리 %d · 옮김 %d (%d B 사용)' % (nin, nmv, cur - BIN_FREE[0]))
    return bytes(b)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    rows = load_tr()
    print(rules.BANNER)
    errs = []
    for c in rows:
        e, _ = rules.check(c, c[7])
        errs += ['%s %s' % (c[0], x) for x in e]
        if not c[7].strip():
            errs.append('%s 번역 빔' % c[0])
    if errs:
        for e in errs[:30]:
            print('⛔', e)
        raise SystemExit('⛔번역 검사 오류 %d건 — 빌드 중단' % len(errs))
    dat = bytearray(open(os.path.join(ROOT, 'work', 'disc', 'YUNA1.DAT'), 'rb').read())
    fon = bytearray(open(os.path.join(ROOT, 'work', 'disc', 'KANJI.FON'), 'rb').read())
    font = Font(fon, bdf.Font(poc.FONT))
    msg = {}; menu = {}
    for c in rows:
        if c[0][0] == 'M':
            b, k = c[1].split(':'); msg[(int(b, 16) * BLK, int(k))] = (c[3], c[7])
        else:
            for loc in c[1].split():
                b, o = loc.split('@'); menu[(int(b, 16) * BLK, int(o, 16))] = c[7]
    nmsg = nin = nmove = 0
    for b0 in range(0, len(dat), BLK):
        d = bytearray(dat[b0:b0 + BLK])
        A, B, C, E = struct.unpack_from('<HHHH', d, 0)
        S = A + 6; T = S + B; M = T + C
        offs = list(struct.unpack_from('<%dH' % (C // 2), d, T))
        # 대사 영역 새로
        old_end = max(d.index(0, M + o) + 1 for o in offs if M + o < BLK)
        new = bytearray(); seen = {}; newoffs = []
        for k, o in enumerate(offs):
            if M + o >= BLK:
                newoffs.append(o); continue
            if o in seen:
                newoffs.append(seen[o]); continue
            s = bytes(d[M + o:d.index(0, M + o)])
            if (b0, k) in msg:
                face, t = msg[(b0, k)]
                head = s[:1] if face else b''
                assert (face.encode() == head) if face else True, (hex(b0), k, face, head)
                s = head + font.enc(t); nmsg += 1
            seen[o] = len(new); newoffs.append(len(new))
            new += s + b'\0'
        if M + len(new) > BLK:
            raise SystemExit('⛔블록 0x%X 대사 영역 넘침' % b0)
        d[M:old_end] = bytes(old_end - M)
        d[M:M + len(new)] = new
        struct.pack_into('<%dH' % len(newoffs), d, T, *newoffs)
        tail = M + len(new)
        # 메뉴 문자열
        blk = None
        for (mb, o), t in sorted(menu.items()):
            if mb != b0:
                continue
            old = bytes(d[S + o:d.index(0, S + o)])
            enc = font.enc(t)
            if len(enc) <= len(old):
                d[S + o:S + o + len(old)] = enc + bytes(len(old) - len(enc)); nin += 1
                continue
            if blk is None:
                blk = DATP.Block(bytes(dat[b0:b0 + BLK]), b0)
            no = tail - S
            d[tail:tail + len(enc) + 1] = enc + b'\0'; tail += len(enc) + 1
            if tail > BLK:
                raise SystemExit('⛔블록 0x%X 넘침(메뉴 옮김)' % b0)
            hit = 0
            for p, op, fl, a in blk.ins:
                for kk, v in enumerate(a):
                    if v == o and (op, kk) in STR_OPS and not fl >> (15 - kk) & 1:
                        struct.pack_into('<H', d, p + 4 + 2 * kk, no); hit += 1
            if not hit:
                raise SystemExit('⛔블록 0x%X 메뉴 @%X 참조를 못 찾음' % (b0, o))
            nmove += 1
        dat[b0:b0 + BLK] = d
    exe = patch_bin(font)
    with open(os.path.join(ROOT, 'work', 'trans', 'charmap.tsv'), 'w', encoding='utf-8', newline=chr(10)) as fh:   # 검산·디버그용
        fh.write('글자' + chr(9) + 'SJIS' + chr(10) + ''.join(k + chr(9) + v.hex().upper() + chr(10) for k, v in font.map.items()))
    print('대사 %d · 메뉴 제자리 %d · 옮김 %d · 한글 음절 %d / 칸 %d (16구‥)' % (nmsg, nin, nmove, len(font.map), len(font.slots)))
    G, _, _, _ = gfx.build()
    files = {'YUNA1.DAT': bytes(dat), 'KANJI.FON': bytes(fon), 'TITPS.CSA': G['TITPS.CSA'], '111.BIN': exe}
    files.update(gfx_title.main())
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    iso.patch(ROM, OUT, files)
    sub = {'CALDATA/CLTES3.GS8': G['CALDATA/CLTES3.GS8']}
    # ⑤ 동영상(tools/moviesub.py 자막 · tools/moviecap.py 지명 캡션이 구운 work/kr/<영상>.CPK, 원본 크기 그대로 — 느려서 빌드 때 다시 굽지 않음)
    import moviesub
    mov = {moviesub.disc_path(os.path.basename(p)[:-4]): open(p, 'rb').read()
           for p in sorted(glob.glob(os.path.join(ROOT, 'work', 'kr', '*.CPK')))}
    print('동영상 %d개' % len(mov))
    sub.update(mov)
    iso.patch_sub(OUT, sub)
    print('→', OUT)


if __name__ == '__main__':
    main()
