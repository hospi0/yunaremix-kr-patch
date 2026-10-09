# -*- coding: utf-8 -*-
r"""유나 리믹스 음성 ACM → wav (2026-10-09)
  ACM = AIFF(FORM/AIFF/COMM 모노 4비트 18,900 Hz) + «APCM» 덩어리 = CD-XA ADPCM 소리 묶음(128 B: 머리 16 + 자료 112, 단위 8 × 28 표본), 2,324 B 블록마다 18묶음
  python tools/acm2wav.py 파일.ACM … → 같은 자리에 .wav"""
import struct, sys, wave
K0 = (0, 60, 115, 98); K1 = (0, 0, -52, -55)


def decode(d):
    i = d.find(b'APCM'); n = struct.unpack_from('>I', d, i + 4)[0]
    rate = 18900
    c = d.find(b'COMM')
    if c >= 0:
        e = struct.unpack_from('>H', d, c + 16)[0]; m = struct.unpack_from('>I', d, c + 18)[0]
        rate = round(m * 2.0 ** (e - 16383 - 31))
    blk = struct.unpack_from('>I', d, i + 12)[0] or 2324   # APCM 머리 8 B(오프셋·블록 크기 0x914 = XA 섹터 사용자 자료)
    a = d[i + 16:i + 8 + n]
    out = []; s1 = s2 = 0
    groups = [a[b + g:b + g + 128] for b in range(0, len(a), blk) for g in range(0, 18 * 128, 128)]   # 블록마다 묶음 18 + 남는 20 B
    for G in groups:
        if len(G) < 128:
            break
        for k in range(8):
            p = G[4 + k]; f = (p >> 4) & 3; sh = p & 0xF
            for j in range(28):
                b = G[16 + j * 4 + k // 2]
                nib = (b >> 4) if k & 1 else (b & 0xF)
                if nib >= 8: nib -= 16
                v = ((nib << 12) >> sh) + ((s1 * K0[f] + s2 * K1[f] + 32) >> 6)
                v = max(-32768, min(32767, v)); s2, s1 = s1, v; out.append(v)
    return rate, out


if __name__ == '__main__':
    for p in sys.argv[1:]:
        rate, s = decode(open(p, 'rb').read())
        w = wave.open(p.rsplit('.', 1)[0] + '.wav', 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(struct.pack('<%dh' % len(s), *s)); w.close()
        print(p, rate, '%.2f초' % (len(s) / rate), '최대', max(map(abs, s)))
