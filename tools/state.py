# -*- coding: utf-8 -*-
r"""RetroArch(Beetle Saturn) 상태 파일 → work/mem/<이름>/ 에 VDP1_VRAM·VDP2_VRAM·CRAM·WorkRAML·WorkRAMH(전부 swap16 한 빅엔디언)·VDP2_REGS(u16 BE 256)
  ★이 게임 상태 파일은 VDP2 VRAM·CRAM 도 swap16 (FONT.DAT 로 검산). 첫 VRAM = VDP1(뒤에 프레임버퍼), 두 번째 = VDP2.
  python tools/state.py <상태파일> <이름>
"""
import os, struct, sys
sys.path.insert(0, r'C:\claude\project\df2-kr-patch\tools')
import rzip, dump_state as ds
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def dump(path, name):
    raw = open(path, 'rb').read()
    snap = rzip.unpack(path)[0] if raw[:5] == b'#RZIP' else raw
    out = os.path.join(ROOT, 'work', 'mem', name); os.makedirs(out, exist_ok=True)
    hits = ds.find_vars(snap); used = set()
    for want, tag in (('VRAM', 'VDP1_VRAM'), ('VRAM', 'VDP2_VRAM'), ('CRAM', 'CRAM'), ('WorkRAML', 'WorkRAML'), ('WorkRAMH', 'WorkRAMH')):
        for k, (i, nm, off, sz) in enumerate(hits):
            if nm == want and k not in used:
                used.add(k); open(os.path.join(out, tag + '.bin'), 'wb').write(ds.swap16(snap[off:off + sz])); break
    i = snap.find(b'\x07RawRegs'); n = struct.unpack_from('<I', snap, i + 8)[0]
    R = snap[i + 12:i + 12 + n]
    open(os.path.join(out, 'VDP2_REGS.bin'), 'wb').write(struct.pack('>256H', *struct.unpack('<256H', R)))
    return out


if __name__ == '__main__':
    print(dump(sys.argv[1], sys.argv[2]))
