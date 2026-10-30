"""Resolve existing sound sets and decode preview WAVs outside the game folder."""
from pathlib import Path, PurePosixPath
from dataclasses import dataclass
import hashlib
import os
import math
import wave
import subprocess
import xml.etree.ElementTree as ET
from sr_impex.utilities.effect_tracks import choose_variant


@dataclass
class AudioCue:
    path: Path
    volume: float=1.
    looped: bool=False
    pitch_min: float=1.
    pitch_max: float=1.


def pitch_wave(path,factor,cache):
    """Cache a PCM pitch/rate variant; originals remain read-only."""
    if not math.isfinite(factor) or factor<=0:raise ValueError('Audio pitch factor must be positive')
    if abs(factor-1)<1e-6:return Path(path)
    path=Path(path)
    if path.suffix.lower()!='.wav':raise ValueError('Pitch preview requires decoded PCM WAV audio')
    key=hashlib.sha256(path.read_bytes()+str(factor).encode()).hexdigest()
    target=Path(cache)/'audio'/key/'pitch.wav'
    if not target.is_file():
        target.parent.mkdir(parents=True,exist_ok=True)
        with wave.open(str(path),'rb') as source, wave.open(str(target),'wb') as output:
            if source.getcomptype()!='NONE':raise ValueError('Pitch preview requires PCM audio')
            output.setparams(source.getparams())
            output.setframerate(max(1,round(source.getframerate()*factor)))
            while True:
                chunk=source.readframes(65536)
                if not chunk:break
                output.writeframesraw(chunk)
    return target


def resolve_audio(library,name,relative_to=None,language='en'):
    try:return library.resolve(name,relative_to)
    except (FileNotFoundError,ValueError) as original:
        stem=PurePosixPath(name.replace('\\','/')).stem
        for prefix in ('bf1/sound/ram',f'bf1/sound/{language}/ram','ram'):
            try:return library.resolve(f'{prefix}/{stem}.snr')
            except (FileNotFoundError,ValueError):pass
        try:return library.resolve(stem+'.snr')
        except (FileNotFoundError,ValueError):raise original


def load_audio(library,name,cache,relative_to=None,seed=0,language='en'):
    asset=resolve_audio(library,name,relative_to,language)
    volume=1.;looped=False;pitch_min=pitch_max=1.
    if asset.name.lower().endswith('.xml'):
        root=ET.fromstring(asset.read())
        if root.tag!='fxSoundSet':raise ValueError(f'Unsupported sound-set XML root: {root.tag}')
        variants=[dict(v.attrib,name=(v.text or '').strip()) for v in root.findall('variant')]
        selected=choose_variant(variants,seed)
        if not selected:return None
        volume=float(selected.get('volume',1.))
        pitch_min=float(selected.get('minPitch',1.));pitch_max=float(selected.get('maxPitch',1.))
        looped=root.get('looped','0') not in ('0','false','False','')
        asset=resolve_audio(library,selected['name'],asset,language)
    extension=PurePosixPath(asset.name.replace('\\','/')).suffix.lower()
    if extension in ('.wav','.ogg'):
        return AudioCue(asset.materialize(cache),volume,looped,pitch_min,pitch_max)
    if extension!='.snr':raise ValueError(f'Unsupported audio resource: {asset.name}')
    source=asset.read()
    stream_data=b''
    try:
        partner=library.resolve(PurePosixPath(asset.name.replace('\\','/')).with_suffix('.sns').name,asset)
        stream_data=partner.read()
    except FileNotFoundError:pass
    key=hashlib.sha256(source+stream_data).hexdigest()
    folder=Path(cache)/'audio'/key
    wave=folder/'preview.wav'
    if not wave.is_file():
        folder.mkdir(parents=True,exist_ok=True)
        snr=folder/(PurePosixPath(asset.name.replace('\\','/')).stem+'.snr')
        snr.write_bytes(source)
        if stream_data:snr.with_suffix('.sns').write_bytes(stream_data)
        binary=Path(__file__).resolve().parents[1]/'resources/vgmstream/vgmstream-cli.exe'
        if not binary.is_file():raise FileNotFoundError('Bundled vgmstream decoder is missing')
        temporary=folder/'decoding.wav'
        command=subprocess.run([str(binary),'-o',str(temporary),str(snr)],capture_output=True,
                               timeout=30,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        if command.returncode or not temporary.is_file():
            raise ValueError('Audio decoding failed: '+command.stderr.decode(errors='replace')[-600:])
        temporary.replace(wave)
    return AudioCue(wave,volume,looped,pitch_min,pitch_max)
