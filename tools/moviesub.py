# -*- coding: utf-8 -*-
r"""유나 리믹스 동영상 자막 굽기 (2026-10-01, 유나 3 tools/moviesub.py 그대로 — 지명 캡션은 tools/moviecap.py)
  자막 표: my files/tsv/movie_subs.tsv — 영상 · 시작 · 끝 · 원문 · 번역(«\n» = 한 자막 안 줄바꿈) · 비고
  시간: 표의 [시작, 끝] 을 쓰되 읽을 시간(글자×0.15초 + 0.8초, 최소 1.2초)보다 짧으면 다음 자막 앞까지 늘림.
  글씨: 나눔고딕 Bold 14px 흰색 + 검은 1px 테두리, 320×224 화면 아래 가운데(줄 간격 17px), 부호 뒤 공백 1칸 삭제.
  굽기: 원본 프레임(ffmpeg passthrough, 15fps) 위에 자막 판 → 그 프레임이 든 키 구간만 cinepak 재굽기(tools/movenc.py, 띠 2개,
        구간 바이트 ≤ 원본 — 모자라면 앞 구간 남은 바이트를 넘겨 씀) → work/kr/<영상>.CPK(원본 크기로 0 채움, 디스크 제자리).
  미리보기: work/movie/sub/<영상>_kr.mp4
  python tools/moviesub.py [영상 …]   (없으면 표의 영상 전부)
"""
import glob, os, re, subprocess, sys
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import movenc

FFBIN = r'C:\claude\utils\ffmpeg-9.0.1-essentials_build\bin'
FONT = r'C:\claude\utils\font\nanum-gothic\NanumGothicBold.ttf'
PX, W, H, FPS = 14, 320, 224, 15
TSV = os.path.join(ROOT, 'my files', 'tsv', 'movie_subs.tsv')
SRC = os.path.join(ROOT, 'work', 'movie')
PUNCT_SP = re.compile(r'([,.!?:;)\]}\'"~、。，．！？：；）］｝」』】〉》”’…‥・·～〜♪♥]) (?! )')


def disc_path(name):
    """CH01_EF → CH01/EF.CPK · EPILOGUE → EPILOGUE.CPK"""
    return (name.replace('_', '/', 1) if name.startswith('CH') else name) + '.CPK'


def secs(t):
    m, s = t.split(':')
    return int(m) * 60 + float(s)


def rows():
    out = {}
    for ln in open(TSV, encoding='utf-8'):
        if ln.startswith('#') or not ln.strip():
            continue
        c = ln.rstrip('\n').split('\t')
        lines = [PUNCT_SP.sub(r'\1', p.strip()) for p in c[4].split('\\n')]
        out.setdefault(c[0], []).append((secs(c[1]), secs(c[2]), lines))
    return out


def events(rs, dur):
    ev = []
    for k, (s, e, lines) in enumerate(rs):
        nxt = rs[k + 1][0] if k + 1 < len(rs) else dur
        need = max(sum(len(p) for p in lines) * 0.15 + 0.8, 1.2)
        end = max(e, s + need)
        end = min(end, nxt - 0.07, dur - 0.05)
        ev.append((s, end, lines))
    return ev


def plate(lines, F):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for ln in lines:
        assert d.textlength(ln, font=F) <= W - 12, ('줄 넘침', ln)
    y = H - 12 - (len(lines) - 1) * 17
    for ln in lines:
        d.text((W / 2, y), ln, font=F, anchor='mm', fill=(255, 255, 255), stroke_width=1, stroke_fill=(0, 0, 0)); y += 17
    px = im.load()
    for yy in range(H):
        for xx in range(W):
            r, g, b, a = px[xx, yy]
            px[xx, yy] = (r, g, b, 255) if a >= 128 else (0, 0, 0, 0)     # 반투명 없이(cinepak 에서 번짐 줄임)
    return im


def frames(name):
    fr = os.path.join(SRC, 'frames', name.lower())
    if not glob.glob(os.path.join(fr, 'f*.png')):
        os.makedirs(fr, exist_ok=True)
        subprocess.run([os.path.join(FFBIN, 'ffmpeg.exe'), '-v', 'error', '-y', '-i', os.path.join(SRC, name + '.CPK'),
                        '-fps_mode', 'passthrough', os.path.join(fr, 'f%04d.png')], check=True)
    return fr


def burn(name, ev, log):
    fr = frames(name)
    nf = len(glob.glob(os.path.join(fr, 'f*.png')))
    kr = os.path.join(fr, 'kr'); os.makedirs(kr, exist_ok=True)
    for f in glob.glob(os.path.join(kr, 'f*.png')):
        os.remove(f)
    F = ImageFont.truetype(FONT, PX); done = 0
    for a, b, lines in ev:
        pl = plate(lines, F)
        for f in range(nf):
            if a <= f / FPS < b:
                im = Image.open(os.path.join(fr, 'f%04d.png' % (f + 1))).convert('RGBA')
                im.alpha_composite(pl)
                im.convert('RGB').save(os.path.join(kr, 'f%04d.png' % (f + 1))); done += 1
    src = os.path.join(SRC, name + '.CPK')
    dst = os.path.join(ROOT, 'work', 'kr', name + '.CPK')
    size = os.path.getsize(src)
    movenc.reencode(src, fr, kr, dst, size, log=log)            # 자리 넘치면 AssertionError 로 멈춤(하위 폴더는 제자리만 가능)
    d = open(dst, 'rb').read()
    open(dst, 'wb').write(d + bytes(size - len(d)))
    log('%s 프레임 %d/%d 에 자막 → %s' % (name, done, nf, dst))


def preview(name):
    subprocess.run([os.path.join(FFBIN, 'ffmpeg.exe'), '-v', 'error', '-y', '-i', os.path.join(ROOT, 'work', 'kr', name + '.CPK'),
                    '-vf', 'scale=%d:%d:flags=neighbor' % (W * 3, H * 3), '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-b:a', '192k', os.path.join(SRC, 'sub', name + '_kr.mp4')], check=True)


def duration(name):
    fr = frames(name)
    return len(glob.glob(os.path.join(fr, 'f*.png'))) / FPS


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    allr = rows()
    names = sys.argv[1:] or sorted(allr)
    log = lambda *a: print(*a, flush=True)
    os.makedirs(os.path.join(SRC, 'sub'), exist_ok=True)
    for name in names:
        ev = events(allr[name], duration(name))
        log('== %s 자막 %d개' % (name, len(ev)))
        for a, b, t in ev:
            log('   %6.2f‥%6.2f  %s' % (a, b, ' / '.join(t)))
        burn(name, ev, log)
        preview(name)


if __name__ == '__main__':
    main()
