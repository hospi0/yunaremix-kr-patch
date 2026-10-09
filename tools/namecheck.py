# -*- coding: utf-8 -*-
r"""인명·지명·명사 표기 흔들림 찾기 (2026-10-09 사용자 «가에데 카에데 통일 안 됨»)
  번역(my files/tsv/yunaremix_*.tsv + work/trans/voice_new_fix.tsv)의 낱말(조사 떼고)을 모아,
  ① 초성 거센소리·된소리·예사소리만 다른 쌍(가에데/카에데) ② 받침·모음 한 군데만 다른 쌍 중 원문에 가타카나가 든 줄의 낱말
  → work/trans/name_variants.tsv (쌍·횟수·예문 ID)
  python tools/namecheck.py"""
import collections, glob, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
JOSA = sorted(['이','가','을','를','은','는','의','와','과','도','만','에','에게','한테','께','로','으로','에서','부터','까지','이랑','랑','하고',
               '야','아','여','이여','님','씨','짱','이야','이에요','예요','이다','다','처럼','보다','라고','이라고','라는','이라는','네','들'], key=len, reverse=True)
G = {0: 0, 1: 0, 15: 0, 3: 3, 4: 3, 16: 3, 7: 7, 8: 7, 17: 7, 12: 12, 13: 12, 14: 12, 9: 9, 10: 9}   # ㄱㄲㅋ·ㄷㄸㅌ·ㅂㅃㅍ·ㅈㅉㅊ·ㅅㅆ


def key(w):
    out = []
    for ch in w:
        o = ord(ch) - 0xAC00
        if 0 <= o < 11172:
            c, v, j = o // 588, (o % 588) // 28, o % 28; out.append((G.get(c, c), v, j))
        else:
            out.append(ch)
    return tuple(out)


def stem(w):
    for j in JOSA:
        if len(w) > len(j) + 1 and w.endswith(j):
            return w[:-len(j)]
    return w


def rows():
    for p in sorted(glob.glob(os.path.join(ROOT, 'my files', 'tsv', 'yunaremix_*.tsv'))):
        for ln in open(p, encoding='utf-8').read().split('\n')[1:]:
            c = ln.split('\t')
            if len(c) == 8:
                yield c[0], c[6], c[7]
    for ln in open(os.path.join(ROOT, 'work', 'trans', 'voice_new_fix.tsv'), encoding='utf-8').read().split('\n'):
        if ln and not ln.startswith('#'):
            c = ln.split('\t'); yield 'V:' + c[0], c[1], c[2]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    words = collections.Counter(); ex = collections.defaultdict(list); kata = collections.Counter()
    for iid, src, t in rows():
        hk = bool(re.search('[ァ-ヺ]{2,}', src)) or bool(re.search('[一-鿿]', src))
        for w in re.findall('[가-힣]+', t.replace('\n', ' ')):
            s = stem(w)
            if len(s) < 2:
                continue
            words[s] += 1
            if len(ex[s]) < 3:
                ex[s].append(iid)
            if hk:
                kata[s] += 1
    groups = collections.defaultdict(set)
    for w in words:
        groups[key(w)].add(w)
    out = []
    for k, ws in groups.items():
        if len(ws) > 1 and any(kata[w] for w in ws):
            out.append(sorted(ws, key=lambda w: -words[w]))
    out.sort(key=lambda ws: -sum(words[w] for w in ws))
    with open(os.path.join(ROOT, 'work', 'trans', 'name_variants.tsv'), 'w', encoding='utf-8') as f:
        f.write('표기들(횟수)\t예문 ID\n')
        for ws in out:
            f.write('%s\t%s\n' % (' / '.join('%s(%d)' % (w, words[w]) for w in ws), ' | '.join('%s:%s' % (w, ','.join(ex[w])) for w in ws)))
    print('흔들림 후보 %d쌍 → work/trans/name_variants.tsv' % len(out))
    for ws in out:
        print(' / '.join('%s(%d)' % (w, words[w]) for w in ws))


if __name__ == '__main__':
    main()


# ② 원문 쪽: 가타카나 낱말 → 번역에서 옮긴 꼴 모으기(가나→한글 어림 표기와 가장 닮은 번역 낱말)
K = dict(zip('アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンガギグゲゴザジズゼゾダヂヅデドバビブベボパピプペポ',
             '아이우에오카키쿠케코사시스세소타치츠테토나니누네노하히후헤호마미무메모야유요라리루레로와오ㄴ가기구게고자지즈제조다지즈데도바비부베보파피푸페포'))
SMALL = {'ャ': '야', 'ュ': '유', 'ョ': '요', 'ァ': '아', 'ィ': '이', 'ゥ': '우', 'ェ': '에', 'ォ': '오'}


def kana2hangul(w):
    out = ''
    for ch in w:
        if ch == 'ン' and out:
            o = ord(out[-1]) - 0xAC00
            if 0 <= o < 11172 and o % 28 == 0:
                out = out[:-1] + chr(ord(out[-1]) + 4); continue
        if ch in ('ッ', 'ー', '・'):
            continue
        if ch in SMALL and out:
            o = ord(out[-1]) - 0xAC00
            if 0 <= o < 11172:
                v = (ord(SMALL[ch]) - 0xAC00) % 588 // 28
                out = out[:-1] + chr(0xAC00 + (o // 588) * 588 + v * 28); continue
        out += K.get(ch, '')
    return out


def jamo(s):
    r = []
    for ch in s:
        o = ord(ch) - 0xAC00
        r += [o // 588, 100 + (o % 588) // 28, 200 + o % 28] if 0 <= o < 11172 else []
    return r


def katakana_map(minlen=3):
    import difflib
    m = collections.defaultdict(collections.Counter); ids = collections.defaultdict(list)
    for iid, src, t in rows():
        toks = [stem(w) for w in re.findall('[가-힣]+', t.replace('\n', ' '))]
        for W in set(re.findall('[ァ-ヺー・]{%d,}' % minlen, src)):
            W = W.strip('ー・')
            exp = kana2hangul(W)
            if len(exp) < 2:
                continue
            best = max(((difflib.SequenceMatcher(None, jamo(exp), jamo(x)).ratio(), x) for x in toks), default=(0, ''))
            if best[0] >= 0.6:
                m[W][best[1]] += 1
                if len(ids[(W, best[1])]) < 3:
                    ids[(W, best[1])].append(iid)
    return m, ids
