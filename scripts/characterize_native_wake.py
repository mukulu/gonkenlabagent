#!/usr/bin/env python3
"""Synthetic host-only native wake characterization; never Pi acceptance.

Requires distro libpocketsphinx3/pocketsphinx-en-us, espeak and sox. Temporary
synthetic audio is deleted. The measured detection rate is NOT a human/acoustic
acceptance score. No user audio, microphone, network or GPIO is accessed.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from gonken_agent.audio.keyword_native import NativeKeywordDetector

POSITIVES=('Gon Ken','Gonken',"Gon Ken what is the temperature",'Hey Gon Ken',
           'Hey Gon Ken turn off the fan','Gon Ken turn the fan on after two minutes')
NEGATIVES=('hello there','turn on the fan','what is the temperature','good morning',
           'the conference starts at ten','open the window','go and get the book',
           'I am going camping','the fan actuator started','the fan actuator stopped',
           'yes','thank you')

def run(threshold=1e-20):
    for command in ('espeak','sox'):
        if not shutil.which(command):raise RuntimeError(command+' unavailable')
    rows=[];times=[];audio_seconds=0.0
    with tempfile.TemporaryDirectory(prefix='gonken-synthetic-wake-') as tmp:
        root=Path(tmp);decoder=NativeKeywordDetector('GonKen',root,threshold=threshold)
        try:
            for voice in ('en-us','en-gb'):
                for expected,phrases in ((True,POSITIVES),(False,NEGATIVES)):
                    for phrase in phrases:
                        subprocess.run(['espeak','-v',voice,'-s','150','-w',str(root/'speech.wav'),phrase],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=10)
                        subprocess.run(['sox',str(root/'speech.wav'),'-r','16000','-b','16','-c','1',str(root/'pcm.wav')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=10)
                        with wave.open(str(root/'pcm.wav'),'rb') as w:
                            pcm=b'\0'*12800+w.readframes(w.getnframes())+b'\0'*32000
                        pcm+=b'\0'*((-len(pcm))%2560);decoder.reset();hit=None
                        for offset in range(0,len(pcm),2560):
                            before=time.monotonic();candidate=decoder.feed(pcm[offset:offset+2560]);times.append((time.monotonic()-before)*1000)
                            if candidate and hit is None:hit={'detected_at_ms':(offset+2560)*1000//32000,'keyword_end_ms':candidate.end_sample*1000//16000}
                        audio_seconds+=len(pcm)/32000
                        rows.append({'synthetic_phrase':phrase,'voice':voice,'wake_expected':expected,'native_detected':hit is not None,'hit':hit})
        finally:decoder.close()
    return {'format':'gonken-b15-native-characterization-v1','evidence':'HOST_SYNTHETIC_ONLY',
        'physical_acceptance_claimed':False,'host':platform.platform(),'python':platform.python_version(),
        'threshold':threshold,'samples':len(rows),'positive_native_hits':sum(r['wake_expected'] and r['native_detected'] for r in rows),
        'positive_samples':sum(r['wake_expected'] for r in rows),'negative_native_hits':sum(not r['wake_expected'] and r['native_detected'] for r in rows),
        'negative_samples':sum(not r['wake_expected'] for r in rows),'audio_seconds':round(audio_seconds,3),
        'native_compute_seconds':round(sum(times)/1000,3),'frame_ms':80,'decode_frame_p50_ms':round(statistics.median(times),3),
        'decode_frame_p95_ms':round(sorted(times)[int(.95*(len(times)-1))],3),'decode_frame_max_ms':round(max(times),3),
        'limitations':['synthetic voices are not user speech','native misses use utterance-level Whisper fallback in production','Whisper was not run in this characterization','not Raspberry Pi timing'], 'cases':rows}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--threshold',type=float,default=1e-20);a=parser.parse_args()
    result=run(a.threshold);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2))
