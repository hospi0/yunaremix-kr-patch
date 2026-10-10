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
    # ★글 창 버튼 대기 0x0602098C 의 «음성 재생 중이면(0x0601F174 ≠0) 버튼을 안 읽고 기다림»을 건너뜀 →
    #   음성이 나오는 동안에도 창을 넘길 수 있다(2026-10-09 실기 «음성이 다 끝나야 넘어감» — 긴 음성 하나에 창 여럿인 새 자막).
    #   원래 대본의 음성 562곳은 전부 뒤에 0x0041(음성 끝 대기)이 있어 일반 대사의 음성은 안 끊긴다(전수 확인).
    o = 0x060209AC - BIN_BASE
    assert bytes(b[o:o + 4]) == bytes.fromhex('480B0009'), '버튼 대기 자리 다름'
    b[o:o + 4] = bytes.fromhex('E0000009')            # JSR @R8(음성 재생 중?) ; NOP → MOV #0,R0 ; NOP
    # ★전투 이름 길이 표(2026-10-10 «요시와 공격»): 「의 공격」「의 대미지…」 같은 꼬리는 x = 이름 x + 표[인물]×글자 폭 에 찍는다
    #   (0x0600DDD0 0x0604E2B4[인물] × 0x0604E100). 표 = 원문 글자 수라 한글 이름이 길면 꼬리가 이름 끝 글자 위에 겹쳤다(요시카+의 → «와»).
    #   → 이름 표 0x0604E590(8 B 간격, 이름 포인터)의 각 이름을 «번역 글자 수»로 다시 채움(짧은 이름 사이 빈칸도 사라짐).
    ko = {}
    for ln in open(os.path.join(ROOT, 'work', 'trans', 'bin_ko.tsv'), encoding='utf-8').read().split('\n')[1:]:
        if ln.strip():
            oo, t = ln.split('\t'); ko[int(oo, 16)] = rules.norm(t)
    NAMES, LENS = 0x0604E590 - BIN_BASE, 0x0604E2B4 - BIN_BASE
    for i in range(18):
        p = struct.unpack_from('>I', DAT_BIN0, NAMES + 8 * i)[0] - BIN_BASE
        jp = DAT_BIN0[p:DAT_BIN0.index(0, p)].decode('cp932')
        assert struct.unpack_from('>I', DAT_BIN0, LENS + 4 * i)[0] == len(jp), ('이름 길이 표가 원문 글자 수와 다름', i)
        struct.pack_into('>I', b, LENS + 4 * i, len(ko[p]))
    return bytes(b)


DAT_BIN0 = open(os.path.join(ROOT, 'work', 'disc', '111.BIN'), 'rb').read()   # 원본 111.BIN(이름 길이 표 검산용)


# ★글 없이 음성만 나오는 장면에 자막 붙이기(2026-10-09, docs/01 «자막 없는 음성»)
#   대본이 [0x103F 음성][0x0041 대기] 만 늘어놓고 글(DAT 에 있음 — 대본이 안 부를 뿐)을 안 띄운다.
#   → run(연속한 음성 자리)의 첫 0x103F 를 점프(0x1001, 주소 = 코드 기준 = 블록 오프셋 − 6)로 바꾸고, 코드 끝(마지막 0x0003 앞)에
#     다른 대사와 같은 호출을 이어 붙인 뒤 되돌아온다. 0x5002 [루틴][얼굴][글 번호][일련번호][음성] · 0x4002 [루틴][글 번호][일련번호][음성]
#     (일련번호 ≠0 = 음성+글+대기, 0 = 글만 — 한 음성에 대사가 여럿이면 둘째부터 0). 글이 없는 자리는 원래 [103F][0041] 그대로.
#     그 뒤 문자열·대사표는 통째로 밀고 머리 A 만 늘림(참조는 전부 S 기준이라 그대로).
#   다른 블록에만 있는 글은 대사표 끝에 새 번호로 덧붙이고(C 늘림, 대사 영역은 M 기준이라 그대로) 번역도 그 행 것을 씀.
#   표 = tools/voice_table.py(python tools/voicetext.py table 이 받아쓰기·짝짓기로 만듦). 1장 블록 0x30000 은 실기 «완벽» 판 그대로.
import voice_table
VOICE_TEXT = dict(voice_table.VOICE_TEXT)
VOICE_TEXT[0x30000] = [dict(at=0x0C36, back=0x0C90, spots=[(w, [(0x5002, sub, face, k, seq)]) for sub, face, k, seq, w in [
    (0x100C, 0, 0x70, 0xD8, 'A_353.ACM'), (0x100C, 0, 0x72, 0xD9, 'A_354.ACM'), (0x10CC, 0, 0x73, 0xDA, 'A_355.ACM'),
    (0x100C, 0, 0x74, 0xDB, 'A_356A.ACM'), (0x10CC, 0, 0x75, 0xDC, 'A_357.ACM'), (0x10CC, 0, 0x76, 0xDD, 'A_358.ACM'),
    (0x10CC, 0, 0x77, 0xDE, 'A_359.ACM'), (0x100C, 0, 0x78, 0xDF, 'A_356.ACM'), (0x100C, 0, 0x79, 0xDF, 'A_360.ACM')]])]
DAT0 = open(os.path.join(ROOT, 'work', 'disc', 'YUNA1.DAT'), 'rb').read()
import voicetext
VOICE_NEW = voicetext.load_new()


def add_voice_text(d, b0, msg):
    A, B, C = struct.unpack_from('<3H', d, 0); S = A + 6
    strs = {}; p = 0
    for x in bytes(d[S:S + B]).split(b'\0'):
        strs[x] = strs.get(x, p); p += len(x) + 1
    ntab = C // 2; newtexts = []                                  # 다른 블록 글 → 새 번호
    code = bytearray(); base = A + 6          # ★마지막 0003(= 마지막 대사 루틴의 복귀) «뒤» — 앞에 넣으면 그 루틴이 덧붙인 코드로 흘러든다(2026-10-09 실기: 매니저 대사 뒤 1장 음성 재생)
    for run in VOICE_TEXT[b0]:
        p = run['at']; start = base + len(code)
        for wav, lines in run['spots']:
            op, fl, a0 = struct.unpack_from('<HHH', d, p); op2 = struct.unpack_from('<H', d, p + 6)[0]
            assert (op, fl, op2) == (0x103F, 0, 0x0041) and a0 == strs[wav.encode()], ('음성 자리 다름', hex(b0), hex(p), wav)
            p += 10
            if not lines:
                code += struct.pack('<5H', 0x103F, 0, a0, 0x0041, 0); continue
            if lines == 'new':                                     # 글이 없던 음성: 음성 → 해설 창(얼굴 없음) 차례로 → 음성 끝 대기
                code += struct.pack('<3H', 0x103F, 0, a0)
                for jp, kr in VOICE_NEW[wav.upper()[:-4]]:
                    k = ntab + len(newtexts); newtexts.append(jp.replace(NL, chr(10)).encode('cp932'))
                    m = ['M99999', '0:0', '해설', '', '24', '1', jp, kr]
                    t = rules.norm(kr, jp, m); e, _ = rules.check(m, t)
                    if e:
                        raise SystemExit('⛔음성 새 자막 %s: %s' % (wav, e))
                    msg[(b0, k)] = ('', t)
                    code += struct.pack('<3H', 0x1017, 0, k)
                code += struct.pack('<2H', 0x0041, 0); continue
            for i, (op, sub, face, tx, seq) in enumerate(lines):
                if isinstance(tx, (tuple, list)):
                    _, sb, sk = tx
                    sA, sB, sC = struct.unpack_from('<3H', DAT0, sb); sT = sb + sA + 6 + sB; sM = sT + sC
                    so = struct.unpack_from('<H', DAT0, sT + 2 * sk)[0]
                    jp = DAT0[sM + so:DAT0.index(0, sM + so)]
                    if (sb, sk) not in msg:
                        raise SystemExit('⛔음성 자막: 베껴 올 번역 없음 %X:%X' % (sb, sk))
                    tx = ntab + len(newtexts); newtexts.append(jp); msg[(b0, tx)] = msg[(sb, sk)]
                sq = seq if i == 0 else 0
                code += (struct.pack('<7H', 0x5002, 0, sub, face, tx, sq, a0) if op == 0x5002 else
                         struct.pack('<6H', 0x4002, 0, sub, tx, sq, a0))
        assert p == run['back'], (hex(b0), hex(p))
        code += struct.pack('<3H', 0x1001, 0, run['back'] - 6)
        struct.pack_into('<3H', d, run['at'], 0x1001, 0, start - 6)   # 나머지 옛 명령 바이트는 건너뛰어 안 쓰임
    assert struct.unpack_from('<HH', d, A + 2) == (0x0003, 0), '코드 끝 0003 아님'
    code += struct.pack('<2H', 0x0003, 0)      # 블록 모양 유지: 마지막 명령 = 0003, 그 시작 = A+2
    grow = len(code) + 2 * len(newtexts)
    assert not any(d[BLK - grow - sum(len(t) + 1 for t in newtexts):]), '블록 끝 빈 곳 부족 %X' % b0
    d = bytearray(d[:base] + code + d[base:BLK - len(code)])
    A += len(code); struct.pack_into('<H', d, 0, A)
    if newtexts:                                                   # 대사표 끝에 새 번호(M 이 2n 밀림 — 대사 영역은 M 기준이라 그대로)
        S = A + 6; T = S + B; M = T + C
        offs = struct.unpack_from('<%dH' % ntab, d, T)
        end = max(d.index(0, M + o) + 1 for o in offs if M + o < BLK)
        add = bytearray(); no = []
        for jp in newtexts:
            no.append(end + 2 * len(newtexts) + len(add) - (M + 2 * len(newtexts))); add += jp + b'\0'
        d = bytearray(d[:M] + struct.pack('<%dH' % len(no), *no) + d[M:end] + add + d[end:])[:BLK]
        struct.pack_into('<H', d, 4, C + 2 * len(newtexts))
    return d


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
        if b0 in VOICE_TEXT:
            d = add_voice_text(d, b0, msg)
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
