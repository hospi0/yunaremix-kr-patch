# -*- coding: utf-8 -*-
"""111.BIN SH-2 역어셈블(테라 프로젝트 sh2_disasm 재사용) — python tools/sh2dis.py 0x0602406C [개수]  (적재 0x06004000)"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
LOAD = 0x06004000
EXE = os.path.join(ROOT, 'work', 'disc', '111.BIN')
_src = open(r'C:\claude\project\terra-kr-patch\tools\sh2_disasm.py', encoding='utf-8').read().split("if __name__")[0]
_ns = {}; exec(_src, _ns)


def dis(addr, n=80, g=None):
    g = g or open(EXE, 'rb').read(); o = addr - LOAD
    return ['%08X  %04X  %s' % (a, w, t) for a, w, t in _ns['disasm_sh2'](g[o:o + n * 2], addr, n)]


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    print('\n'.join(dis(int(sys.argv[1], 16), int(sys.argv[2]) if len(sys.argv) > 2 else 80)))
