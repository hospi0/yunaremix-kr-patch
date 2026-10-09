# -*- coding: utf-8 -*-
r"""유나 리믹스 PoC (2026-10-01) — 1장 거리 장면 대사 2줄 한글
  YUNA1.DAT 블록 = [u16 A 코드 길이][u16 B 문자열 길이][u16 C 대사 번호표 바이트][u16 E] + 코드(+8‥) + 문자열(S=A+6, B)
                   + 대사 번호표(T=S+B, u16 LE × C/2 — 대사 기준 M=T+C 에서의 오프셋) + 대사(SJIS, 00 끝, 앞에 화자 머리 한 글자 있을 수 있음)
  ⇒ 새 대사는 블록 빈 곳(대사 끝 뒤)에 덧붙이고 번호표 값만 바꾼다(블록 32 KB 안).
  KANJI.FON = 16×16 1bpp(32 B) × 7,806칸, 칸 = (구−1)×94 + (점−1) (JIS 순). 한글 음절은 게임에서 안 쓰는 JIS 2수준 한자(E8xx‥) 칸에.
  python tools/poc.py → work/out/…(Track 1).bin
"""
import os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, r'C:\claude\project\anearth-kr-patch\tools')
import bdf, iso, gfx, gfx_title

ROM = next(p for p in (r'C:\claude\roms\ss\완료\Ginga Ojousama Densetsu Yuna Remix (Japan)\Ginga Ojousama Densetsu Yuna Remix (Japan) (Track 1).bin',   # 완료 폴더로 옮김(2026-10)
                      r'C:\claude\roms\ss\Ginga Ojousama Densetsu Yuna Remix (Japan)\Ginga Ojousama Densetsu Yuna Remix (Japan) (Track 1).bin') if os.path.exists(p))
OUT = os.path.join(ROOT, 'work', 'out', os.path.basename(ROM))
FONT = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11.bdf'
BLK = 0x8000
POC = [(0x8000, 1, '하룻밤이 지난 거리입니다'), (0x8000, 2, '어제 큰 소동 때문에\n주변은 엉망진창입니다'),
       (0x8000, 3, '어떡하지‥‥\n이웃들한테 뭐라고 사과해야 하지')]     # 초상화 대사(머리 «B») — 한 줄 19칸


def jis_index(code):
    a, b = code
    a -= 0x81 if a < 0xE0 else 0xC1
    b -= 0x40 if b < 0x80 else 0x41
    return (a * 2 + (1 if b >= 94 else 0)) * 94 + b % 94


def free_codes(dat):
    used = set(m.group(0) for m in re.finditer(rb'[\x81-\x9f\xe0-\xea][\x40-\x7e\x80-\xfc]', dat))
    out = []
    for hi in range(0xE8, 0xEB):
        for lo in list(range(0x40, 0x7F)) + list(range(0x80, 0xFD)):
            c = bytes([hi, lo])
            try:
                c.decode('cp932')
            except UnicodeDecodeError:
                continue
            if c not in used:
                out.append(c)
    return out


def glyph(F, ch):
    """갈무리11 → 16×16 1bpp. ★게임은 칸의 x 4‥15(12px)만 12px 간격으로 찍는다(한자도 그 폭을 꽉 채움) —
       갈무리14(13px)는 넘쳐 붙어 보였음(2026-10-01 실기) → 11px 몸을 x 4‥14(오른쪽 1px 여백), 세로 y 2‥12"""
    pts, _ = F.draw(ch, 0, 0)
    rows = [0] * 16
    for x, y in pts:
        X, Y = x + 4, y - 1
        if 0 <= X < 16 and 0 <= Y < 16:
            rows[Y] |= 0x8000 >> X
    return b''.join(r.to_bytes(2, 'big') for r in rows)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    dat = bytearray(open(os.path.join(ROOT, 'work', 'disc', 'YUNA1.DAT'), 'rb').read())
    fon = bytearray(open(os.path.join(ROOT, 'work', 'disc', 'KANJI.FON'), 'rb').read())
    F = bdf.Font(FONT)
    codes = free_codes(dat); amap = {}
    for b0, k, text in POC:
        d = dat[b0:b0 + BLK]
        A, B, C, E = struct.unpack_from('<HHHH', d, 0)
        T = A + 6 + B; M = T + C
        offs = list(struct.unpack_from('<%dH' % (C // 2), d, T))
        old = d[M + offs[k]:d.index(0, M + offs[k])]
        head = old[:1] if old[:1].isalnum() and old[:1].isascii() else b''
        enc = bytearray(head)
        for ch in text:
            if ch == '\n':
                enc.append(0x0A); continue
            if ch == ' ':
                enc += '　'.encode('cp932'); continue
            if not '가' <= ch <= '힣':
                enc += ch.encode('cp932'); continue          # 부호(‥ 등)는 원래 글꼴 그대로
            if ch not in amap:
                c = codes[len(amap)]; amap[ch] = c
                i = jis_index(c); fon[i * 32:i * 32 + 32] = glyph(F, ch)
            enc += amap[ch]
        end = len(d.rstrip(b'\0')) + 1
        new_off = end - M
        assert end + len(enc) + 1 < BLK
        dat[b0 + end:b0 + end + len(enc) + 1] = enc + b'\0'
        struct.pack_into('<H', dat, b0 + T + 2 * k, new_off)
        print('블록 %X 대사 %d: «%s» → «%s» (%d B, 오프셋 %X→%X)' % (b0, k, old.decode('cp932'), text, len(enc), offs[k], new_off))
    print('한글 음절 %d → 한자 칸 %s‥' % (len(amap), list(amap.values())[0].hex()))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    G = gfx.build()[0]                                          # 옵션·달력 한글 그림(2026-10-01)
    files = {'YUNA1.DAT': bytes(dat), 'KANJI.FON': bytes(fon), 'TITPS.CSA': G['TITPS.CSA']}
    files.update(gfx_title.main())                              # 제목 로고 TBG00‥12.SS1(크기 달라짐 — 넘치면 끝으로 옮김)
    iso.patch(ROM, OUT, files)
    iso.patch_sub(OUT, {'CALDATA/CLTES3.GS8': G['CALDATA/CLTES3.GS8']})
    print('→', OUT)


if __name__ == '__main__':
    main()
