# -*- coding: utf-8 -*-
r"""(걸리버 tools/opening_enc.py 에서 가져옴 2026-09-29 — 유나 3 은 띠 2개·15fps·320×224) 자막 덮은 프레임이 든 키 프레임 구간(GOP)만 cinepak 으로 다시 굽고 FILM 을 다시 묶는다.
  입력: 원본 .cpk, fr/f####.png(원본 프레임), kr/f####.png(덮은 프레임, tools/moviesub.py)
  구간마다 ffmpeg cinepak(띠 2개, 첫 프레임만 키) → 새턴식 변환(tools/filmcpk.py) → 원래 구간 바이트 이하가 되도록 q 를 올려 맞춤.
  소리 조각·나머지 구간은 원본 그대로, 항목 순서도 그대로. → work/kr/op22.cpk
  (tools/moviesub.py 가 부름)
"""
import glob, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import filmcpk

FF = r'C:\claude\utils\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe'
STRIPS = 2                            # 유나 리믹스도 띠 2개(112줄씩) — 아래 확인
TMP = os.path.join(ROOT, 'work', 'movie', 'sub', '_gop')


def encode(frames, q):  # noqa
    if os.path.isdir(TMP):
        for f in glob.glob(os.path.join(TMP, '*')):
            os.remove(f)
    os.makedirs(TMP, exist_ok=True)
    for i, p in enumerate(frames):
        shutil.copyfile(p, os.path.join(TMP, 'g%04d.png' % (i + 1)))
    avi = os.path.join(TMP, 'o.avi')
    subprocess.run([FF, '-v', 'error', '-y', '-framerate', '15', '-i', os.path.join(TMP, 'g%04d.png'),
                    '-c:v', 'cinepak', '-min_strips', str(STRIPS), '-max_strips', str(STRIPS), '-max_extra_cb_iterations', '4',
                    '-g', '9999'] + (['-global_quality', str(q)] if q else []) + [avi], check=True)
    pk = filmcpk.avi_packets(open(avi, 'rb').read())
    assert len(pk) == len(frames), (len(pk), len(frames))
    return [filmcpk.to_saturn(p, i == 0) for i, p in enumerate(pk)]


def reencode(src, fr, kr, out, room, log=print):
    """src(.cpk) 의 영상 중 kr/ 에 그린 프레임이 든 키 구간만 다시 굽고 out 에 쓴다 → 새 길이"""
    film = filmcpk.read(open(src, 'rb').read())
    vid = [i for i, e in enumerate(film['stab']) if e[2] != 0xFFFFFFFF]      # 항목 번호(영상만, 프레임 순서)
    key = [k for k, i in enumerate(vid) if not film['stab'][i][2] & 0x80000000]
    changed = {int(os.path.basename(p)[1:5]) - 1 for p in glob.glob(os.path.join(kr, 'f*.png'))}   # 0부터
    gops = list(zip(key, key[1:] + [len(vid)]))
    chunks = list(film['chunks'])
    infos = [e[2] for e in film['stab']]
    n_re = 0
    carry = 0                                  # 앞 구간에서 남긴 바이트(짧은 키 구간은 원래 크기로 못 맞출 때가 있다 → 넘겨받아 씀)
    for a, b in gops:
        if not any(a <= f < b for f in changed):
            continue
        frames = []
        for f in range(a, b):
            k = os.path.join(kr, 'f%04d.png' % (f + 1))
            frames.append(k if os.path.exists(k) else os.path.join(fr, 'f%04d.png' % (f + 1)))
        budget = sum(len(film['chunks'][vid[f]]) for f in range(a, b))
        for q in (0, 1000, 2000, 4000, 7000, 12000, 20000, 35000, 60000, 100000, 200000):   # ★-q:v 는 cinepak 에 거의 안 먹음 → global_quality(λ) 사다리(2026-10-01 유나 리믹스)
            new = encode(frames, q)
            if sum(map(len, new)) <= budget + carry:
                break
        else:                                  # 걸리버: 못 맞추면 가장 작은 판으로 빚지고 뒤 구간에서 갚는다(합계는 끝에서 자리로 검사)
            log('  ⚠구간 %d‥%d 빚 %d B' % (a + 1, b, sum(map(len, new)) - budget - carry))
        carry += budget - sum(map(len, new))
        for f, c in zip(range(a, b), new):
            chunks[vid[f]] = c
            t = film['stab'][vid[f]][2] & 0x7FFFFFFF
            infos[vid[f]] = t if f == a else t | 0x80000000
        n_re += 1
        log('구간 %4d‥%4d  gq %6d  %6d / %6d B' % (a + 1, b, q, sum(map(len, new)), budget))
    assert all(len(c) % 4 == 0 for c in chunks), '4 바이트 정렬 아님'
    data = filmcpk.write(film, chunks, infos)
    assert len(data) <= room, ('자리 초과', len(data), room)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'wb').write(data)
    log('다시 구운 구간 %d/%d · %s %d B (원본 %d, 자리 %d)' % (n_re, len(gops), out, len(data), os.path.getsize(src), room))
    return len(data)

