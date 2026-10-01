# -*- coding: utf-8 -*-
r"""동영상에 박힌 일본어 지명 캡션 → 한국어 (2026-10-01, 사용자 스샷 my files/동영상 자막/*.png)
  캡션 = 흰 가는 글씨 12px 안팎 + 오른쪽 아래 회색 그림자, 화면에 고정, 영상 뒷부분(CH03 은 _0 끝 ~ _1 앞)에 나타남.
  ① 마스크: 캡션 없는 프레임(base) ↔ 캡션 프레임(ref) 차이 > 35 이고 ref 에서 무채색(최대−최소 < 50)인 화소, 둘레 1px 넓힘
     (움직이는 배경의 색 화소는 빠지고 글자·그림자만 남는다)
  ② 캡션 프레임마다 마스크 자리를 주변 화소 확산으로 메움(numpy, 바깥에서 안쪽으로)
  ③ 한국어 캡션: 나눔고딕 13px 흰색 + 오른쪽 아래 1px 회색 그림자, 원래 글줄 가운데에 맞춰 줄마다
  ④ tools/movenc.py 로 그 구간만 다시 굽기 → work/kr/<영상>.CPK (원본 크기 그대로 0 채움)
  python tools/moviecap.py [영상 …]   미리보기 work/movie/sub/<영상>_kr.mp4
"""
import glob, os, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import movenc

FFBIN = r'C:\claude\utils\ffmpeg-9.0.1-essentials_build\bin'
FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothic.ttf'
SRC = os.path.join(ROOT, 'work', 'movie')
W, H = 320, 224
# 영상: (캡션 프레임 범위(0부터, 끝 제외), base 프레임, ref 프레임, 한국어 줄들[, 캡션 위쪽 한계 y, 넓힘])
CAPS = {
    'CH03_EV05_0': (range(39, 46), 37, 45, ['플랜터 성계', '행성 마리아나'], 158, 2),
    'CH03_EV05_1': (range(0, 3), 4, 0, ['플랜터 성계', '행성 마리아나'], 158, 2),
    'CH04_EV07_1': (range(9, 16), 7, 15, ['티안 성역', '발무드 별']),
    'CH05_EV06_0': (range(38, 46), 36, 45, ['카페 항성계', '행성 루리즈스']),
    'CH06_EV09_0': (range(24, 31), 22, 30, ['은하계 동방 외완부', '암흑성운']),
    'CH07_EV10_1': (range(8, 16), 6, 15, ['칼디아 성계 인공행성', '플린트 우주역', '소행성대']),
    'CH08_EV08_0': (range(38, 46), 36, 45, ['거문고자리 부근　블랙홀', 'GNC-01089']),
}
YS = {'CH03_EV05_0': [168, 183], 'CH03_EV05_1': [168, 183]}   # 글줄 중심 직접 지정(자동 판별이 행성 가장자리에 속음)


def frames(name):
    fr = os.path.join(SRC, 'frames', name.lower())
    if not glob.glob(os.path.join(fr, 'f*.png')):
        os.makedirs(fr, exist_ok=True)
        subprocess.run([os.path.join(FFBIN, 'ffmpeg.exe'), '-v', 'error', '-y', '-i', os.path.join(SRC, name + '.CPK'),
                        '-fps_mode', 'passthrough', os.path.join(fr, 'f%04d.png')], check=True)
    return fr


def load(fr, i):
    return np.array(Image.open(os.path.join(fr, 'f%04d.png' % (i + 1))).convert('RGB')).astype(np.int32)


def dilate(m, r=1):
    o = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            o |= np.roll(np.roll(m, dy, 0), dx, 1)
    return o


def make_mask(fr, base, ref, ytop=100, grow=1):
    a, b = load(fr, base), load(fr, ref)
    diff = np.abs(b - a).sum(2) > 35
    grey = (b.max(2) - b.min(2)) < 50
    m = diff & grey
    m[:ytop] = False                                        # 캡션은 화면 아래쪽
    # 외톨이 화소(별 반짝임) 빼기: 3×3 이웃 2개 미만
    nb = sum(np.roll(np.roll(m, dy, 0), dx, 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1)) - m
    m &= nb >= 2
    return dilate(m, grow)


def fill(img, m):
    """마스크 자리를 바깥 화소 평균으로 한 겹씩 채움"""
    img = img.astype(np.float64).copy(); known = ~m
    while not known.all():
        acc = np.zeros_like(img); cnt = np.zeros(img.shape[:2])
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
            k = np.roll(np.roll(known, dy, 0), dx, 1)
            acc += np.roll(np.roll(img, dy, 0), dx, 1) * k[..., None]; cnt += k
        new = (~known) & (cnt > 0)
        img[new] = acc[new] / cnt[new][:, None]; known |= new
    return img.astype(np.uint8)


def lines_y(m):
    """마스크 행 → 글줄 중심 y 들"""
    rows = np.where(m.sum(1) > 0)[0]
    groups, g = [], [rows[0]]
    for r in rows[1:]:
        if r - g[-1] <= 2:
            g.append(r)
        else:
            groups.append(g); g = [r]
    groups.append(g)
    return [(g[0] + g[-1]) / 2 for g in groups if len(g) >= 6]


def plate(lines, m, F, ys=None):
    xs = np.where(m.sum(0) > 0)[0]
    cx = (xs.min() + xs.max()) / 2
    ys = ys or lines_y(m)
    if len(ys) != len(lines):                                # 줄 수가 다르면 원래 덩어리 가운데에 15px 간격
        ys0 = np.where(m.sum(1) > 0)[0]; mid = (ys0.min() + ys0.max()) / 2
        ys = [mid + (k - (len(lines) - 1) / 2) * 15 for k in range(len(lines))]
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for ln, y in zip(lines, ys):
        d.text((cx + 1, y + 1), ln, font=F, anchor='mm', fill=(96, 96, 96, 255))
        d.text((cx, y), ln, font=F, anchor='mm', fill=(240, 240, 240, 255))
    a = np.array(im); a[..., 3] = np.where(a[..., 3] >= 110, 255, 0)
    return Image.fromarray(a)


def run(name, log=print):
    rng, base, ref, lines, *opt = CAPS[name]
    fr = frames(name)
    m = make_mask(fr, base, ref, *opt)
    F = ImageFont.truetype(FONT, 13)
    pl = plate(lines, m, F, YS.get(name))
    kr = os.path.join(fr, 'kr'); os.makedirs(kr, exist_ok=True)
    for f in glob.glob(os.path.join(kr, 'f*.png')):
        os.remove(f)
    for i in rng:
        im = Image.fromarray(fill(load(fr, i), m)).convert('RGBA')
        im.alpha_composite(pl)
        im.convert('RGB').save(os.path.join(kr, 'f%04d.png' % (i + 1)))
    Image.fromarray((m * 255).astype(np.uint8)).save(os.path.join(SRC, 'sub', name + '_mask.png'))
    src = os.path.join(SRC, name + '.CPK'); dst = os.path.join(ROOT, 'work', 'kr', name + '.CPK')
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    size = os.path.getsize(src)
    movenc.reencode(src, fr, kr, dst, size, log=log)
    d = open(dst, 'rb').read()
    open(dst, 'wb').write(d + bytes(size - len(d)))
    log('%s 캡션 %d프레임 (마스크 %d화소) → %s' % (name, len(rng), int(m.sum()), dst))


def preview(name):
    subprocess.run([os.path.join(FFBIN, 'ffmpeg.exe'), '-v', 'error', '-y', '-i', os.path.join(ROOT, 'work', 'kr', name + '.CPK'),
                    '-vf', 'scale=%d:%d:flags=neighbor' % (W * 3, H * 3), '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-b:a', '192k', os.path.join(SRC, 'sub', name + '_kr.mp4')], check=True)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    os.makedirs(os.path.join(SRC, 'sub'), exist_ok=True)
    for name in sys.argv[1:] or sorted(CAPS):
        run(name); preview(name)


if __name__ == '__main__':
    main()
