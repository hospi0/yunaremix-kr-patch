# -*- coding: utf-8 -*-
r"""유나 리믹스 받은 번역 병합·검사 (2026-10-01) — my files/yunaremix/*.tsv → my files/tsv/yunaremix_*.tsv «번역» 열
  받은 파일: 열 8개(ID·위치·구분·얼굴·줄폭·공유·원문·번역). ★009 처럼 번역 칸 안에 «실제 줄바꿈»이 있으면(따옴표 없음)
    ID(M#####/S####)로 시작하지 않는 줄을 앞 행 번역에 \n 으로 이어 붙인다.
  정규화(rules.norm): 실제 줄바꿈 → \n · 반각 부호·영숫자 → 전각(게임 본문은 1바이트 글자를 0x0A 말고 못 씀) · 문장부호 뒤 공백 1칸 삭제 ·
    이름 표기 통일(NAMES 의 거센소리 변형 → 바른 꼴, rules.BAD)
  ⛔막음(rules.check): ID·원문이 추출본과 다름 · 가나/한자 남음 · SJIS 로 못 쓰는 글자 · 줄 수 > 상자 줄 수(MAXL) ·
    줄 폭 > 줄폭 열(초상화 19 / 해설 24 — 글자는 전부 12px 한 칸) · 이름 변형
  ⚠경고: 메뉴(S) 글이 원문보다 김(메뉴 칸 폭 미측정) · 원문과 줄 수 다름
  행 단위 수정: work/trans/menu_fix.tsv(메뉴 명사형·띄어쓰기 없음, 사용자 2026-10-01)·fixes.tsv 가 받은 번역보다 우선. 메뉴(S)는 공백 전부 뺌.
  python tools/trmerge.py [--apply] → 보고 work/trans/merge_report.tsv
"""
import glob, os, re, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import rules

NL = chr(92) + 'n'
ROWSTART = re.compile(r'^(M\d{5}|S\d{4})\t')


def read_given():
    got = {}; joined = 0
    for f in sorted(glob.glob(os.path.join(ROOT, 'my files', 'yunaremix', '*.tsv'))):
        cur = None
        for ln in open(f, encoding='utf-8-sig').read().replace('\r\n', '\n').split('\n')[1:]:
            if ROWSTART.match(ln):
                c = ln.split('\t')
                if len(c) != 8:
                    raise SystemExit('⛔%s %s 열 %d개' % (os.path.basename(f), c[0], len(c)))
                got[c[0]] = c; cur = c
            elif ln.strip() and cur is not None:
                cur[7] += NL + ln; joined += 1
    return got, joined


def read_mine():
    rows = {}; where = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'my files', 'tsv', 'yunaremix_*.tsv'))):
        for ln in open(f, encoding='utf-8').read().split('\n')[1:]:
            c = ln.split('\t')
            if len(c) == 8:
                rows[c[0]] = c; where[c[0]] = f
    return rows, where


FIX = {}
for _fn in ('menu_fix.tsv', 'fixes.tsv'):                   # 사용자 확인을 거친 행 단위 수정 — 받은 번역보다 우선
    _p = os.path.join(ROOT, 'work', 'trans', _fn)
    if os.path.exists(_p):
        for _l in open(_p, encoding='utf-8').read().split(chr(10))[1:]:
            _c = _l.split(chr(9))
            if len(_c) >= 2 and _c[1].strip():
                FIX[_c[0]] = _c[1]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    apply_ = '--apply' in sys.argv
    got, joined = read_given()
    mine, where = read_mine()
    err = []; warn = []; out = {}
    for iid, m in mine.items():
        g = got.get(iid)
        if g is None:
            err.append((iid, '받은 번역에 없음', '')); continue
        if g[6] != m[6]:
            err.append((iid, '원문이 추출본과 다름', g[6])); continue
        t = FIX.get(iid, g[7])
        t = rules.norm(t, m[6], m)
        if iid[0] == 'S':
            t = t.replace('　', '')                    # 메뉴·선택지는 띄어쓰기 없이(사용자 2026-10-01)
        e, w = rules.check(m, t)
        err += [(iid, x, t) for x in e]; warn += [(iid, x, t) for x in w]
        out[iid] = t
    for iid in got:
        if iid not in mine:
            err.append((iid, '추출본에 없는 ID', ''))
    rep = os.path.join(ROOT, 'work', 'trans'); os.makedirs(rep, exist_ok=True)
    with open(os.path.join(rep, 'merge_report.tsv'), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('ID\t종류\t내용\t번역(정규화)\n')
        for k, (iid, x, t) in [('⛔', e) for e in err] + [('⚠', w) for w in warn]:
            fh.write('%s\t%s\t%s\t%s\n' % (iid, k, x, t))
    print(rules.BANNER)
    print('받은 %d행(실제 줄바꿈 이어 붙임 %d) · 오류 %d · 경고 %d → work/trans/merge_report.tsv' % (len(got), joined, len(err), len(warn)))
    for iid, x, t in err[:30]:
        print('⛔', iid, x, '«%s»' % t[:60])
    if apply_:
        if err:
            raise SystemExit('⛔오류가 있어 적용 안 함')
        bak = os.path.join(rep, 'tsv_before_merge'); os.makedirs(bak, exist_ok=True)
        n = 0
        for f in sorted(set(where.values())):
            shutil.copy2(f, bak)
            L = open(f, encoding='utf-8').read().split('\n'); o = [L[0]]
            for ln in L[1:]:
                c = ln.split('\t')
                if len(c) == 8 and c[0] in out:
                    c[7] = out[c[0]]; n += 1
                o.append('\t'.join(c))
            open(f, 'w', encoding='utf-8', newline='\n').write('\n'.join(o))
        print('적용 %d행 → my files/tsv (백업 work/trans/tsv_before_merge)' % n)


if __name__ == '__main__':
    main()
