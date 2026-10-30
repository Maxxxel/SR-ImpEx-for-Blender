"""Joint keys shared by the DRS and SKA exporters."""
import zlib


# This key is interpreted by the animation sampler as a special alpha track.
ALPHA_TRACK_ID = 0x16C2CE77


def generate_bone_id(bone_name: str) -> int:
    """Return FoundationR's checksum of the exact UTF-8 bone name.

    FoundationR starts its reflected CRC-32 accumulator at zero and applies
    no final XOR. zlib's interface complements both ends, hence the seed and
    final XOR here. Names are case-sensitive and are not normalized.
    """
    return (zlib.crc32(bone_name.encode("utf-8"), 0xFFFFFFFF) ^ 0xFFFFFFFF) & 0xFFFFFFFF


def resolve_bone_ids(bone_names, known_ids):
    """Preserve known keys, generate new ones, and reject unsafe collisions."""
    result = {}
    by_key = {}
    for name in bone_names:
        key = known_ids[name] if name in known_ids else generate_bone_id(name)
        if key == ALPHA_TRACK_ID:
            raise ValueError(f"Bone '{name}' uses the reserved animation alpha ID 0x{key:08X}; rename it before export.")
        other = by_key.get(key)
        if other is not None and other != name:
            raise ValueError(f"Bones '{other}' and '{name}' share animation ID 0x{key:08X}; rename one before export.")
        by_key[key] = name
        result[name] = key
    return result
