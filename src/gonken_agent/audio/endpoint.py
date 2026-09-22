"""Conservative PCM16 speech endpoint detection; no model, no audio persistence.

Only ends an already bounded *question* capture after sustained energy followed
by silence. No detected speech or persistent room noise retains the original
maximum capture window. Wake windows/probes/PTT remain unchanged.
"""
from __future__ import annotations
from array import array
import math
from pathlib import Path
import struct
import sys

class SpeechEndpoint:
    def __init__(self, rate: int, *, threshold: int=250, silence_ms: int=900):
        if type(rate) is not int or not 8000<=rate<=192000 or rate%50!=0 or type(threshold) is not int or not 50<=threshold<=2000 or type(silence_ms) is not int or not 500<=silence_ms<=2000:
            raise ValueError('invalid_speech_endpoint_policy')
        self.rate=rate; self.threshold=threshold; self.silence_frames=math.ceil(silence_ms/20)
        self.frame_bytes=(rate//50)*2
        self.tail=b'';self.frames=0;self.voiced=0;self.quiet=0;self.speech_seen=False;self.finished=False
        self.offset=0;self.header=None

    def feed(self, pcm: bytes) -> bool:
        if not isinstance(pcm,bytes) or len(pcm)>262144: raise ValueError('endpoint_input_too_large')
        data=self.tail+pcm;size=self.frame_bytes
        upto=(len(data)//size)*size
        for pos in range(0,upto,size):
            samples=array('h');samples.frombytes(data[pos:pos+size])
            if sys.byteorder!='little': samples.byteswap()
            energy=sum(x*x for x in samples)/len(samples)
            self.frames+=1
            if energy>=self.threshold*self.threshold:
                self.voiced+=1;self.quiet=0
                if self.voiced>=8: self.speech_seen=True
            else:
                self.voiced=0;self.quiet+=1
            if self.frames>=60 and self.speech_seen and self.quiet>=self.silence_frames:
                self.finished=True
        self.tail=data[upto:]
        return self.finished

    @staticmethod
    def wav_offset(header: bytes, rate: int) -> int | None:
        if len(header)<12 or header[:4]!=b'RIFF' or header[8:12]!=b'WAVE':return None
        position=12;valid=False
        while position+8<=len(header):
            name=header[position:position+4];length=struct.unpack_from('<I',header,position+4)[0]
            if name==b'data': return position+8 if valid else None
            if name==b'fmt ' and length>=16 and position+24<=len(header):
                encoding,channels,hz,_,_,bits=struct.unpack_from('<HHIIHH',header,position+8)
                valid=(encoding,channels,hz,bits)==(1,1,rate,16)
            if length>4096: return None
            position+=8+length+(length%2)
        return None

    def observe(self, path: Path, *, raw: bool=False) -> bool:
        """Read only newly captured bounded bytes; absent/partial headers defer."""
        try:
            if path.is_symlink():return False
            with path.open('rb') as stream:
                if self.header is None:
                    self.header=0 if raw else self.wav_offset(stream.read(4096),self.rate)
                    if self.header is None:return False
                stream.seek(self.header+self.offset)
                data=stream.read(32768)
            self.offset+=len(data)
            return self.feed(data)
        except (OSError,ValueError,struct.error):
            return False
