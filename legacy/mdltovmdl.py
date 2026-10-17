"""
Batch-converts CS:GO/CSS .mdl models to CS2 .vmdl files using Valve's
cs_mdl_import.exe, preserving folder structure under \\models\\.

IMPORTANT: this deliberately avoids "-r" + a bare "*.mdl" wildcard.
That combination causes cs_mdl_import to scan the entire mounted
"-game csgo" content tree (tens of thousands of stock models) instead
of just the folder passed via -i, and can crash (access violation) on
unrelated stock models with complex animation includes - wiping out
the whole batch before it ever reaches your own files.

Instead, this builds an explicit file list (the documented "-l" option)
containing only the .mdl paths you actually want, so cs_mdl_import only
ever touches those files.
"""

import subprocess
import sys
from pathlib import Path

# ---- EDIT THESE IF YOUR SETUP DIFFERS -----------------------------------
CS2_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive")
ADDON_NAME = "ba_jail_seaside"
GAME_MOD = "csgo"
# ---------------------------------------------------------------------------

CS_MDL_IMPORT = CS2_ROOT / "game" / "bin" / "win64" / "cs_mdl_import.exe"
SOURCE_MODELS = CS2_ROOT / "csgo" / ADDON_NAME / "models"
DEST_MODELS = CS2_ROOT / "content" / "csgo_addons" / ADDON_NAME / "models"


def find_mdls(root: Path):
    return sorted(p for p in root.rglob("*.mdl"))


def main():
    if not CS_MDL_IMPORT.exists():
        sys.exit(f"cs_mdl_import.exe not found at:\n  {CS_MDL_IMPORT}")
    if not SOURCE_MODELS.exists():
        sys.exit(f"Source models folder not found:\n  {SOURCE_MODELS}")

    DEST_MODELS.mkdir(parents=True, exist_ok=True)

    source_mdls = find_mdls(SOURCE_MODELS)
    print(f"Found {len(source_mdls)} .mdl files under {SOURCE_MODELS}\n")
    if not source_mdls:
        sys.exit("No .mdl files found - check ADDON_NAME / the source path.")

    # Build an explicit file list of relative paths (Windows backslashes,
    # matching how the tool printed paths in its own log).
    filelist_path = SOURCE_MODELS.parent / "mdl_filelist.txt"
    rel_paths = [str(p.relative_to(SOURCE_MODELS)) for p in source_mdls]
    filelist_path.write_text("\n".join(rel_paths), encoding="utf-8")
    print(f"Wrote explicit file list ({len(rel_paths)} entries) to:\n  {filelist_path}\n")

    cmd = [
        str(CS_MDL_IMPORT),
        "-game", GAME_MOD,
        "-v",
        "-lods",
        "-i", str(SOURCE_MODELS),
        "-o", str(DEST_MODELS),
        "-l", str(filelist_path),
    ]

    print("Running:\n  " + " ".join(f'"{c}"' if " " in c else c for c in cmd) + "\n")

    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout[-8000:])  # tail, this can be long with -v
    if result.stderr:
        print("---- stderr ----")
        print(result.stderr[-4000:])

    crashed = result.returncode < 0 or "accessviolation" in result.stdout.lower()
    if crashed:
        print(f"\n*** Process crashed or exited abnormally (returncode={result.returncode}). ***")
        print("If a minidump was written, check the working directory you ran this from.")
        print("Consider narrowing mdl_filelist.txt to bisect which specific file triggers it.")

    # Verify what actually got converted, relative to \models\
    missing = []
    for mdl in source_mdls:
        rel = mdl.relative_to(SOURCE_MODELS).with_suffix(".vmdl")
        if not (DEST_MODELS / rel).exists():
            missing.append(rel)

    converted = len(source_mdls) - len(missing)
    print(f"\n{converted}/{len(source_mdls)} models converted successfully.")

    if missing:
        report = DEST_MODELS.parent / "mdl_import_failures.txt"
        report.write_text("\n".join(str(r) for r in missing), encoding="utf-8")
        print(f"{len(missing)} still missing - list written to:\n  {report}")


if __name__ == "__main__":
    main()