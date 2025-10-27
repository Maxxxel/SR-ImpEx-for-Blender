# pak_indexer.py
from __future__ import annotations
import os, io, json, time, struct, zlib, re
from typing import Iterable

_MAGIC_PAK_V1 = 0x014B4150  # "PAK\x01" (little-endian) == 21709136
_FILTERS = ["effects", "sound"]

# ---------- helpers

def _pak_dir(game_root: str) -> str:
    return os.path.join(game_root, "base", "pak")

def _read_exact(f: io.BufferedReader, n: int) -> bytes:
    b = f.read(n)
    if len(b) != n:
        raise EOFError("Unexpected EOF")
    return b

def _print(*a):
    print("[pak_indexer]", *a)

def _write_filename_to_pak(out_json_path: str, mapping: dict[str, str], root: str) -> None:
    os.makedirs(os.path.dirname(out_json_path), exist_ok=True)
    with open(out_json_path, "w", encoding="utf-8") as fp:
        json.dump(
            {
                "root": root,
                "created": int(time.time()),
                "files": mapping  # {"textures/a.dds": "effects_pak2.pak", ...}
            },
            fp,
            ensure_ascii=False,
            indent=2,
        )

# ---------- versioning (extract integer version from filename)

# Examples that parse well:
#   effects.pak           -> version 0
#   effects_pak1.pak      -> 1
#   effects1.pak          -> 1
#   v2_effects.pak        -> 2
# Strategy: last integer in the base name is the version
_LAST_INT_RE = re.compile(r"(\d+)(?!.*\d)")

def _pak_version(pak_filename: str) -> int:
    base = os.path.splitext(os.path.basename(pak_filename))[0]
    m = _LAST_INT_RE.search(base)
    return int(m.group(1)) if m else 0

def _iter_effect_paks(pak_dir: str) -> Iterable[str]:
    try:
        names = [
            os.path.join(pak_dir, n)
            for n in os.listdir(pak_dir)
            if n.lower().endswith(".pak")
            and any(f in n.lower() for f in _FILTERS)
        ]
    except FileNotFoundError:
        return []
    # sort by (version asc, name asc). Later versions come last and will overwrite.
    names.sort(key=lambda p: (_pak_version(os.path.basename(p)), os.path.basename(p).lower()))
    return names

# ---------- PAK\x01 parser (your layout)

def _zlib_or_raw_deflate(buf: bytes) -> bytes:
    # Try zlib wrapper first; fallback to raw DEFLATE.
    try:
        return zlib.decompress(buf)
    except Exception:
        d = zlib.decompressobj(wbits=-zlib.MAX_WBITS)
        out = d.decompress(buf)
        out += d.flush()
        return out

def _parse_pak_v1_list_names(pak_path: str) -> list[str]:
    """
    Header: [magic:u32][index_offset:u32][index_decompressed_size:u32][index_compressed_size:u32]
    Index:  [count:u32] then count * { [name_len:u32][name:bytes][start:u32][end:u32] }
    """
    names: list[str] = []
    fsize = os.path.getsize(pak_path)
    with open(pak_path, "rb") as fp:
        head = _read_exact(fp, 16)
        magic, idx_off, idx_size, idx_csize = struct.unpack("<IIII", head)
        if magic != _MAGIC_PAK_V1:
            raise ValueError(f"{pak_path}: not PAK\\x01 (magic=0x{magic:08X})")
        if idx_off + idx_csize > fsize:
            raise ValueError(f"{pak_path}: index out of range")

        fp.seek(idx_off)
        cblob = _read_exact(fp, idx_csize)
        iblob = _zlib_or_raw_deflate(cblob)
        idx = io.BytesIO(iblob)

        def _read_u32() -> int:
            b = idx.read(4)
            if len(b) != 4:
                raise EOFError("index EOF")
            return struct.unpack("<I", b)[0]

        count = _read_u32()
        if count > 1_000_000:
            raise ValueError(f"{pak_path}: unreasonable file count {count}")

        for _ in range(count):
            nlen = _read_u32()
            if nlen > 32768:
                raise ValueError(f"{pak_path}: unreasonable name length {nlen}")
            raw = idx.read(nlen)
            if len(raw) != nlen:
                raise EOFError(f"{pak_path}: truncated name")
            try:
                name = raw.decode("utf-8")
            except UnicodeDecodeError:
                name = raw.decode("latin-1", errors="replace")
            # consume start/end (we don't need them in the map)
            _ = idx.read(8)
            # keep stored virtual path as-is
            names.append(name)
    return names

# ---------- public API

def build_index(game_root: str, out_json_path: str) -> None:
    pak_dir = _pak_dir(game_root)
    if not os.path.isdir(pak_dir):
        _print(f"pak dir not found: {pak_dir}")
        _write_filename_to_pak(out_json_path, {}, game_root)
        return

    files_to_pak: dict[str, str] = {}
    any_effects = False

    for pak_path in _iter_effect_paks(pak_dir):
        any_effects = True
        pak_name = os.path.basename(pak_path)
        try:
            names = _parse_pak_v1_list_names(pak_path)
            # later paks in the sorted list have higher version -> overwrite older entries
            for vpath in names:
                files_to_pak[vpath] = pak_name
            _print(f"{pak_name} (v{_pak_version(pak_name)}): {len(names)} names")
        except Exception as e:
            _print(f"{pak_name}: skipped ({e})")

    if not any_effects:
        _print("No 'effects' .pak files found.")

    _write_filename_to_pak(out_json_path, files_to_pak, game_root)
    _print(f"Wrote filename→pak map: {out_json_path}")

def _read_u32(f: io.BufferedReader) -> int:
    b = f.read(4)
    if len(b) != 4:
        raise PakError("Unexpected EOF while reading uint32")
    return struct.unpack("<I", b)[0]

class PakError(Exception):
    pass

def _read_toc_from(fp: io.BufferedReader, dir_offset: int, dir_uncomp_size: int, dir_comp_size: int):
    """
    Returns list of entries: [{'name': str, 'offset': int, 'end': int, 'size': int}]
    """
    fp.seek(dir_offset, os.SEEK_SET)
    comp = fp.read(dir_comp_size)
    if len(comp) != dir_comp_size:
        raise PakError("Could not read compressed TOC block")
    try:
        toc_bytes = zlib.decompress(comp)
    except Exception as e:
        raise PakError(f"zlib decompress TOC failed: {e}")
    if len(toc_bytes) != dir_uncomp_size:
        # Some tools can emit a few trailing zeros; don't be strict-fatal
        pass

    ds = io.BytesIO(toc_bytes)
    files_count = _read_u32(ds)
    entries = []
    for i in range(files_count):
        name_len = _read_u32(ds)
        name_bytes = ds.read(name_len)
        if len(name_bytes) != name_len:
            raise PakError(f"EOF in name {i}")
        try:
            name = name_bytes.decode("ascii")
        except UnicodeDecodeError:
            # Spec says ASCII; still allow latin-1 to avoid crash
            name = name_bytes.decode("latin-1", errors="replace")
        off = _read_u32(ds)
        end = _read_u32(ds)
        if end < off:
            raise PakError(f"Invalid range for entry {i}: end<off ({end}<{off})")
        entries.append({
            "name": name,
            "offset": off,
            "end": end,
            "size": end - off,
        })
    return entries

def _norm_relpath(p: str) -> str:
    # normalize to backslashes for matching; keep lowercase for case-insensitive compare
    return p.replace("/", "\\").lower()

def _find_entry(entries, rel_path: str):
    """
    Match by exact normalized path first, then by endswith (useful if index stores a longer prefix).
    """
    needle = _norm_relpath(rel_path)
    # exact
    for e in entries:
        if _norm_relpath(e["name"]) == needle:
            return e
    # endswith fallback
    for e in entries:
        if _norm_relpath(e["name"]).endswith(needle):
            return e
    return None

def extract_single(game_root: str, pak_name: str, rel_path: str, out_file: str) -> None:
    """
    Open game_root/base/pak/<pak_name>, extract the file at rel_path to out_file.
    Format per provided C#:
      header:
        u32 magic = 0x014B4150
        u32 data_end_offset  (first free offset after raw file data)
        u32 toc_uncompressed_size
        u32 toc_compressed_size
      data region: raw file bytes laid out starting at file offset 16
      toc (zlib) at 'data_end_offset':
        u32 file_count
        repeat file_count times:
          u32 name_len, name[ascii], u32 file_offset, u32 file_end
        file_size = file_end - file_offset
    """
    pak_path = os.path.join(game_root, "base", "pak", pak_name)
    if not os.path.isfile(pak_path):
        raise PakError(f"PAK not found: {pak_path}")

    with open(pak_path, "rb") as fp:
        magic = _read_u32(fp)
        if magic != _MAGIC_PAK_V1:
            raise PakError(f"Bad magic: 0x{magic:08X} (expected 0x{_MAGIC_PAK_V1:08X})")

        data_end = _read_u32(fp)
        toc_size = _read_u32(fp)
        toc_comp = _read_u32(fp)

        # Basic sanity
        pak_size = os.path.getsize(pak_path)
        if data_end < 16 or data_end > pak_size:
            raise PakError(f"Invalid data_end offset {data_end} for size {pak_size}")
        if data_end + toc_comp > pak_size:
            raise PakError(f"TOC exceeds file bounds (off {data_end} + comp {toc_comp} > size {pak_size})")

        # Read TOC
        entries = _read_toc_from(fp, data_end, toc_size, toc_comp)
        entry = _find_entry(entries, rel_path)
        if not entry:
            # help diagnose by showing a couple of close candidates (same basename)
            base = os.path.basename(rel_path.replace("/", "\\")).lower()
            alts = [e["name"] for e in entries if os.path.basename(e["name"]).lower() == base]
            hint = f" Candidates with same file name: {alts[:5]}" if alts else ""
            raise PakError(f"Path not found in PAK TOC: '{rel_path}'.{hint}")

        off, size = entry["offset"], entry["size"]
        if off + size > pak_size:
            raise PakError(f"Entry out of bounds: off {off} + size {size} > pak {pak_size}")

        fp.seek(off, os.SEEK_SET)
        data = fp.read(size)
        if len(data) != size:
            raise PakError(f"Short read: wanted {size} bytes, got {len(data)}")

        os.makedirs(os.path.dirname(out_file), exist_ok=True)
        with open(out_file, "wb") as wf:
            wf.write(data)

        print(f"[pak_indexer] extracted {rel_path} from {pak_name} -> {out_file} ({size} bytes)")