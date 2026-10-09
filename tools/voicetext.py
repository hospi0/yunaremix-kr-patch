# -*- coding: utf-8 -*-
r"""글 없이 음성만 나오는 대본 자리 찾기·짝짓기 (2026-10-09, docs/01 «자막 없는 음성»)
  ① 전수: 0x103F(음성 재생, 효과음 S/s 제외) 바로 앞뒤에 0x1017(글)이 없는 것 — 전부 [103F][0041] 꼴
  ② 음성 파일 뽑기 → work/voice/<이름>.wav (tools/acm2wav.py) — 받아쓰기는 utils/whisper-venv(따로)
  ③ 짝짓기: 같은 블록의 «대본이 부르지 않는 대사»(번호표엔 있는데 어떤 명령 인수에도 안 나오는 번호) 중 받아쓰기와 가장 닮은 것
  python tools/voicetext.py scan   → work/voice/spots.tsv + wav
  python tools/voicetext.py table  → tools/voice_table.py(빌더 표) + work/voice/review.tsv(검토)
"""
import os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
DAT = os.path.join(ROOT, 'work', 'disc', 'YUNA1.DAT')
OUTD = os.path.join(ROOT, 'work', 'voice')
BLK = 0x8000


def parse(d):
    A, B, C = struct.unpack_from('<3H', d, 0); S = A + 6; T = S + B; M = T + C
    strs = {}; p = 0
    for x in bytes(d[S:S + B]).split(b'\0'):
        strs[p] = x; p += len(x) + 1
    ins = []; p = 6
    while p < A + 2:
        op, fl = struct.unpack_from('<HH', d, p); n = op >> 12
        ins.append((p, op, fl, struct.unpack_from('<%dH' % n, d, p + 4))); p += 4 + 2 * n
    texts = []
    for k in range(C // 2):
        o = struct.unpack_from('<H', d, T + 2 * k)[0]
        texts.append(bytes(d[M + o:d.index(0, M + o)]) if M + o < BLK else b'')
    return dict(A=A, S=S, strs=strs, ins=ins, texts=texts)


def spots(D):
    out = []
    for b0 in range(0, len(D), BLK):
        try:
            P = parse(D[b0:b0 + BLK])
        except Exception:
            continue
        ins, strs = P['ins'], P['strs']
        for k, (p, op, fl, a) in enumerate(ins):
            if op == 0x103F and not fl & 0x8000 and a[0] in strs and strs[a[0]][:1] not in b'Ss':
                prv = ins[k - 1][1] if k else None; nxt = ins[k + 1][1] if k + 1 < len(ins) else None
                if 0x1017 in (prv, nxt):
                    continue
                assert nxt == 0x0041, (hex(b0), hex(p))
                out.append((b0, p, strs[a[0]].decode('cp932'), prv))
    return out


def referenced(P):
    """대본 명령 인수(즉값)에 나오는 모든 수 — 대사 번호 후보에서 뺄 것(보수적으로 전부)"""
    return {v for p, op, fl, a in P['ins'] for k, v in enumerate(a) if not fl >> (15 - k) & 1}


def norm(s):
    s = re.sub(r'[\s　、。，．・…‥！？!?「」『』（）()～〜ー\-★♥☆:：,.]', '', s)
    return ''.join(chr(ord(c) - 0x60) if 'ァ' <= c <= 'ヶ' else c for c in s)


def match(D, asr):
    """→ [(블록, 위치, 음성, 받아쓰기, 대사 번호, 닮음, 대사 원문)] — 블록마다 안 부르는 대사 중 가장 닮은 것"""
    import difflib
    out = []
    for b0, p, nm, prv in spots(D):
        P = parse(D[b0:b0 + BLK]); ref = referenced(P)
        cands = [k for k in range(len(P["texts"])) if P["texts"][k]]          # 다른 갈래에서 부르는 대사도 후보(같은 글 재사용)
        t = asr.get(nm.upper()[:-4], '')
        best = (0, -1)
        for k in cands:
            x = P['texts'][k].decode('cp932', 'replace'); x = x[1:] if x[:1].isascii() else x
            r = difflib.SequenceMatcher(None, norm(t), norm(x)).ratio()
            best = max(best, (r, k))
        r, k = best; k = None if k < 0 else k
        out.append((b0, p, nm, t, k, r, P['texts'][k].decode('cp932', 'replace') if k is not None else ''))
    return out


def all_texts(D):
    out = {}
    for b0 in range(0, len(D), BLK):
        try:
            P = parse(D[b0:b0 + BLK])
        except Exception:
            continue
        for k, x in enumerate(P['texts']):
            if x:
                out[(b0, k)] = x
    return out


def body(x):
    s = x.decode('cp932', 'replace')
    return s[1:] if s[:1].isascii() else s


def decide(D, asr, th=0.75):
    """→ [(블록, 위치, 음성, 받아쓰기, 판정, (블록, 번호) | None, 닮음)] 판정 = 같은블록 | 다른블록 | 없음"""
    import difflib
    T = all_texts(D); res = []
    for b0, p, nm, prv in spots(D):
        t = norm(asr.get(nm.upper()[:-4], ''))
        sc = sorted(((difflib.SequenceMatcher(None, t, norm(body(x))).ratio(), key) for key, x in T.items()), reverse=True)
        same = [s for s in sc if s[1][0] == b0]
        if same and same[0][0] >= th:
            res.append((b0, p, nm, t, '같은블록', same[0][1], same[0][0]))
        elif sc and sc[0][0] >= th:
            res.append((b0, p, nm, t, '다른블록', sc[0][1], sc[0][0]))
        else:
            res.append((b0, p, nm, t, '없음', None, sc[0][0] if sc else 0))
    return res


def calls(P):
    """블록 안 대사 호출 → [(위치, op, 루틴, 얼굴|None, 글 번호, 일련번호)] (5002: 루틴·얼굴·글·일련·음성 / 4002: 루틴·글·일련·음성)"""
    out = []
    for p, op, fl, a in P['ins']:
        if fl:
            continue
        if op == 0x5002:
            out.append((p, op, a[0], a[1], a[2], a[3]))
        elif op == 0x4002:
            out.append((p, op, a[0], None, a[1], a[2]))
    return out


def pick_call(P, k, p):
    """글 번호 k 를 띄울 호출 꼴 → (op, 루틴, 얼굴, 일련번호, 근거)"""
    C = [c for c in calls(P) if c[4] < len(P['texts']) and P['texts'][c[4]]]
    same = [c for c in C if c[4] == k]
    if same:
        c = min(same, key=lambda c: abs(c[0] - p)); return c[1], c[2], c[3], c[5], '같은 글 호출'
    head = P['texts'][k][:1]
    hs = [c for c in C if P['texts'][c[4]][:1] == head]
    if not hs:
        return None
    c = min(hs, key=lambda c: (abs(c[4] - k), abs(c[0] - p)))           # 번호가 가장 가까운 같은 화자 머리
    return c[1], c[2], c[3], c[5], '이웃 %X' % c[4]


# 손 판정(받아쓰기 대조 — 2026-10-09)
SKIP = {'B_85', 'B_86', 'B_87', 'B_88', 'B_89', 'B_90', 'V_10'}        # 40000 그림 248a_3 장면: 글 없음 → 새 글(2단계)
MULTI = {'B_202': [0x79, 0x7A]}                                 # 한 음성 = 대사 여럿(DAT 글 «密林の惑星» ↔ 음성 «ブラックホール» — 사용자 확인)
FIX = {'A_353': 0x70, 'A_360': 0x79}
KEEP30000 = True                                                # 1장 9줄은 실기 «완벽» 판 그대로(얼굴 0·일련 D8‥)


def load_new():
    """work/trans/voice_new_fix.tsv → {음성(대문자, 확장자 없음): [(원문, 번역)…]} — 글이 아예 없던 음성의 새 자막(해설 창)"""
    out = {}
    for ln in open(os.path.join(ROOT, 'work', 'trans', 'voice_new_fix.tsv'), encoding='utf-8').read().split('\n'):
        if ln and not ln.startswith('#'):
            c = ln.split('\t'); out.setdefault(c[0], []).append((c[1], c[2]))
    return out


def table(D, asr):
    """→ {블록: [run]} run = dict(at, back, spots=[(음성, [줄…])]) 줄 = (op, 루틴, 얼굴, 글, 일련) 글 = 번호 | ('copy', 블록, 번호)"""
    res = {}; NEW = load_new()
    R = decide(D, asr, 0.6)
    for b0, p, nm, t, j, key, sc in R:
        nmu = nm.upper()[:-4]; P = parse(D[b0:b0 + BLK])
        lines = None
        if nmu in NEW:
            lines = 'new'
        elif nmu in SKIP or (j == '없음' and nmu not in MULTI):
            lines = None
        elif nmu in MULTI:
            ks = MULTI[nmu]; c = pick_call(P, ks[0], p)
            lines = [(c[0], c[1], c[2], ks[0], c[3])] + [(lambda c2: (c2[0], c2[1], c2[2], k, 0))(pick_call(P, k, p)) for k in ks[1:]]
        elif j == '같은블록':
            k = FIX.get(nmu, key[1]); c = pick_call(P, k, p)
            lines = [(c[0], c[1], c[2], k, c[3] or 1)]
        elif j == '다른블록':
            head = all_texts(D)[key][:1]
            hs = [cc for cc in calls(P) if cc[4] < len(P['texts']) and P['texts'][cc[4]][:1] == head and cc[5]]
            cc = min(hs, key=lambda cc: abs(cc[0] - p))
            lines = [(cc[1], cc[2], cc[3], ('copy', key[0], key[1]), cc[5])]
        runs = res.setdefault(b0, [])
        if runs and runs[-1]['back'] == p:
            runs[-1]['back'] = p + 10; runs[-1]['spots'].append((nm, lines))
        else:
            runs.append(dict(at=p, back=p + 10, spots=[(nm, lines)]))
    # 글이 하나도 없는 run 은 버림
    return {b: [r for r in rs if any(l for _, l in r['spots'])] for b, rs in res.items() if any(any(l for _, l in r['spots']) for r in rs)}


def sub_name(P, sub):
    """대사 루틴(코드 기준 주소) 안 첫 0x1051 인수(캐릭터 그림 이름 «yuna01_»·«kaede»…)"""
    st = sub + 6; seen = False
    for p, op, fl, a in P['ins']:
        if p < st:
            continue
        if op == 0x1051 and a[0] in P['strs']:
            return P['strs'][a[0]].decode('cp932', 'replace')
        if op == 0x0003 and seen:
            return '?'
        seen = True
    return '?'


def write_table(D, asr, path):
    """빌더가 읽는 표(파이썬) + 검토용 TSV(work/voice/review.tsv)"""
    Tb = table(D, asr); T = all_texts(D)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('# -*- coding: utf-8 -*-\n# 자동 생성: python tools/voicetext.py table (받아쓰기 work/voice/asr.tsv) — 손대지 말고 voicetext.py 의 SKIP·MULTI·FIX 를 고칠 것\n')
        f.write('VOICE_TEXT = {\n')
        for b0, rs in sorted(Tb.items()):
            f.write('    0x%X: [\n' % b0)
            for r in rs:
                f.write('        dict(at=0x%X, back=0x%X, spots=[\n' % (r['at'], r['back']))
                for nm, lines in r['spots']:
                    f.write('            (%r, %r),\n' % (nm, lines))
                f.write('        ]),\n')
            f.write('    ],\n')
        f.write('}\n')
    with open(os.path.join(OUTD, 'review.tsv'), 'w', encoding='utf-8') as f:
        f.write('블록\t음성\t받아쓰기\t화자 그림\t글\n')
        for b0, rs in sorted(Tb.items()):
            P = parse(D[b0:b0 + BLK])
            for r in rs:
                for nm, lines in r['spots']:
                    if lines == 'new':
                        for k, (jp, kr) in enumerate(load_new()[nm.upper()[:-4]]):
                            f.write('%X\t%s\t%s\t%s\t%s\n' % (b0, nm if not k else '', asr.get(nm.upper()[:-4], '')[:40] if not k else '', '(해설 창)', kr))
                        continue
                    for k, (op, sub, face, tx, seq) in enumerate(lines or []):
                        src = T[(tx[1], tx[2])] if isinstance(tx, tuple) else P['texts'][tx]
                        f.write('%X\t%s\t%s\t%s\t%s\n' % (b0, nm if not k else '', asr.get(nm.upper()[:-4], '') if not k else '',
                                                          sub_name(P, sub), body(src).replace('\n', ' ')))
    return Tb


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    D = open(DAT, 'rb').read()
    if sys.argv[1] == 'table':
        asr = dict(l.split('\t', 1) for l in open(os.path.join(OUTD, 'asr.tsv'), encoding='utf-8').read().split('\n') if l)
        Tb = write_table(D, asr, os.path.join(HERE, 'voice_table.py'))
        print('블록 %d · 글 붙는 음성 %d → tools/voice_table.py · work/voice/review.tsv' % (len(Tb), sum(1 for rs in Tb.values() for r in rs for s in r['spots'] if s[1])))
    if sys.argv[1] == 'scan':
        import iso, poc, acm2wav, wave
        os.makedirs(OUTD, exist_ok=True)
        fh = open(poc.ROM, 'rb'); tree = iso.tree(fh)
        byname = {}
        for k, v in tree.items():
            byname.setdefault(os.path.basename(k).upper(), []).append((k, v))
        S = spots(D)
        with open(os.path.join(OUTD, 'spots.tsv'), 'w', encoding='utf-8') as f:
            f.write('블록\t위치\t음성\t파일\n')
            for b0, p, nm, prv in S:
                c = byname.get(nm.upper(), [])
                path = c[0][0] if c else ''
                if len(c) > 1:
                    path = ' '.join(x[0] for x in c)
                f.write('%X\t%04X\t%s\t%s\n' % (b0, p, nm, path))
                if c:
                    lba, size = c[0][1][:2]
                    w = os.path.join(OUTD, nm.upper().replace('.ACM', '.wav'))
                    if not os.path.exists(w):
                        rate, s = acm2wav.decode(iso.read_user(fh, lba, (size + 2047) // 2048)[:size])
                        o = wave.open(w, 'wb'); o.setnchannels(1); o.setsampwidth(2); o.setframerate(rate)
                        o.writeframes(struct.pack('<%dh' % len(s), *s)); o.close()
        print(len(S), '곳 → work/voice/spots.tsv')
