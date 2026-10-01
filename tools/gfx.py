# -*- coding: utf-8 -*-
r"""유나 리믹스 그림 글자 한글 (2026-10-01) — 옵션(TITPS.CSA)·달력(CALDATA/CLTES3.GS8)
  색 = 각 그림의 TCO(ACE color, 머리 0x100 + u16×256) — 실기 스테이트 옵션·달력 CRAM 뱅크 0x200 과 일치 확인.
  ① 테두리 글자(outlined): 원래 글자 상자 안 «바탕이 아닌 픽셀»을 그 줄 바탕색으로 지우고, 갈무리 비트맵(안티앨리어싱 없음)을
     1px 테두리(8방향) + 몸은 «원본 그 줄의 몸 색»(세로 그러데이션)으로 다시 그린다. 상자 왼쪽·세로 가운데 맞춤, 상자 밖으로 안 나감.
       · 옵션: 밝은 판 테두리 0x11·몸 0x12‥0x1E / 어두운 판 테두리 0x61·몸 0x62‥0x6E, 바탕 0x51‥0x53(줄마다). EXIT·START 등 영어는 그대로.
       · 달력 «表紙»·«月»: 테두리 0x1F, 몸 줄마다(주황 E2‥E7 / 9B·85·86·6D·6E), 바탕 0(투명).
  ② 말풍선(bubble): 분홍 말풍선 16개는 모두 같은 50×20 틀 — 왼쪽 열 10개 다수결로 «글자 없는 틀»을 만들어 안쪽을 덮고,
     한글을 1F 한 색으로 바탕 AC 줄(9줄) 가운데에. 갈무리9 가 넘치면 갈무리7. (원래 글은 몇 개가 윗테두리 줄까지 올라와 있음)
  python tools/gfx.py → work/gfx/*.{CSA,GS8} + my files/그래픽/비교_옵션.png·비교_달력.png
"""
import collections, os, struct, sys
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, 'work', 'gsrc')
OUT = os.path.join(ROOT, 'work', 'gfx')
FD = r'C:\claude\utils\font\Galmuri-v2.40.3' + '\\'
G11B = (FD + 'Galmuri11-Bold.ttf', 12)
G11 = (FD + 'Galmuri11.ttf', 12)
G14 = (FD + 'Galmuri14.ttf', 15)
G9 = (FD + 'Galmuri9.ttf', 10)
G7 = (FD + 'Galmuri7.ttf', 8)

OPT_BG = {0x51, 0x52, 0x53}
OPTION = [  # (상자 x0,y0,x1,y1 = 원래 글자 상자, 한글, 테두리 색)
    ((12, 208, 75, 223), '스테레오', 0x11), ((100, 208, 163, 223), '모노럴', 0x11),
    ((4, 224, 83, 239), '본체 RAM', 0x11), ((100, 224, 235, 239), '카트리지 RAM', 0x11),
    ((100, 240, 235, 255), '카트리지 RAM', 0x61),
    ((140, 112, 203, 127), '스테레오', 0x61), ((132, 128, 195, 143), '모노럴', 0x61), ((132, 144, 211, 159), '본체 RAM', 0x61),
]
CAL_OUT = [((144, 304, 181, 319), '표지', 0x1F, G14), ((176, 160, 191, 175), '월', 0x1F, G11)]
CAL_BUB = [  # (말풍선 틀 x, y, 한글) — 틀 자리는 깨끗한 틀과 윗·아랫 3줄 90% 이상 일치로 찾은 16곳
    (256, 4, '생일'), (256, 28, '개학식'), (256, 52, '운동회'), (256, 76, '문화제'), (256, 100, '봄방학'),
    (256, 124, '여름방학'), (256, 148, '겨울방학'), (256, 172, '데이트'), (256, 196, '숙제'), (256, 220, '여행'),
    (304, 4, '쇼핑'), (312, 44, '월간 음성'), (312, 68, '음성'),
    (96, 268, '유나 버튼'), (96, 292, '유리 버튼'), (96, 316, '리아 버튼'),
]


def mask(text, font):
    f = ImageFont.truetype(*font)
    l, t, r, b = f.getbbox(text)
    im = Image.new('1', (r + 2, b + 2)); d = ImageDraw.Draw(im); d.fontmode = '1'
    d.text((0, 0), text, font=f, fill=1)
    px = im.load()
    pts = [(x, y) for y in range(im.height) for x in range(im.width) if px[x, y]]
    x0 = min(x for x, _ in pts); y0 = min(y for _, y in pts)
    pts = [(x - x0, y - y0) for x, y in pts]
    return pts, max(x for x, _ in pts) + 1, max(y for _, y in pts) + 1


class Sheet:
    def __init__(self, name, off):
        self.name = name; self.raw = bytearray(open(os.path.join(SRC, name), 'rb').read()); self.off = off
        self.W, self.H = struct.unpack_from('<HH', self.raw, off - 0x100 + 0x36)
        self.orig = bytes(self.raw[off:off + self.W * self.H])

    def get(self, x, y):
        return self.raw[self.off + y * self.W + x]

    def put(self, x, y, v):
        assert 0 <= x < self.W and 0 <= y < self.H
        self.raw[self.off + y * self.W + x] = v


def outlined(S, box, text, oc, bgset, font=G11):
    x0, y0, x1, y1 = box
    fill = {}
    for y in range(y0, y1 + 1):                                   # 원본 줄마다 몸 색(테두리·바탕 아닌 가장 흔한 색)
        c = collections.Counter(S.get(x, y) for x in range(x0, x1 + 1)
                                if S.get(x, y) not in bgset and S.get(x, y) != oc)
        if c:
            fill[y] = c.most_common(1)[0][0]
    for y in range(y0, y1 + 1):                                   # 지우기 — 그 줄 바탕색으로
        bgc = collections.Counter(S.get(x, y) for x in range(x0, x1 + 1) if S.get(x, y) in bgset)
        b = bgc.most_common(1)[0][0] if bgc else 0
        for x in range(x0, x1 + 1):
            if S.get(x, y) not in bgset:
                S.put(x, y, b)
    pts, w, h = mask(text, font)
    assert w + 2 <= x1 - x0 + 1 and h + 2 <= y1 - y0 + 1, (text, w, h, box)
    ox = x0 + 1; oy = y0 + 1 + (y1 - y0 - 1 - h) // 2
    core = {(ox + x, oy + y) for x, y in pts}
    rows = sorted(fill)
    for x, y in core:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                q = (x + dx, y + dy)
                if q not in core:
                    S.put(q[0], q[1], oc)
    for x, y in core:
        S.put(x, y, fill.get(y) or fill[min(rows, key=lambda r: abs(r - y))])
    return w + 2


BW, BH = 50, 20                        # 말풍선 틀(왼쪽 위 = 꼬리 아래 윗선 줄) — 16개 모두 같은 모양


def bubble_template(S):
    """왼쪽 열 말풍선 10개의 픽셀 다수결 → 줄마다 안쪽 열(6‥43)의 남은 글자(1F)는 그 줄 다른 색 다수로 = 깨끗한 말풍선"""
    T = [[collections.Counter(S.get(256 + x, 4 + 24 * k + y) for k in range(10)).most_common(1)[0][0] for x in range(BW)]
         for y in range(BH)]
    for y in range(4, 16):
        m = collections.Counter(T[y][x] for x in range(6, 44) if T[y][x] != 0x1F).most_common(1)[0][0]
        for x in range(6, 44):
            if T[y][x] == 0x1F:
                T[y][x] = m
    return T


def bubble(S, T, ox, oy, text):
    """(ox, oy) 말풍선 틀 자리. 안쪽(줄 4‥15·열 4‥45)을 깨끗한 틀로 덮고, 바탕 AC 줄 7‥15 · 열 7‥41 가운데에 1F 한 색"""
    for y in range(4, 16):
        for x in range(4, 46):
            S.put(ox + x, oy + y, T[y][x])
    ax0, ax1, ay0, ay1 = 7, 41, 7, 15
    aw, ah = ax1 - ax0 + 1, ay1 - ay0 + 1
    for font in (G9, G7):
        pts, w, h = mask(text, font)
        if w <= aw and h <= ah:
            break
    else:
        raise SystemExit('⛔말풍선 %s 넘침 %d > %d' % (text, w, aw))
    dx = ox + ax0 + (aw - w) // 2; dy = oy + ay0 + (ah - h) // 2
    for x, y in pts:
        S.put(dx + x, dy + y, 0x1F)
    return w, aw, 'G9' if font == G9 else 'G7'


def pal(tco, off=0):
    return [((v & 31) << 3, (v >> 5 & 31) << 3, (v >> 10 & 31) << 3) for v in struct.unpack_from('>256H', tco, off + 0x100)]


def compare(S, P, path, k=3, crop=None):
    W, H = S.W, S.H
    cur = bytes(S.raw[S.off:S.off + W * H])
    x0, y0, x1, y1 = crop or (0, 0, W, H)
    cw, ch = x1 - x0, y1 - y0
    out = Image.new('RGB', (cw * 2 + 4, ch), (40, 40, 40))
    for j, d in enumerate((S.orig, cur)):
        im = Image.new('RGB', (W, H)); im.putdata([P[v] if v else (0, 0, 60) for v in d])
        out.paste(im.crop((x0, y0, x1, y1)), ((cw + 4) * j, 0))
    out.resize((out.width * k, out.height * k), Image.NEAREST).save(path)


def build():
    """→ {디스크 경로: 바이트}"""
    os.makedirs(OUT, exist_ok=True)
    res = {}
    T = Sheet('TITPS.CSA', 0x440)
    for box, text, oc in OPTION:
        bg = OPT_BG
        outlined(T, box, text, oc, bg)
    res['TITPS.CSA'] = bytes(T.raw)
    C = Sheet('CALDATA_CLTES3.GS8', 0x100)
    for box, text, oc, font in CAL_OUT:
        outlined(C, box, text, oc, {0x00}, font)
    TB = bubble_template(C)
    info = [bubble(C, TB, x, y, t) + (t,) for x, y, t in CAL_BUB]
    res['CALDATA/CLTES3.GS8'] = bytes(C.raw)
    for k, v in res.items():
        open(os.path.join(OUT, k.replace('/', '_')), 'wb').write(v)
    return res, T, C, info


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    res, T, C, info = build()
    for w, iw, f, t in info:
        print('말풍선 %-8s %2d/%2d px %s' % (t, w, iw, f))
    G = os.path.join(ROOT, 'my files', '그래픽')
    compare(T, pal(T.raw, 0x40), os.path.join(G, '비교_옵션.png'), 3, (0, 104, 240, 256))
    tco = open(os.path.join(SRC, 'CALDATA_CLTES3.TCO'), 'rb').read()
    compare(C, pal(tco), os.path.join(G, '비교_달력.png'), 2, (90, 0, 360, 340))
    print('→', OUT, '· 비교 my files/그래픽/비교_옵션.png·비교_달력.png')


if __name__ == '__main__':
    main()
