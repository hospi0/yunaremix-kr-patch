# -*- coding: utf-8 -*-
r"""유나 리믹스 제목 로고 한글 (2026-10-01, 사용자 «타이틀 로고도 한글로»)
  TBG00‥12.SS1(제목 배경 13장, 320×240) = 달력 옅은 그림 CALDATA/CAL00‥12S.SS1 + 로고. 로고는 «빼기» 합성:
    T = clamp(C − D) — D(x, y) = 13장 (C − T) 중앙값(T>0 인 것만), 잔차 평균 0.44(5비트 단계). ⇒ 깨끗한 배경 C 가 있으니 로고만 바꿀 수 있다.
  바꾸는 것: «銀河お嬢様伝説»(x 21‥117, y 45‥61) → «은하 아가씨 전설», 큰 «ユナ» → «유나». 고리·별·GALAXY FRAULEIN·밑줄·REMIX·저작권 줄은 원본 그대로(T).
   · 지움 자리(옛 글자) = C. 옛 글자 밑에 가려졌던 고리 구간은 고리 화소로 맞춘 타원(일반 원뿔곡선 최소제곱)을 그려 메움.
   · 유나 = 둥근 끝 굵은 획(13px) 기하 도형, 색 = 옛 ユナ 화소 D 중앙값, 가장자리 1px 은 그 60%(원본처럼 옅은 테두리). 고리보다 위.
   · 은하 아가씨 전설 = 나눔고딕 ExtraBold, 몸 D = 옛 글자 «속» 화소의 줄별 중앙값(세로 그러데이션), 테두리 D = 옛 글자 «테두리» 중앙값.
  python tools/gfx_title.py → work/gfx/TBG##.SS1 + my files/그래픽/비교_제목.png
"""
import os, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import tbg, ss1

W, H = 320, 240
N = 13
EXB = r'C:\claude\utils\font\nanum-gothic\NanumGothicExtraBold.ttf'
JBOX = (21, 44, 118, 62)                 # 銀河お嬢様伝説 (밑줄 y 62‥66 은 제외)
YBOX = (104, 36, 250, 134)               # ユナ 둘레
STROKE = 13


def ch(a):
    return np.stack([(a & 31), (a >> 5 & 31), (a >> 10 & 31)], -1).astype(float)


def pack(rgb, msb):
    r, g, b = [np.clip(np.rint(rgb[..., i]), 0, 31).astype(np.int64) for i in range(3)]
    return (r | g << 5 | b << 10 | msb)


def yuna_mask():
    """유나 기하 도형 — 4배 크기로 그려 줄임(둥근 끝), → (몸 bool, 가장자리 bool)"""
    S = 4
    im = Image.new('L', (W * S, H * S)); d = ImageDraw.Draw(im)
    w = STROKE * S

    def line(x0, y0, x1, y1):
        d.line([(x0 * S, y0 * S), (x1 * S, y1 * S)], fill=255, width=w)
        for x, y in ((x0, y0), (x1, y1)):
            r = (w - S) / 2                                  # 끝 원 = 선 굵기와 같게(크면 이음매가 1px 불룩 — 점처럼 보임)
            d.ellipse([(x * S - r, y * S - r), (x * S + r, y * S + r)], fill=255)
    # 유: ㅇ + ㅠ
    cx, cy, rx, ry = 147, 60, 20, 16
    d.ellipse([((cx - rx) * S - w / 2, (cy - ry) * S - w / 2), ((cx + rx) * S + w / 2, (cy + ry) * S + w / 2)], fill=255)
    d.ellipse([((cx - rx) * S + w / 2, (cy - ry) * S + w / 2), ((cx + rx) * S - w / 2, (cy + ry) * S - w / 2)], fill=0)
    line(116, 93, 178, 93); line(134, 93, 134, 122); line(160, 93, 160, 122)
    # 나: ㄴ + ㅏ (REMIX(y 108‥) 위에서 끝냄)
    line(194, 46, 194, 98); line(194, 98, 216, 98)
    line(233, 40, 233, 100); line(233, 70, 248, 70)
    m = np.array(im.resize((W, H), Image.LANCZOS)) >= 128
    inner = m.copy()
    inner[1:, :] &= m[:-1, :]; inner[:-1, :] &= m[1:, :]; inner[:, 1:] &= m[:, :-1]; inner[:, :-1] &= m[:, 1:]
    return m, m & ~inner


def text_layer(text, box, size):
    x0, y0, x1, y1 = box
    f = ImageFont.truetype(EXB, size)
    l, t, r, b = f.getbbox(text)
    im = Image.new('L', (r - l + 4, b - t + 4)); d = ImageDraw.Draw(im)
    d.text((2 - l, 2 - t), text, font=f, fill=255)
    a = np.array(im) >= 110
    ys, xs = np.where(a)
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = a.shape
    assert w + 2 <= x1 - x0 and h + 2 <= y1 - y0 + 1, (text, w, h)
    core = np.zeros((H, W), bool)
    ox = x0 + (x1 - x0 - w) // 2; oy = y0 + (y1 - y0 + 1 - h) // 2
    core[oy:oy + h, ox:ox + w] = a
    out = np.zeros((H, W), bool)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            out |= np.roll(np.roll(core, dy, 0), dx, 1)
    return core, out & ~core


def fit_ellipse(xs, ys):
    A = np.vstack([xs * xs, xs * ys, ys * ys, xs, ys, np.ones_like(xs)]).T
    _, _, V = np.linalg.svd(A)
    return V[-1]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    Tr = np.array([tbg.load('TBG%02d.SS1' % k)[2] for k in range(N)]).reshape(N, H, W)
    Cr = np.array([tbg.load('CALDATA_CAL%02dS.SS1' % k)[2] for k in range(N)]).reshape(N, H, W)
    T, C = ch(Tr), ch(Cr)
    D = np.where(T > 0, C - T, np.nan)
    with np.errstate(all='ignore'):
        D = np.nan_to_num(np.nanmedian(D, axis=0), nan=0.0)
    diff = (Tr != Cr).any(0)
    yy, xx = np.mgrid[0:H, 0:W]

    def inbox(b):
        return (xx >= b[0]) & (xx <= b[2]) & (yy >= b[1]) & (yy <= b[3])
    # 옛 ユナ 글자 화소 = 분홍(녹색을 많이·빨강을 조금 뺀) · 고리 = 남색(빨강·녹색을 많이)
    pink0 = diff & inbox(YBOX) & (D[..., 1] >= 12) & (D[..., 0] <= 9)
    pink = np.zeros_like(pink0)                       # 큰 덩어리(글자)만 — 분홍 별은 빼기
    seen = np.zeros_like(pink0)
    for sy, sx in zip(*np.where(pink0)):
        if seen[sy, sx]:
            continue
        st = [(sy, sx)]; seen[sy, sx] = True; comp = []
        while st:
            y, x = st.pop(); comp.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                y2, x2 = y + dy, x + dx
                if 0 <= y2 < H and 0 <= x2 < W and pink0[y2, x2] and not seen[y2, x2]:
                    seen[y2, x2] = True; st.append((y2, x2))
        if len(comp) > 300:
            for y, x in comp:
                pink[y, x] = True
    ring = diff & ~pink & (D[..., 0] >= 12) & (D[..., 1] >= 12) & (D[..., 2] <= D[..., 0])
    old_j = diff & inbox(JBOX)
    # 옛 글자 둘레 1px 까지 지움(가장자리 옅은 테두리 포함)
    grow = pink.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            grow |= np.roll(np.roll(pink, dy, 0), dx, 1)
    erase = (grow & diff & ~ring) | old_j
    Dpink = np.median(D[pink], axis=0)
    # 銀河 글자: 테두리 = 가장 진한(D 합 큰) 쪽 1/3, 속 = 나머지 — 속은 줄별 중앙값
    s = D[old_j].sum(-1); thr = np.percentile(s, 66)
    Dout = np.median(D[old_j][s >= thr], axis=0)
    rows = {}
    for y in range(JBOX[1], JBOX[3] + 1):
        sel = old_j[y] & (D[y].sum(-1) < thr)
        if sel.any():
            rows[y] = np.median(D[y][sel], axis=0)
    # 새 글자
    ybody, yedge = yuna_mask()
    jcore, jout = text_layer('은하 아가씨 전설', JBOX, 13)
    # ★고리: 옛 글자 둘레 상자 안의 원본 고리 조각은 지우고, 원본 고리 화소에 맞춘 타원(잔차 0.58px)으로 «유나» 뒤를 둥글게 이어 그린다
    #   (사용자 2026-10-01: 1차 «우하단 둥근 검은 찌꺼기» = 엉뚱하게 맞춘 타원 조각 → 2차 상자 안 고리를 다 지웠더니 «원본은 둥글게 이어져 있는데 잘려 있다»)
    ringish = diff & (D[..., 0] >= 10) & (D[..., 1] >= 8) & (D[..., 2] <= D[..., 0] + 3) & (np.abs(D[..., 0] - D[..., 1]) <= 6)
    fitp = ringish & inbox((60, 10, 215, 140)) & ~inbox((15, 40, 120, 80)) & ~inbox((190, 104, 310, 135))
    ry, rx = np.where(fitp)
    E = fit_ellipse(rx.astype(float), ry.astype(float))
    q = E[0] * xx * xx + E[1] * xx * yy + E[2] * yy * yy + E[3] * xx + E[4] * yy + E[5]
    gx = 2 * E[0] * xx + E[1] * yy + E[3]; gy = E[1] * xx + 2 * E[2] * yy + E[4]
    dist = np.abs(q) / np.maximum(np.hypot(gx, gy), 1e-9)
    LBOX = (113, 38, 250, 128)
    hide = inbox(LBOX) & ~inbox((193, 106, 305, 131)) & ~inbox((15, 40, 120, 80)) & diff & ~ybody         & (D[..., 0] >= 3) & (D[..., 1] >= 3) & (D[..., 2] <= D[..., 0] + 2)
    erase |= hide
    zone = erase & ~inbox((15, 40, 120, 80))                 # 지운 자리(부제 글자 칸 제외)에만 고리를 다시
    ring_core = (dist <= 0.6) & zone
    ring_soft = (dist > 0.6) & (dist <= 1.1) & zone
    ring_fill = ring_core | ring_soft
    Dring = np.median(D[ringish & fitp & (dist <= 0.6)], axis=0)
    Dnew = np.zeros((H, W, 3))
    Dnew[ring_core] = Dring
    Dnew[ring_soft] = Dring * 0.5
    for y, v in rows.items():
        Dnew[y][jcore[y]] = v
    for y in range(H):
        if jcore[y].any() and y not in rows:
            k = min(rows, key=lambda r: abs(r - y)); Dnew[y][jcore[y]] = rows[k]
    Dnew[jout] = Dout
    Dnew[ybody] = Dpink                                      # 글자가 고리 위
    Dnew[yedge] = Dpink * 0.6
    newm = ring_fill | jcore | jout | ybody
    os.makedirs(os.path.join(ROOT, 'work', 'gfx'), exist_ok=True)
    out = {}; cmp_ = []
    for k in range(N):
        img = T[k].copy()
        img[erase] = C[k][erase]
        img[newm] = np.clip(C[k][newm] - Dnew[newm], 0, 31)
        px = pack(img, Tr[k] & 0x8000).reshape(-1).tolist()
        b = ss1.encode(W, H, px)
        orig = open(os.path.join(tbg.SRC, 'TBG%02d.SS1' % k), 'rb').read()
        out['TBG%02d.SS1' % k] = b
        open(os.path.join(ROOT, 'work', 'gfx', 'TBG%02d.SS1' % k), 'wb').write(b)
        if k in (0, 3, 8):
            cmp_.append((T[k], img))
        print('TBG%02d.SS1 %d → %d B' % (k, len(orig), len(b)))
    sheet = Image.new('RGB', (W * 2 + 4, (H + 4) * len(cmp_)), (40, 40, 40))
    for j, (a, b) in enumerate(cmp_):
        for i, x in enumerate((a, b)):
            sheet.paste(Image.fromarray((x * 8).astype('uint8')), ((W + 4) * i, (H + 4) * j))
    sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST).save(os.path.join(ROOT, 'my files', '그래픽', '비교_제목.png'))
    print('유나 D', Dpink.round(1), '고리 D', Dring.round(1), '銀河 테두리 D', Dout.round(1), '지움', int(erase.sum()), '고리 다시', int(ring_fill.sum()), '고리 지움', int(hide.sum()))
    return out


if __name__ == '__main__':
    main()
