# -*- coding: utf-8 -*-
r"""유나 리믹스 번역 규칙 — 정규화(norm)·검사(check). trmerge(병합)·빌더가 «쓰는 순간» 같이 쓴다 (2026-10-01)
  본문은 전부 전각 12px 칸(1바이트 글자는 0x0A 줄바꿈뿐) → 줄 폭 = 글자 수. 초상화 대사 19칸 · 해설 24칸(«줄폭» 열).
  상자 줄 수: 원문 최대 4줄(초상화 22·해설 3개가 4줄) → 번역 ≤ 4줄. 줄이 폭을 넘으면 그 줄만 낱말 경계에서 고르게 나눔(wrap — 4줄 넘으면 문장 전체를 고르게).
  용어(2026-10-01 받은 번역 통일 — 유나 3 표기와 맞춤): 엘나·카구라자카·에리나·루미나에프·사유카·알레프치나·테시가와라·레이미·
    お嬢様 = 아가씨(«영애» 안 씀) · 暗黒お嬢様１３人衆 = «암흑 아가씨 13인방»(사용자 2026-10-01)
"""
import re

NL = chr(92) + 'n'
BANNER = '규칙: 줄폭(초상화 19·해설 24, 넘치면 낱말 단위로 다시 접음) · 줄 수 ≤ 4 · 『』「」 원문과 같은 수 · 가나·한자 금지 · SJIS 글자만 · 이름·용어 통일 · 부호 뒤 공백 삭제'
TERMS = [  # (틀린 꼴, 바른 꼴) — 긴 것 먼저
    ('사유키하나', '사유카'), ('사유키카', '사유카'), ('가구라자카', '카구라자카'), ('엘리나', '에리나'), ('루미나예프', '루미나에프'),
    ('알레프티나', '알레프치나'), ('초쿠시가와라', '테시가와라'), ('레이메이', '레이미'), ('엘나어', '엘나'), ('에르나', '엘나'), ('가에데', '카에데'),
    ('암흑 영애', '암흑 아가씨'), ('영애 사유카', '아가씨 사유카'), ('13인조', '13인방'), ('13인중', '13인방'),
]
NAMES = ['유나', '엘나', '리아', '지나', '에리나', '마리나', '루미나에프', '류디아', '에밀리', '알레프치나', '카구라자카', '시오리',
         '사유카', '무라카미', '롯폰기', '마이', '요시카', '테시가와라', '레이미']
_ALT = {14: [10, 13, 12], 15: [1, 0], 16: [4, 3]}       # 초성 ㅊ→ㅆ·ㅉ·ㅈ · ㅋ→ㄲ·ㄱ · ㅌ→ㄸ·ㄷ (거센소리 규칙 어긴 꼴)


def _variants(name):
    out = set()
    for i, ch in enumerate(name):
        o = ord(ch) - 0xAC00; cho, rest = o // 588, o % 588
        for alt in _ALT.get(cho, []):
            out.add(name[:i] + chr(0xAC00 + alt * 588 + rest) + name[i + 1:])
    return out - {name}


BAD = {v: n for n in NAMES if len(n) >= 3 for v in _variants(n)}
FW = {'ー': '―', 'ㅣ': '이', ' ': '　', '!': '！', '?': '？', '~': '～', '〜': '～', '.': '．', ',': '，', ':': '：', ';': '；', '(': '（', ')': '）',
      '…': '‥', '-': '－', '/': '／', '&': '＆', '%': '％', '+': '＋', '=': '＝', '·': '・', '♡': '♥'}
PUNCT = '，．！？：；）］」』～‥・♥★'
JP = re.compile(r'[぀-ヺー一-鿿]')                 # ・(30FB)는 원문에도 있는 부호


def _fw(ch):
    if ch in FW:
        return FW[ch]
    if '0' <= ch <= '9' or 'A' <= ch <= 'Z' or 'a' <= ch <= 'z':
        return chr(ord(ch) + 0xFEE0)
    return ch


def _brackets(t, src):
    """원문에 『』/「」 가 있는데 번역은 " " 나 ' ' 로 쓴 경우 → 원문 괄호로 (토큰 유지)"""
    for o, c in (('『', '』'), ('「', '」')):
        n = src.count(o)
        if n and t.count(o) < n:
            for q in ('"', "'", '“', '”', '‘', '’'):
                if t.count(q) >= 2:
                    parts = t.split(q)
                    t = ''.join(p + ((o if k % 2 == 0 else c) if k < len(parts) - 1 else '') for k, p in enumerate(parts))
                    break
            t = t.replace('“', o).replace('”', c)
    return t


def _words(line):
    """줄 → [(낱말, 앞 이음)] — 전각 공백 자리(이음 '　')와 문장 끝 부호(．！？‥) 바로 뒤(이음 '')에서 끊을 수 있다"""
    out = []
    for k, w in enumerate(x for x in line.split('　') if x):
        parts = re.split('(?<=[．！？])(?=[^．！？‥～』」）])', w)
        for j, p in enumerate(parts):
            out.append((p, '　' if j == 0 else ''))
    return out


def _join(ws):
    return ''.join((g if i else '') + w for i, (w, g) in enumerate(ws))


def _balance(words, k, W):
    """낱말 목록을 k 줄로 — 가장 긴 줄이 가장 짧게(고르게), 줄마다 ≤ W. 안 되면 None"""
    n = len(words)
    if k > n:
        return None
    best = None

    def rec(i, kk, acc):
        nonlocal best
        if kk == 1:
            line = _join(words[i:])
            if width(line) <= W:
                cand = acc + [line]; m = max(map(width, cand))
                if best is None or m < best[0]:
                    best = (m, cand)
            return
        for j in range(i + 1, n - kk + 2):
            line = _join(words[i:j])
            if width(line) > W:
                break
            rec(j, kk - 1, acc + [line])
    rec(0, k, [])
    return best[1] if best else None


def wrap(t, W, maxl):
    """넘치는 줄만 그 줄 안에서 낱말 경계로 고르게 2‥3줄로 나눔(번역자가 바꾼 줄은 그대로). 전체가 maxl 줄을 넘으면
       문장 전체를 maxl 줄 이하로 고르게 다시 접음. 글자 단위로는 안 자름 — 못 하면 그대로 둬서 검사가 막게."""
    lines = t.split(NL)
    if all(width(l) <= W for l in lines):
        return t
    out = []
    for l in lines:
        if width(l) <= W:
            out.append(l); continue
        ws = _words(l)
        for k in (2, 3):
            r = _balance(ws, k, W)
            if r:
                out += r; break
        else:
            out.append(l)
    if len(out) <= maxl and all(width(l) <= W for l in out):
        return NL.join(out)
    ws = [w for l in lines for w in _words(l)]
    for k in range(2, maxl + 1):
        r = _balance(ws, k, W)
        if r:
            return NL.join(r)
    return t


def norm(t, src='', m=None):
    t = t.strip().replace('\r', '')
    for a, b in TERMS:
        t = t.replace(a, b)
    for a, b in BAD.items():
        t = t.replace(a, b)
    t = _brackets(t, src)
    lines = []
    for ln in t.split(NL):
        s = ''.join(_fw(ch) for ch in ln.strip())
        s = re.sub('([%s])　(?!　)' % re.escape(PUNCT), r'\1', s)       # 부호 뒤 공백 1칸 삭제(2칸 이상은 둠)
        lines.append(s.strip('　'))
    t = NL.join(lines)
    if m is not None and m[0][0] == 'M':
        t = wrap(t, int(m[4]), 4)
    return t


def width(line):
    return len(line)


def check(m, t):
    """m = 추출본 행(ID·위치·구분·얼굴·줄폭·공유·원문·번역), t = 정규화한 번역 → (오류, 경고)"""
    err = []; warn = []
    src = m[6]
    if not t:
        return ['번역 빔'], []
    j = JP.findall(t)
    if j:
        err.append('가나·한자 남음 «%s»' % ''.join(j[:6]))
    for ch in set(t.replace(NL, '')):
        if '가' <= ch <= '힣':
            continue
        try:
            ch.encode('cp932')
        except UnicodeEncodeError:
            err.append('SJIS 에 없는 글자 «%s»' % ch)
    for o in '『』「」':
        if t.count(o) < src.count(o):
            err.append('«%s» %d개(원문 %d) — 원문 괄호 빠짐' % (o, t.count(o), src.count(o)))
        elif t.count(o) > src.count(o):
            warn.append('«%s» %d개(원문 %d) — 번역에서 더함' % (o, t.count(o), src.count(o)))
    if t.count('『') != t.count('』') or t.count('「') != t.count('」'):
        err.append('괄호 짝 안 맞음')
    for v, n in BAD.items():
        if v in t:
            err.append('이름 «%s» → «%s»' % (v, n))
    lines = t.split(NL); sl = src.count(NL) + 1
    if m[0][0] == 'M':
        if len(lines) > 4:
            err.append('줄 %d개 > 4(상자)' % len(lines))
        elif len(lines) != sl:
            warn.append('줄 수 %d(원문 %d)' % (len(lines), sl))
        W = int(m[4])
        for k, ln in enumerate(lines):
            if width(ln) > W:
                err.append('%d번째 줄 %d칸 > %d «%s»' % (k + 1, width(ln), W, ln))
    else:
        if NL in t:
            err.append('메뉴에 줄바꿈')
        if width(t) > len(src):
            warn.append('메뉴 %d칸 > 원문 %d칸' % (width(t), len(src)))
    return err, warn
