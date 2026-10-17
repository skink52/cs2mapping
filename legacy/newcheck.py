"""
Cross-checks every .mdl's expected VTX checksum against the checksum
actually stored in its .dx90.vtx file. A mismatch here is exactly what
crashed cs_mdl_import on trashdumpster02a - and since cs_mdl_import
dies on the FIRST mismatch it hits rather than skipping and continuing,
one bad pair kills every file queued after it in the same -l run.

This lets us find ALL mismatched pairs up front (not just the first one
that happens to reach the tool alphabetically), so we can exclude them
from the file list, run the rest safely, and know exactly which ones
still need to be resolved (e.g. via Crowbar decompile/recompile) as a
separate task.

File formats (little-endian, from the Source SDK public headers):

studiohdr_t (mdl):
    offset 4  : version   (int32)
    offset 8  : checksum  (int32)   <- must match vtx's checksum field

OptimizedModel::FileHeader_t (vtx):
    offset 0  : version        (int32)
    offset 4  : vertCacheSize  (int32)
    offset 8  : maxBonesPerStrip  (int16)
    offset 10 : maxBonesPerTri   (int16)
    offset 12 : maxBonesPerVert  (int32)
    offset 16 : checksum         (int32)  <- compared against mdl's checksum

Usage:
    python check_vtx_checksums.py
    python check_vtx_checksums.py "path\\to\\models" "path\\to\\mdl_filelist.txt"
"""

import struct
import sys
from pathlib import Path

DEFAULT_SOURCE_MODELS = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive"
    r"\csgo\ba_jail_seaside\models"
)
DEFAULT_FILELIST = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive"
    r"\csgo\ba_jail_seaside\mdl_filelist.txt"
)

VTX_SUFFIXES = [".dx90.vtx", ".dx80.vtx", ".sw.vtx", ".vtx"]


def mdl_checksum(mdl_path: Path):
    with open(mdl_path, "rb") as f:
        data = f.read(12)
    if len(data) < 12:
        return None
    return struct.unpack("<i", data[8:12])[0]


def vtx_checksum(vtx_path: Path):
    with open(vtx_path, "rb") as f:
        data = f.read(20)
    if len(data) < 20:
        return None
    return struct.unpack("<i", data[16:20])[0]


def find_vtx(base: Path):
    for suf in VTX_SUFFIXES:
        candidate = Path(str(base) + suf)
        if candidate.exists():
            return candidate
    return None


def main():
    source_models = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE_MODELS
    filelist_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_FILELIST

    if not source_models.exists():
        sys.exit(f"Source models folder not found:\n  {source_models}")

    if filelist_path.exists():
        rel_paths = [Path(line.strip()) for line in
                     filelist_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        rel_paths = [p.relative_to(source_models) for p in source_models.rglob("*.mdl")]

    print(f"Checking {len(rel_paths)} models for mdl/vtx checksum mismatches\n")

    mismatched = []
    unreadable = []
    ok = 0

    for rel in rel_paths:
        mdl_path = source_models / rel
        base = mdl_path.with_suffix("")
        vtx_path = find_vtx(base)

        if not mdl_path.exists() or vtx_path is None:
            unreadable.append((rel, "missing mdl or vtx"))
            continue

        mchk = mdl_checksum(mdl_path)
        vchk = vtx_checksum(vtx_path)

        if mchk is None or vchk is None:
            unreadable.append((rel, "couldn't read header"))
            continue

        if mchk != vchk:
            mismatched.append((rel, mchk, vchk, vtx_path.name))
        else:
            ok += 1

    print(f"{ok} models have matching mdl/vtx checksums.")
    print(f"{len(mismatched)} models have a MISMATCH (these are what crash cs_mdl_import).")
    if unreadable:
        print(f"{len(unreadable)} models couldn't be checked (missing file / bad header).")

    if mismatched:
        print("\nMismatched models:")
        for rel, mchk, vchk, vtxname in mismatched:
            print(f"  {rel}  (mdl wants {mchk}, {vtxname} has {vchk})")

        bad_out = source_models.parent / "mdl_checksum_mismatches.txt"
        bad_out.write_text("\n".join(str(r) for r, *_ in mismatched), encoding="utf-8")
        print(f"\nList written to:\n  {bad_out}")

        # Also write a CLEAN filelist with the bad ones excluded, ready to
        # feed straight into cs_mdl_import via -l
        clean_out = source_models.parent / "mdl_filelist_clean.txt"
        bad_set = {str(r) for r, *_ in mismatched}
        clean_rels = [str(r) for r in rel_paths if str(r) not in bad_set]
        clean_out.write_text("\n".join(clean_rels), encoding="utf-8")
        print(f"Wrote a clean file list (mismatches excluded, {len(clean_rels)} entries) to:\n  {clean_out}")
        print("Re-run cs_mdl_import with -l pointed at that clean list to safely convert the rest.")

    if unreadable:
        print("\nCouldn't check (missing file or bad header):")
        for rel, reason in unreadable[:20]:
            print(f"  {rel}  ({reason})")


if __name__ == "__main__":
    main()