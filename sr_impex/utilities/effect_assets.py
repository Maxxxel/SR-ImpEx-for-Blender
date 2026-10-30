"""Read-only external effect library. Blender-independent and never writes to the game.

Loose files take precedence over PAKs. References remain game-relative strings;
materializing an archive member only creates a disposable preview cache copy.
"""
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import hashlib
import io
import re
import struct
import zlib
import json
import os
import tempfile

EXTENSIONS={'.fxb','.dds','.tga','.png','.xml','.snr','.sns','.wav','.ogg','.drs','.ska','.bms'}
CACHE_VERSION=2


def _stamp(path):
    stat=path.stat()
    return [stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns]


def _basename(name):
    return bool(name) and name not in ('.','..') and '/' not in name and '\\' not in name and ':' not in name and '\x00' not in name


def _extension(name):
    name=name.rsplit('/',1)[-1];at=name.rfind('.')
    return name[at:] if at>0 else ''


def virtual_path(value):
    value = str(value).replace('\\', '/').strip().strip('\x00')
    parts = value.split('/')
    if not value or value.startswith('/') or ':' in value or '..' in parts:
        raise ValueError('Use a relative game resource name')
    return '/'.join(p for p in parts if p not in ('','.')).casefold()


@dataclass(frozen=True)
class Asset:
    name: str
    source: Path
    offset: int = 0
    size: int = -1

    def read(self):
        if self.size < 0:
            return self.source.read_bytes()
        with self.source.open('rb') as stream:
            stream.seek(self.offset)
            value = stream.read(self.size)
        if len(value) != self.size:
            raise ValueError(f'Archive changed; refresh the library: {self.source.name}')
        return value

    def materialize(self, cache):
        if self.size < 0:
            return self.source
        stamp = self.source.stat()
        key = hashlib.sha256(f'{self.source}:{stamp.st_size}:{stamp.st_mtime_ns}:{stamp.st_ctime_ns}'.encode()).hexdigest()[:20]
        path = Path(cache) / 'pak' / key / virtual_path(self.name)
        if not path.is_file() or path.stat().st_size != self.size:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + '.tmp')
            temporary.write_bytes(self.read())
            temporary.replace(path)
        return path


def pak_entries(path):
    """PAK v1: raw member ranges followed by a zlib-compressed directory."""
    path = Path(path)
    with path.open('rb') as stream:
        magic, end, length, compressed = struct.unpack('<4I', stream.read(16))
        if magic != 0x014b4150 or not 16 <= end <= path.stat().st_size:
            raise ValueError('Not a PAK v1 archive')
        if not 0 < length <= 128 * 1024 * 1024 or end + compressed > path.stat().st_size:
            raise ValueError('Invalid PAK directory range')
        stream.seek(end)
        decoder = zlib.decompressobj()
        data = decoder.decompress(stream.read(compressed), length + 1)
        if len(data) != length or not decoder.eof:
            raise ValueError('Invalid PAK directory size')
    directory = io.BytesIO(data)
    def word():
        return struct.unpack('<I', directory.read(4))[0]
    count = word()
    if count > 1_000_000:
        raise ValueError('Invalid PAK member count')
    result = []
    for _ in range(count):
        n = word()
        if not 0 < n <= 32768:
            raise ValueError('Invalid PAK member name')
        name = directory.read(n).decode('latin1').rstrip('\x00')
        start, stop = word(), word()
        virtual_path(name)
        if not 16 <= start <= stop <= end:
            raise ValueError('Invalid PAK member range')
        result.append(Asset(name, path, start, stop-start))
    return result


class EffectLibrary:
    """Lazy, persistent metadata index; no archive contents are extracted upfront."""
    def __init__(self, game_root='', effects_folder='', use_paks=True,cache_dir=None):
        self.game_root = Path(game_root).resolve() if game_root else None
        self.effects_folder = Path(effects_folder).resolve() if effects_folder else None
        self.use_paks = use_paks
        self._loose = None
        self._packed = None
        self.errors = []
        self._basenames={}
        self._asset_lists={}
        self._directory_stamps={};self._pak_stamps=None
        self.cache_stats={'directories_scanned':0,'directories_reused':0,'paks_parsed':0,'paks_reused':0}
        folder=Path(cache_dir) if cache_dir else Path(os.environ.get('LOCALAPPDATA',Path.home()/'.cache'))/'SRImpEx'/'effect_library'
        identity=json.dumps([str(p.resolve()).casefold() if p else '' for p in (self.game_root,self.effects_folder)]+[use_paks])
        self.cache_file=folder/(hashlib.sha256(identity.encode()).hexdigest()+'.json') if cache_dir is not False else None
        self._manifest={'version':CACHE_VERSION,'directories':{},'paks':{}}
        self._dirty=False
        if self.cache_file:
            try:
                value=json.loads(self.cache_file.read_text(encoding='utf8'))
                if value.get('version')==CACHE_VERSION and isinstance(value.get('directories'),dict) and isinstance(value.get('paks'),dict):
                    self._manifest=value
            except (OSError,ValueError,TypeError,AttributeError):pass

    def _save_cache(self):
        if self.cache_file is None or not self._dirty:return
        temporary=None
        try:
            self.cache_file.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf8',dir=self.cache_file.parent,delete=False) as stream:
                temporary=Path(stream.name);json.dump(self._manifest,stream,separators=(',',':'))
            temporary.replace(self.cache_file)
            self._dirty=False
        except OSError:pass  # A read-only/full cache directory must not prevent asset access.
        finally:
            try:
                if temporary and temporary.exists():temporary.unlink(missing_ok=True)
            except OSError:pass

    def refresh(self,force=False):
        """Validate metadata lazily on next operation; never called on frames/draws."""
        if not force:
            try:
                loose_valid=self._loose is None or all(_stamp(Path(path))==stamp for path,stamp in self._directory_stamps.items())
                # Missing roots becoming available must invalidate an empty index.
                if self._loose is not None:
                    for root in self._loose_roots():
                        if root.is_dir() and str(root) not in self._directory_stamps:loose_valid=False
                packed_valid=self._packed is None or self._archive_stamps()==self._pak_stamps
                if loose_valid and packed_valid:return
            except OSError:pass
        self._loose=self._packed=None;self._basenames.clear();self.errors.clear()
        self._asset_lists.clear()
        self._directory_stamps={};self._pak_stamps=None
        if force:
            self._manifest={'version':CACHE_VERSION,'directories':{},'paks':{}}
            self._dirty=True
            self._save_cache()

    def _directory(self,path):
        key=str(path);stamp=_stamp(path);self._directory_stamps[key]=stamp
        record=self._manifest['directories'].get(key)
        if (isinstance(record,dict) and record.get('stamp')==stamp
                and all(isinstance(record.get(k),list) and all(isinstance(n,str) and _basename(n) for n in record[k]) for k in ('files','dirs'))):
            self.cache_stats['directories_reused']+=1
            return record
        files=[];dirs=[]
        with os.scandir(path) as entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    if not getattr(entry.stat(follow_symlinks=False),'st_file_attributes',0)&0x400:dirs.append(entry.name)
                elif entry.is_file() and _extension(entry.name).lower() in EXTENSIONS:files.append(entry.name)
        record={'stamp':stamp,'files':sorted(files),'dirs':sorted(dirs)}
        self._manifest['directories'][key]=record
        self._dirty=True
        self.cache_stats['directories_scanned']+=1
        return record

    def _loose_roots(self):
        return ([self.game_root/'Mods'/'Unpack'] if self.game_root else [])+([self.effects_folder] if self.effects_folder else [])

    def _archive_stamps(self):
        if not self.game_root or not self.use_paks:return {}
        return {str(path):_stamp(path) for path in (self.game_root/'base'/'pak').glob('*.pak')}

    def _loose_index(self):
        if self._loose is not None:
            return self._loose
        self._loose = {}
        roots = self._loose_roots()
        for root in roots:
            if not root.is_dir():
                continue
            pending=[(root,'')];seen=set()
            while pending:
                directory,relative=pending.pop();resolved=str(directory)
                if resolved in seen:continue
                seen.add(resolved)
                try:record=self._directory(directory)
                except OSError as exc:
                    self.errors.append(f'{directory}: {exc}');continue
                pending.extend((directory/name,(relative+'/'+name if relative else name)) for name in reversed(record['dirs']))
                for filename in record['files']:
                    path=directory/filename;name=relative+'/'+filename if relative else filename
                    self._loose[virtual_path(name)]=Asset(name,path)
        self._save_cache()
        return self._loose

    def _pak_index(self):
        if self._packed is not None:
            return self._packed
        self._packed = {}
        self._pak_stamps={}
        if not self.game_root or not self.use_paks:
            return self._packed
        # Only current asset archives, never pak-legacy/pak-test. Numeric ordering
        # is this library's override policy, not a claim about engine mount order.
        def order(path):
            digits = re.findall(r'\d+', path.stem)
            return (int(digits[-1]) if digits else 0, path.name.casefold())
        paths = (self.game_root / 'base' / 'pak').glob('*.pak')
        for path in sorted(paths, key=order):
            try:
                stamp=_stamp(path);key=str(path);self._pak_stamps[key]=stamp;record=self._manifest['paks'].get(key)
                entries=None
                if isinstance(record,dict) and record.get('stamp')==stamp:
                    try:
                        entries=[]
                        for name,offset,size in record['entries']:
                            if not isinstance(name,str):raise ValueError('Invalid cached PAK name')
                            virtual_path(name)
                            if type(offset) is not int or type(size) is not int or not 16<=offset<=offset+size<=stamp[0]:raise ValueError('Invalid cached PAK range')
                            entries.append(Asset(name,path,offset,size))
                        self.cache_stats['paks_reused']+=1
                    except (KeyError,TypeError,ValueError):entries=None
                if entries is None:
                    entries=pak_entries(path);self.cache_stats['paks_parsed']+=1
                    self._manifest['paks'][key]={'stamp':stamp,'entries':[[a.name,a.offset,a.size] for a in entries]}
                    self._dirty=True
                for asset in entries:
                    self._packed[virtual_path(asset.name)] = asset
            except (OSError, ValueError, struct.error, zlib.error) as exc:
                self.errors.append(f'{path.name}: {exc}')
        self._save_cache()
        return self._packed

    def _match(self,index, key):
        if key in index:
            return index[key]
        lookup=self._basenames.get(id(index))
        if lookup is None:
            lookup={}
            for name,asset in index.items():lookup.setdefault(name.rsplit('/',1)[-1],[]).append((name,asset))
            self._basenames[id(index)]=lookup
        candidates=[asset for name,asset in lookup.get(key.rsplit('/',1)[-1],[]) if name.endswith('/'+key)]
        if len(candidates) == 1:
            return candidates[0]
        if candidates:
            raise ValueError(f'Ambiguous resource {key}: '+', '.join(a.name for a in candidates[:5]))
        return None

    def resolve(self, name, relative_to=None):
        key = virtual_path(name)
        if relative_to:
            parent = relative_to.source if isinstance(relative_to, Asset) else Path(relative_to)
            nearby = parent.parent / key
            if nearby.is_file():
                return Asset(key, nearby)
            if isinstance(relative_to, Asset):
                qualified = str(PurePosixPath(virtual_path(relative_to.name)).parent / key)
                loose = self._loose_index()
                if qualified in loose:
                    return loose[qualified]
                packed = self._pak_index()
                if qualified in packed:
                    return packed[qualified]
        for index in (self._loose_index(),):
            found = self._match(index, key)
            if found:
                return found
        found = self._match(self._pak_index(), key)
        if found:
            return found
        raise FileNotFoundError(f'Resource not found: {name}. Set the Effects Folder or Skylords Reborn Folder in add-on preferences.')

    def assets(self, extensions=None):
        key=frozenset(extensions) if extensions is not None else None
        if key in self._asset_lists:return list(self._asset_lists[key])
        entries = dict(self._pak_index())
        entries.update(self._loose_index())
        result=sorted((a for k,a in entries.items() if extensions is None or _extension(k) in extensions), key=lambda a:a.name.casefold())
        self._asset_lists[key]=result
        return list(result)

    def effects(self):
        return self.assets({'.fxb'})
