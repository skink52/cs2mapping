"""
post_import_cleanup.py

Run this AFTER import_map_community.py (with -usebsp, no -skipdeps) has run
- whether it completed fully or died partway through. The native importer
aborts the ENTIRE run on the first model/material it can't handle
(utlc.RunCommand -> Error() -> sys.exit(1)), with no way to opt out, so on
a large map "it died" can mean anything from "barely started" to
"everything imported fine but never got compiled".

This script never edits the .vmap. By default it is driven off the .vmap
itself: vmap_refs.py (next to this file) walks <addon>.vmap and every prefab
it references and writes <addon>_vmap_refs.txt with the materials and models
the map actually uses, minus stock CS2 ones. That catches what the importer's
own <addon>_refs.txt missed (prefab contents, things the importer died
before). Pass --refs to use the importer's refs.txt instead; if the vmap is
missing (importer died before writing it) the refs.txt is used automatically.

USAGE
-----
    python post_import_cleanup.py <addon_name>

<addon_name> must match the folder name under both content\\csgo_addons\\
and game\\csgo_addons\\. It's a required argument on purpose - this script
is meant to be reusable across maps/addons without editing the file, so it
never silently assumes which project you mean.

Optional: --steam-root "<path>" if your Steam library isn't at the
default "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Counter-Strike
Global Offensive".

See README.md for one-time setup (extracting CS:GO's assets, the raw-
content junction, the vpk.signatures fix, VTF staging folders, and
installing VTFCmd).

PHASES
------
  1. MODELS
     Skips re-running cs_mdl_import for any model that already has a
     .vmdl. For compiling, checks the GAME-side compiled output
     (game\\csgo_addons\\<addon>\\...) against the CONTENT-side source
     (content\\csgo_addons\\<addon>\\...) - same addon, same relative path,
     just game\\ instead of content\\, mirroring how import_map_community.py
     itself derives the two folders. If a compiled .vmdl_c/.vmat_c already
     exists AND is newer than its source file, the compile is skipped.
     Comparing timestamps rather than just existence means re-importing a
     fixed model still gets recompiled - existence-only would silently
     skip it forever once any compiled version exists at all.

  2. TEXTURE CASCADE
     Reads every "materials/....vmt" entry directly out of
     <addon>_refs.txt. This is ONLY the map's own direct texture refs - a
     model's OWN material dependencies are a separate set (discovered from
     that model's individual per-model _refs.txt), and Phase 1 already
     imports+compiles those via source1import/resourcecompiler on its own.
     Nothing here duplicates that, and resourcecompiler keeps their
     materials\\... structure correct automatically, same as always.

     For anything not already present (any extension, exact relative path)
     under the addon's own materials\\ folder, runs this cascade:

       a. Already converted and sitting in VTF_STAGING_OUTPUT at the exact
          expected relative path? -> MOVE it straight into the addon and
          immediately generate its .vmat, preserving the materials\\...
          structure from refs.txt exactly.
       b. Else, already staged as a .vtf in VTF_STAGING_INPUT at the exact
          expected path? -> leave it there, queue it for conversion.
       c. Else, found in S1_RAW_CONTENT_ROOT? -> copy the .vtf into
          VTF_STAGING_INPUT (preserving structure), queue it for
          conversion.
       d. Otherwise -> no source anywhere. Flagged as needing the full
          manual Crowbar/Blender/ModelDoc pipeline.

     Once the cascade above finishes, if VTFCMD_PATH is configured, this
     phase makes ONE batch call to VTFCmd across the whole VTF_STAGING_INPUT
     tree (not one call per file - that would pay VTFCmd's startup cost
     hundreds of times over), converting everything sitting there to PNG in
     VTF_STAGING_OUTPUT. It then rechecks each texture queued in step (b)/(c):
     anything that now has a PNG gets moved into the addon and gets its vmat,
     same as (a). Anything still missing after that genuinely needs your
     attention - either VTFCmd isn't configured, or it choked on that
     specific file.

  3. VMAT SWEEP
     Catch-all across the WHOLE addon materials folder (not just what
     Phase 2 just resolved) for any base-color texture still missing a
     .vmat - covers textures that were already sitting there before this
     run even started.

  4. REPORT
     Writes <addon>_cleanup_report.txt next to the refs.txt: models that
     failed to import/compile, textures with no source anywhere, and
     textures that still need a VTF -> PNG conversion (automatic or manual).
"""

import argparse
import glob
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from utils import utlc as utl

# ==========================================================================
# CONFIG - edit these for your setup (see README.md for the one-time setup
# each of these paths assumes)
# ==========================================================================

# Base CS:GO/CS2 install. Standard default Steam library location - only
# change this if your library is somewhere else (or pass --steam-root).
STEAM_CSGO_ROOT = r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive"

# Root of your extracted raw CS:GO source content: a real folder (NTFS
# junction is fine, a plain ".lnk" shortcut is NOT - Python won't follow
# those) that mirrors STEAM_CSGO_ROOT\csgo\materials, \models, etc. See
# README.md "Setup" for the exact commands to extract assets and create
# this junction.
S1_RAW_CONTENT_ROOT = r"C:\cscontent"

# VTF staging folders. Any location works as long as it has a materials\
# subfolder directly underneath, matching the addon's own layout.
VTF_STAGING_INPUT = r"C:\VTF\VTFInput"
VTF_STAGING_OUTPUT = r"C:\VTF\VTFOutput"

# Full path to VTFCmd.exe (ships with VTFEdit-Reloaded, see README.md
# "Installing VTFCmd"). Leave "" to skip automatic conversion entirely and
# rely on manually running VTFEdit's mass export yourself.
VTFCMD_PATH = r"C:\VTF\VTFEdit\VTFCmd.exe"

# Materials models depend on (their own skins/decals) - separate pool from
# the map's own texture refs, handled entirely in Phase 1.
COMPILE_MODEL_MATERIALS = True

# Overwrite existing .vmat files instead of skipping them.
OVERWRITE_VMATS = False

# ==========================================================================

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tga", ".bmp", ".vtf"}

VMAT_TEMPLATE = """Layer0
{{
    shader "csgo_complex.vfx"

    //---- Material ----
    TextureColor "{texpath}"

    //---- Normal ----
    TextureNormal "materials\\default\\default_normal.tga"

    //---- Roughness ----
    TextureRoughness "materials\\default\\default_rough.tga"

    //---- Metalness ----
    TextureMetalness "materials\\default\\default_metal.tga"
}}
"""

VMT_PATTERN = re.compile(r'"file"\s*"([^"]+)"')

# populated in main() once the addon name is known
S2_ADDON_NAME = None
S1_GAMECSGO = None
S2_CONTENT_ADDON = None
S2_GAME_ADDON = None
REFS_FILE = None


def run_command_safe(cmd):
    utl.print_I("--------------------------------")
    utl.print_I("- Running Command: " + cmd)
    utl.print_I("--------------------------------")
    result = subprocess.run(cmd, shell=True)
    return result.returncode == 0


def needs_compile(source_path, compiled_path):
    """True if there's no compiled output yet, or the source is newer than
    the existing compiled output. compiled_path not existing yet (e.g. the
    game\\csgo_addons\\<addon> tree hasn't been created at all) is handled
    fine - os.path.exists just returns False, so this returns True."""
    if not os.path.exists(compiled_path):
        return True
    return os.path.getmtime(source_path) > os.path.getmtime(compiled_path)


SKIP_MODEL_PREFIXES = ("models/player/",)


def strip_mdls_from_refs(filename):
    if filename.endswith("_vmap_refs.txt"):   # our own file: plain "file" lines, no importer options
        with open(filename) as f:
            mdls = [m for m in VMT_PATTERN.findall(f.read()) if m.lower().endswith(".mdl")]
    else:
        refs = utl.ReadTextFile(filename)
        mdls, others = [], []
        utl.SplitMdlFromRefs(mdls, others, refs)
    mdlfilename = filename.replace("_refs.txt", "_mdl_lst.txt")
    utl.EnsureFileWritable(mdlfilename)
    with open(mdlfilename, "w") as f:
        for x in mdls:
            f.write(x + "\n")
    return mdlfilename, mdls


def find_refs_file():
    primary = os.path.join(S2_CONTENT_ADDON, "maps", S2_ADDON_NAME + "_refs.txt")
    if os.path.exists(primary):
        return primary
    fallback = os.path.join(S2_CONTENT_ADDON, "maps", S2_ADDON_NAME + "_prefab_refs.txt")
    if os.path.exists(fallback):
        print("Note: '%s_refs.txt' not found, using '%s' instead" % (S2_ADDON_NAME, fallback))
        return fallback
    return None


# ==========================================================================
# Phase 1 - Models (unchanged behaviour from the previous version)
# ==========================================================================
def phase1_models():
    print("\n" + "=" * 70)
    print("PHASE 1 - MODELS")
    print("=" * 70)

    mdl_lst_file, mdlfiles = strip_mdls_from_refs(REFS_FILE)
    # player models drag in the whole t/ct_animations set (cs_mdl_import runs for an hour+ and the result is unusable
    # in CS2), so they are skipped; more can be listed one per line in maps/<addon>_skip_models.txt
    skip = list(SKIP_MODEL_PREFIXES)
    skip_file = os.path.join(S2_CONTENT_ADDON, "maps", S2_ADDON_NAME + "_skip_models.txt")
    if os.path.exists(skip_file):
        with open(skip_file) as f:
            skip += [l.strip().lower().replace("\\", "/") for l in f if l.strip() and not l.startswith("#")]
    skipped_mdls = [m for m in mdlfiles if not m.startswith("-") and m.lower().replace("\\", "/").startswith(tuple(skip))]
    mdlfiles = [m for m in mdlfiles if m not in skipped_mdls]
    for m in skipped_mdls:
        print("Skipped (skip list): %s" % m)
    real_mdls = [m for m in mdlfiles if not m.startswith("-")]
    print("Model entries found: %d" % len(real_mdls))

    failed_imports = []
    failed_compiles = []
    mdlmtls = set()
    extraoptions = ""
    already_imported = 0

    for mdlfile in mdlfiles:
        if mdlfile.startswith("-"):
            extraoptions = "" if mdlfile in ("-", "-nooptions") else mdlfile
            continue

        mdlfile = mdlfile.replace("/", "\\")
        outName = os.path.join(S2_CONTENT_ADDON, mdlfile.replace(".mdl", ".vmdl"))
        refsName = os.path.join(S2_CONTENT_ADDON, mdlfile.replace(".mdl", "_refs.txt"))

        if os.path.exists(outName):
            already_imported += 1
        else:
            importCmd = "cs_mdl_import -nop4 %s -i \"%s\" -o \"%s\" \"%s\"" % (
                extraoptions, S1_GAMECSGO, S2_CONTENT_ADDON, mdlfile
            )
            if not run_command_safe(importCmd):
                print("!! FAILED to import: %s" % mdlfile)
                failed_imports.append(mdlfile)
                continue

        if os.path.exists(refsName):
            refs = utl.ReadTextFile(refsName)
            for mtlname in utl.ListStringFromRefs(refs).split("\n"):
                if mtlname:
                    mdlmtls.add(mtlname)

    print("Already imported (skipped): %d" % already_imported)
    print("Failed imports: %d" % len(failed_imports))

    if mdlmtls and COMPILE_MODEL_MATERIALS:
        missing_mtls = []
        for mtlfile in mdlmtls:
            if mtlfile.startswith("-") or mtlfile == "":
                continue
            vmat_path = os.path.join(
                S2_CONTENT_ADDON, mtlfile.replace("/", "\\").replace(".vmt", ".vmat")
            )
            if not os.path.exists(vmat_path):
                missing_mtls.append(mtlfile)

        if missing_mtls:
            print("\nImporting %d missing model-dependency materials..." % len(missing_mtls))
            mtlrefs = utl.RefsStringFromList(missing_mtls)
            temp_refs = mdl_lst_file.replace("mdl_lst", "mtl_lst")
            utl.EnsureFileWritable(temp_refs)
            with open(temp_refs, "w") as fw:
                fw.write(mtlrefs)

            importRefsCmd = (
                "source1import -retail -nop4 -nop4sync -src1gameinfodir \"%s\" "
                "-s2addon %s -game csgo -usefilelist \"%s\""
                % (S1_GAMECSGO, S2_ADDON_NAME, temp_refs)
            )
            if not run_command_safe(importRefsCmd):
                print("!! WARNING: bulk material import reported an error.")
                print("   Continuing - per-material compiles below will just")
                print("   fail for whichever ones didn't actually import.")

    if COMPILE_MODEL_MATERIALS:
        print("\nCompiling model-dependency materials (%d)..." % len(mdlmtls))
        mtl_skipped = 0
        for mtlfile in mdlmtls:
            if mtlfile.startswith("-") or mtlfile == "":
                continue
            outName = os.path.join(
                S2_CONTENT_ADDON, mtlfile.replace("/", "\\").replace(".vmt", ".vmat")
            )
            compiledName = os.path.join(
                S2_GAME_ADDON, mtlfile.replace("/", "\\").replace(".vmt", ".vmat_c")
            )
            if not needs_compile(outName, compiledName):
                mtl_skipped += 1
                continue
            resCompCmd = "resourcecompiler -retail -nop4 -game csgo \"%s\"" % outName
            if not run_command_safe(resCompCmd):
                print("!! FAILED to compile material: %s" % mtlfile)
        print("Materials already compiled and up to date, skipped: %d" % mtl_skipped)

    print("\nCompiling models (%d)..." % len(real_mdls))
    model_skipped = 0
    for mdlfile in mdlfiles:
        if mdlfile.startswith("-"):
            continue
        mdlfile = mdlfile.replace("/", "\\")
        if mdlfile in failed_imports:
            continue

        outName = os.path.join(S2_CONTENT_ADDON, mdlfile.replace(".mdl", ".vmdl"))
        if not os.path.exists(outName):
            print("!! SKIPPING compile, .vmdl not found: %s" % outName)
            failed_compiles.append(mdlfile)
            continue

        compiledName = os.path.join(S2_GAME_ADDON, mdlfile.replace(".mdl", ".vmdl_c"))
        if not needs_compile(outName, compiledName):
            model_skipped += 1
            continue

        resCompCmd = "resourcecompiler -retail -nop4 -game csgo \"%s\"" % outName
        if not run_command_safe(resCompCmd):
            print("!! FAILED to compile model: %s" % mdlfile)
            failed_compiles.append(mdlfile)

    print("Models already compiled and up to date, skipped: %d" % model_skipped)

    return failed_imports, failed_compiles


# ==========================================================================
# Phase 2 - Texture cascade
#
# All path helpers below take vmt_relpath EXACTLY as read from refs.txt,
# e.g. "materials/decals/hr_decals/large_stain_a.vmt" - the leading
# "materials/" segment is kept (not stripped), because S2_CONTENT_ADDON,
# VTF_STAGING_INPUT, VTF_STAGING_OUTPUT, and S1_RAW_CONTENT_ROOT all mirror
# the CS:GO tree starting AT their own root - i.e. each of them already
# has its own materials\ subfolder directly underneath, so the vmt path's
# own "materials/" prefix is exactly what supplies that folder level.
# Passing any of those four roots straight into these helpers is correct;
# do not additionally append "materials" to the root yourself.
# ==========================================================================
def normalize_relpath(vmt_relpath):
    """Collapses accidental doubled slashes, e.g. 'materials//vv_spray.vmt'
    (seen in your actual refs.txt) -> 'materials/vv_spray.vmt'."""
    return re.sub(r"/+", "/", vmt_relpath)


def specific_path(root, vmt_relpath, ext):
    base, _old_ext = os.path.splitext(vmt_relpath)
    return os.path.join(root, base.replace("/", os.sep) + ext)


def any_ext_exists(root, vmt_relpath):
    base, _old_ext = os.path.splitext(vmt_relpath)
    base = base.replace("/", os.sep)
    search_dir = os.path.join(root, os.path.dirname(base))
    base_name = os.path.basename(base)
    if not os.path.isdir(search_dir):
        return False
    return len(glob.glob(os.path.join(search_dir, base_name + ".*"))) > 0


def is_base_color(name):
    low = name.lower()
    return not any(s in low for s in ("_normal", "_n", "_rough", "_roughness", "_metal", "_m"))


def is_tools_material(vmt_relpath):
    """materials/tools/... - nodraw, invisible, clip, trigger, skip, etc.
    These are compiler/editor-only markers with no real texture behind
    them; CS2's base content already provides them, so this pipeline
    should never try to source, stage, or convert one."""
    base, _ext = os.path.splitext(vmt_relpath)
    parts = base.split("/")
    return len(parts) >= 2 and parts[0].lower() == "materials" and parts[1].lower() == "tools"


def write_single_vmat(png_path, materials_root_with_suffix):
    if not is_base_color(os.path.basename(png_path)):
        return
    vmat_path = os.path.splitext(png_path)[0] + ".vmat"
    if os.path.exists(vmat_path) and not OVERWRITE_VMATS:
        return
    rel = os.path.relpath(png_path, materials_root_with_suffix)
    texpath = "materials\\" + str(rel)
    content = VMAT_TEMPLATE.format(texpath=texpath)
    with open(vmat_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Generated vmat: %s" % vmat_path)


def run_vtfcmd_batch_convert():
    """One VTFCmd invocation across the WHOLE VTF_STAGING_INPUT tree,
    converting every .vtf found (recursively) to .png.

    Deliberately passes NO -output flag. Checked directly against VTFCmd's
    own source (CreateOutputPath() in vtfcmd.c): when -output IS given, it
    builds the destination from ONLY the bare filename - strrchr() on the
    input path, keeping everything after the last backslash - so -recurse
    finding a file three folders deep still gets dumped flat into -output,
    with no subfolder recreated. Worse, two different subfolders with a
    same-named texture would silently overwrite each other there. When
    -output is omitted, the same function instead writes the result right
    next to the source file - which is exactly what preserves the
    materials\\... structure, since that "next to the source" location IS
    wherever -recurse found it. So conversion happens in place inside
    VTF_STAGING_INPUT, and the reclaim step below looks for each result
    there (not in VTF_STAGING_OUTPUT).

    A single batch call rather than one per file - each invocation pays a
    real startup cost, the same kind of overhead you saw with
    resourcecompiler's GPU/device init lines."""
    cmd = "\"%s\" -folder \"%s\\*.vtf\" -recurse -exportformat \"png\" -silent" % (
        VTFCMD_PATH, VTF_STAGING_INPUT
    )
    return run_command_safe(cmd)


def phase2_texture_cascade():
    print("\n" + "=" * 70)
    print("PHASE 2 - TEXTURE CASCADE")
    print("=" * 70)

    with open(REFS_FILE, "r") as f:
        text = f.read()
    candidate_vmts = [
        normalize_relpath(m) for m in VMT_PATTERN.findall(text) if m.lower().endswith(".vmt")
    ]
    all_vmts = [v for v in candidate_vmts if not is_tools_material(v)]
    excluded_tools = len(candidate_vmts) - len(all_vmts)
    print("Materials referenced directly by the map: %d" % len(all_vmts))
    if excluded_tools:
        print("Excluded as tools/ materials (nodraw, invisible, etc.): %d" % excluded_tools)

    materials_root_with_suffix = os.path.join(S2_CONTENT_ADDON, "materials")

    missing = [v for v in all_vmts if not any_ext_exists(S2_CONTENT_ADDON, v)]
    print("Not yet present in addon: %d" % len(missing))

    resolved_from_output = []
    awaiting_conversion = []
    fully_missing = []

    def try_claim_converted(vmt):
        """A converted PNG can be in one of two places: VTF_STAGING_OUTPUT
        (the manual VTFEdit GUI workflow lands here if you point its
        output there) or right next to its source .vtf inside
        VTF_STAGING_INPUT (where the automatic VTFCmd path writes it -
        see run_vtfcmd_batch_convert). Check both."""
        for candidate_root in (VTF_STAGING_OUTPUT, VTF_STAGING_INPUT):
            png_candidate = specific_path(candidate_root, vmt, ".png")
            if not os.path.exists(png_candidate):
                continue
            dest = specific_path(S2_CONTENT_ADDON, vmt, ".png")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.move(png_candidate, dest)
            print("Moved converted texture -> %s" % dest)
            write_single_vmat(dest, materials_root_with_suffix)
            return True
        return False

    for vmt in missing:
        if try_claim_converted(vmt):
            resolved_from_output.append(vmt)
            continue

        vtf_in = specific_path(VTF_STAGING_INPUT, vmt, ".vtf")
        if os.path.exists(vtf_in):
            awaiting_conversion.append(vmt)
            continue

        src_vtf = specific_path(S1_RAW_CONTENT_ROOT, vmt, ".vtf")
        if os.path.exists(src_vtf):
            os.makedirs(os.path.dirname(vtf_in), exist_ok=True)
            shutil.copy2(src_vtf, vtf_in)
            print("Copied from source, queued for conversion: %s" % vtf_in)
            awaiting_conversion.append(vmt)
            continue

        print("!! FULLY MISSING (no source found anywhere): %s" % vmt)
        fully_missing.append(vmt)

    print("\nResolved directly from VTFOutput: %d" % len(resolved_from_output))
    print("Queued for conversion (VTFInput): %d" % len(awaiting_conversion))
    print("Fully missing (need manual pipeline): %d" % len(fully_missing))

    auto_converted = 0
    if awaiting_conversion:
        if VTFCMD_PATH and os.path.exists(VTFCMD_PATH):
            print("\nRunning automatic VTF -> PNG conversion via VTFCmd...")
            run_vtfcmd_batch_convert()

            still_pending = []
            for vmt in awaiting_conversion:
                if try_claim_converted(vmt):
                    auto_converted += 1
                else:
                    still_pending.append(vmt)
            awaiting_conversion = still_pending
            print("Auto-converted and moved into addon: %d" % auto_converted)
            print("Still pending after auto-convert attempt: %d" % len(awaiting_conversion))
        elif VTFCMD_PATH:
            print("\nWARNING: VTFCMD_PATH is set but not found: %s" % VTFCMD_PATH)
            print("Falling back to manual conversion for everything queued.")
        else:
            print("\nVTFCMD_PATH not configured - queued files need a manual")
            print("VTFEdit mass-export (VTFInput -> VTFOutput), then a rerun.")

    # final recheck - confirm what's genuinely still absent, not just bookkeeping
    still_missing = [v for v in all_vmts if not any_ext_exists(S2_CONTENT_ADDON, v)]
    print("\nRecheck: still missing from addon after this run: %d" % len(still_missing))

    return awaiting_conversion, fully_missing


# ==========================================================================
# Phase 3 - Vmat sweep (whole materials folder, catch-all)
# ==========================================================================
def phase3_vmat_sweep():
    print("\n" + "=" * 70)
    print("PHASE 3 - VMAT SWEEP")
    print("=" * 70)

    materials_root = Path(S2_CONTENT_ADDON) / "materials"
    if not materials_root.exists():
        print("Materials folder not found: %s" % materials_root)
        return

    created, skipped = 0, 0
    for tex in materials_root.rglob("*"):
        if not tex.is_file() or tex.suffix.lower() not in IMAGE_EXTS:
            continue
        if not is_base_color(tex.name):
            continue
        vmat_path = tex.with_suffix(".vmat")
        if vmat_path.exists() and not OVERWRITE_VMATS:
            skipped += 1
            continue
        rel = tex.relative_to(materials_root)
        texpath = "materials\\" + str(rel).replace("/", "\\")
        content = VMAT_TEMPLATE.format(texpath=texpath)
        vmat_path.write_text(content, encoding="utf-8")
        print("Wrote: %s" % vmat_path)
        created += 1

    print("\nVmats created: %d. Skipped (already existed): %d." % (created, skipped))


# ==========================================================================
# Phase 4 - Report
# ==========================================================================
def phase4_write_report(failed_imports, failed_compiles, still_needs_conversion, fully_missing):
    report_path = os.path.join(S2_CONTENT_ADDON, "maps", S2_ADDON_NAME + "_cleanup_report.txt")
    lines = []
    lines.append("Cleanup report for addon: %s" % S2_ADDON_NAME)
    lines.append("Refs file used: %s" % REFS_FILE)
    lines.append("")
    lines.append("=== MODELS - FAILED TO IMPORT (%d) ===" % len(failed_imports))
    lines.extend(failed_imports or ["(none)"])
    lines.append("")
    lines.append("=== MODELS - FAILED TO COMPILE (%d) ===" % len(failed_compiles))
    lines.extend(failed_compiles or ["(none)"])
    lines.append("")
    lines.append(
        "=== TEXTURES - STILL NEED VTF -> PNG CONVERSION (%d) ===" % len(still_needs_conversion)
    )
    lines.append(
        "(staged in VTF_STAGING_INPUT; run VTFCmd/VTFEdit manually if"
        " VTFCMD_PATH isn't set, or investigate if it is and these still failed)"
    )
    lines.extend(still_needs_conversion or ["(none)"])
    lines.append("")
    lines.append("=== TEXTURES - FULLY MISSING, NO SOURCE FOUND ANYWHERE (%d) ===" % len(fully_missing))
    lines.append("(these need the manual Crowbar/Blender/ModelDoc pipeline)")
    lines.extend(fully_missing or ["(none)"])

    utl.EnsureFileWritable(report_path)
    with open(report_path, "w") as f:
        f.write("\n".join(lines))

    print("\nReport written to: %s" % report_path)
    return report_path


# ==========================================================================
# Main
# ==========================================================================
def main():
    global S2_ADDON_NAME, S1_GAMECSGO, S2_CONTENT_ADDON, S2_GAME_ADDON, REFS_FILE

    parser = argparse.ArgumentParser(description="Post-import model/texture cleanup for a CS2 addon")
    parser.add_argument(
        "addon_name",
        help="CS2 addon name - must match the folder name under both"
        " content\\csgo_addons\\ and game\\csgo_addons\\",
    )
    parser.add_argument(
        "--refs",
        action="store_true",
        help="drive the run off the importer's <addon>_refs.txt instead of scanning the .vmap",
    )
    parser.add_argument(
        "--steam-root",
        default=STEAM_CSGO_ROOT,
        help="Override the base 'Counter-Strike Global Offensive' folder"
        " if your Steam library isn't at the default location"
        " (default: %(default)s)",
    )
    args = parser.parse_args()

    S2_ADDON_NAME = args.addon_name
    S1_GAMECSGO = os.path.join(args.steam_root, "csgo")
    S2_CONTENT_ADDON = os.path.join(args.steam_root, "content", "csgo_addons", S2_ADDON_NAME)
    S2_GAME_ADDON = os.path.join(args.steam_root, "game", "csgo_addons", S2_ADDON_NAME)

    print("Addon: %s" % S2_ADDON_NAME)
    print("S2 content addon: %s" % S2_CONTENT_ADDON)
    print("S2 game addon (compiled output): %s" % S2_GAME_ADDON)

    if not os.path.isdir(S1_GAMECSGO):
        print("ERROR: S1_GAMECSGO not found: %s" % S1_GAMECSGO)
        return
    if not os.path.isdir(S2_CONTENT_ADDON):
        print("ERROR: S2_CONTENT_ADDON not found: %s" % S2_CONTENT_ADDON)
        return

    REFS_FILE = None
    vmap_path = os.path.join(S2_CONTENT_ADDON, "maps", S2_ADDON_NAME + ".vmap")
    if not args.refs and os.path.exists(vmap_path):
        try:
            import vmap_refs
            REFS_FILE = vmap_refs.build(S2_ADDON_NAME, args.steam_root)[0]
        except Exception as e:
            print("!! vmap scan failed (%s) - falling back to the importer's refs.txt" % e)
    elif not args.refs:
        print("Note: %s not found (importer died before writing it?) - using the importer's refs.txt" % vmap_path)
    if REFS_FILE is None:
        REFS_FILE = find_refs_file()
    if REFS_FILE is None:
        print(
            "ERROR: could not find '%s_refs.txt' or '%s_prefab_refs.txt' under %s\\maps"
            % (S2_ADDON_NAME, S2_ADDON_NAME, S2_CONTENT_ADDON)
        )
        return
    print("Refs file: %s" % REFS_FILE)

    start = time.time()

    failed_imports, failed_compiles = phase1_models()
    still_needs_conversion, fully_missing = phase2_texture_cascade()
    phase3_vmat_sweep()
    report_path = phase4_write_report(failed_imports, failed_compiles, still_needs_conversion, fully_missing)

    elapsed = time.time() - start
    print("\n\n" + "=" * 70)
    print("DONE - %s" % utl.GetElapsedTime(elapsed))
    print("=" * 70)
    print("Models failed (import / compile): %d / %d" % (len(failed_imports), len(failed_compiles)))
    print("Textures still needing VTF -> PNG conversion: %d" % len(still_needs_conversion))
    print("Textures with no source found anywhere: %d" % len(fully_missing))
    print("Full report: %s" % report_path)


if __name__ == "__main__":
    main()