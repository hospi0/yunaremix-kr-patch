# -*- coding: utf-8 -*-
r"""위스퍼 받아쓰기 — C:\claude\utils\whisper-venv\Scripts\python.exe tools/asr.py 폴더 결과.tsv
  (av 버전 문제로 파일 경로 대신 16 kHz numpy 배열로 넘긴다 — ffmpeg 로 변환)"""
import os, subprocess, sys, numpy as np
from faster_whisper import WhisperModel
sys.stdout.reconfigure(encoding='utf-8')
FF = r'C:\claude\utils\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe'
m = WhisperModel('large-v3', device='cuda', compute_type='float16')
d, out = sys.argv[1], sys.argv[2]
with open(out, 'w', encoding='utf-8') as f:
    for n in sorted(x for x in os.listdir(d) if x.lower().endswith('.wav')):
        raw = subprocess.run([FF, '-loglevel', 'error', '-i', os.path.join(d, n), '-f', 's16le', '-ac', '1', '-ar', '16000', '-'],
                             capture_output=True, check=True).stdout
        a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
        segs, _ = m.transcribe(a, language='ja', beam_size=5, condition_on_previous_text=False)
        t = ' '.join(s.text.strip() for s in segs)
        f.write('%s\t%s\n' % (n[:-4], t)); print(n[:-4], t)
