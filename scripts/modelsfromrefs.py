"""
modelsfromrefs.py

Reads a CS:GO _refs.txt file, extracts just the .mdl entries, and imports +
compiles ONLY those models (plus the materials the models themselves depend
on) into a CS2 addon. Skips the .vmf -> .vmap conversion entirely and skips
re-importing the map's own texture list (you've already done that part).

Failures on individual models/materials are logged and skipped rather than
aborting the whole run.

Usage:
    Place this file next to import_map_community.py and utils/ (so the
    imports below resolve), edit the CONFIG block, then run:

        python modelsfromrefs.py
"""

import os
import subprocess
import time

from utils import utlc as utl

# ==========================================================================
# CONFIG - edit these for your setup
# ==========================================================================

# Path to the CS:GO installation's game dir (contains gameinfo.txt).
# This is where cs_mdl_import resolves source .mdl files from.
S1_GAMECSGO = r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\csgo"

# CS2 addon content dir (where imported .vmdl/.vmat files will be written)
S2_CONTENT_ADDON = r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\content\csgo_addons\ba_jail_seaside"

# CS2 addon name (used as -s2addon arg for source1import)
S2_ADDON_NAME = "ba_jail_seaside"

# Path to the refs.txt file to read model entries from.
# NOTE: you gave the `maps` folder, not an exact filename - point this at
# the actual refs file. Defaulting to the one you already uploaded here;
# change this if the real file on your machine has a different name
# (e.g. ba_jail_seaside_prefab_refs.txt).
REFS_FILE = r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\content\csgo_addons\ba_jail_seaside\maps\ba_jail_seaside_refs.txt"

# Set True to also skip compiling the materials models depend on. Only do
# this if you're SURE you've already imported/compiled every material every
# model in this map needs - otherwise models will show up broken/missing
# textures in Hammer.
SKIP_MODEL_MATERIALS = False

# ==========================================================================


def run_command_safe(cmd):
    """Run a shell command, returning True/False instead of raising/exiting."""
    utl.print_I("--------------------------------")
    utl.print_I("- Running Command: " + cmd)
    utl.print_I("--------------------------------")
    result = subprocess.run(cmd, shell=True)
    return result.returncode == 0


def strip_mdls_from_refs(filename):
    """Reimplementation of import_map_community.StripMDLsFromRefs so we don't
    need to import that module (which would otherwise run its own top-level
    argparse/keypress code)."""
    refs = utl.ReadTextFile(filename)

    mdls = []
    others = []
    utl.SplitMdlFromRefs(mdls, others, refs)

    mdlfilename = filename.replace("_refs.txt", "_mdl_lst.txt")
    utl.EnsureFileWritable(mdlfilename)
    with open(mdlfilename, "w") as f:
        for x in mdls:
            f.write(x + "\n")

    return mdlfilename, mdls


def main():
    start = time.time()

    if not os.path.exists(REFS_FILE):
        print("ERROR: refs file not found: %s" % REFS_FILE)
        print("Check REFS_FILE points at the exact .txt file, not just the folder.")
        return

    if not os.path.isdir(S1_GAMECSGO):
        print("ERROR: S1_GAMECSGO path not found: %s" % S1_GAMECSGO)
        return

    if not os.path.isdir(S2_CONTENT_ADDON):
        print("ERROR: S2_CONTENT_ADDON path not found: %s" % S2_CONTENT_ADDON)
        return

    print("Reading refs file: %s" % REFS_FILE)
    mdl_lst_file, mdlfiles = strip_mdls_from_refs(REFS_FILE)
    print("Found %d model entries." % len([m for m in mdlfiles if not m.startswith("-")]))

    if len(mdlfiles) < 1:
        print("No MDLs found in refs file. Nothing to do.")
        return

    failed_imports = []
    failed_material_compiles = []
    failed_model_compiles = []
    mdlmtls = set()
    extraoptions = ""

    # ---------------------------------------------------------------
    # Step 1: import each model (cs_mdl_import), tolerating failures
    # ---------------------------------------------------------------
    print("\n=== Importing models ===")
    for mdlfile in mdlfiles:
        if mdlfile.startswith("-"):
            if mdlfile in ("-", "-nooptions"):
                extraoptions = ""
            else:
                extraoptions = mdlfile
            continue

        mdlfile = mdlfile.replace("/", "\\")
        outName = S2_CONTENT_ADDON + "\\" + mdlfile.replace(".mdl", ".vmdl")
        refsName = S2_CONTENT_ADDON + "\\" + mdlfile.replace(".mdl", "_refs.txt")

        importCmd = "cs_mdl_import -nop4 %s -i \"%s\" -o \"%s\" \"%s\"" % (
            extraoptions, S1_GAMECSGO, S2_CONTENT_ADDON, mdlfile
        )

        if not run_command_safe(importCmd):
            print("!! FAILED to import: %s" % mdlfile)
            failed_imports.append(mdlfile)
            continue

        # collect the materials this model needs, so we can compile them once
        if os.path.exists(refsName):
            refs = utl.ReadTextFile(refsName)
            refsString = utl.ListStringFromRefs(refs)
            for mtlname in refsString.split("\n"):
                if mtlname:
                    mdlmtls.add(mtlname)

    # ---------------------------------------------------------------
    # Step 2: import the collected model materials via source1import
    # ---------------------------------------------------------------
    if mdlmtls and not SKIP_MODEL_MATERIALS:
        print("\n=== Importing %d model-dependency materials ===" % len(mdlmtls))
        mdlmtlrefs = utl.RefsStringFromList(list(mdlmtls))
        temp_refs = mdl_lst_file.replace("mdl_lst", "mtl_lst")
        utl.EnsureFileWritable(temp_refs)
        with open(temp_refs, "w") as fw:
            fw.write(mdlmtlrefs)

        importRefsCmd = (
            "source1import -retail -nop4 -nop4sync -src1gameinfodir \"%s\" "
            "-s2addon %s -game csgo -usefilelist \"%s\""
            % (S1_GAMECSGO, S2_ADDON_NAME, temp_refs)
        )
        if not run_command_safe(importRefsCmd):
            print("!! WARNING: bulk material import step failed/reported an error.")
            print("   Continuing anyway - individual material compiles below will")
            print("   just fail for whichever materials didn't actually import.")

    # ---------------------------------------------------------------
    # Step 3: compile the model-dependency materials
    # ---------------------------------------------------------------
    if not SKIP_MODEL_MATERIALS:
        print("\n=== Compiling model-dependency materials ===")
        for mtlfile in mdlmtls:
            if mtlfile.startswith("-") or mtlfile == "":
                continue
            mtlfile = mtlfile.replace("/", "\\")
            outName = S2_CONTENT_ADDON + "\\" + mtlfile.replace(".vmt", ".vmat")

            resCompCmd = "resourcecompiler -retail -nop4 -game csgo \"%s\"" % outName
            if not run_command_safe(resCompCmd):
                print("!! FAILED to compile material: %s" % mtlfile)
                failed_material_compiles.append(mtlfile)

    # ---------------------------------------------------------------
    # Step 4: compile the models themselves
    # ---------------------------------------------------------------
    print("\n=== Compiling models ===")
    for mdlfile in mdlfiles:
        if mdlfile.startswith("-"):
            continue
        mdlfile = mdlfile.replace("/", "\\")

        if mdlfile in failed_imports:
            continue

        outName = S2_CONTENT_ADDON + "\\" + mdlfile.replace(".mdl", ".vmdl")
        if not os.path.exists(outName):
            print("!! SKIPPING compile, .vmdl not found (import likely failed silently): %s" % outName)
            failed_model_compiles.append(mdlfile)
            continue

        resCompCmd = "resourcecompiler -retail -nop4 -game csgo \"%s\"" % outName
        if not run_command_safe(resCompCmd):
            print("!! FAILED to compile model: %s" % mdlfile)
            failed_model_compiles.append(mdlfile)

    # ---------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------
    elapsed = time.time() - start
    print("\n\n================ SUMMARY ================")
    print("Elapsed time: %s" % utl.GetElapsedTime(elapsed))
    print("Models attempted: %d" % len([m for m in mdlfiles if not m.startswith("-")]))
    print("Failed imports: %d" % len(failed_imports))
    for f in failed_imports:
        print("   -", f)
    print("Failed material compiles: %d" % len(failed_material_compiles))
    for f in failed_material_compiles:
        print("   -", f)
    print("Failed model compiles: %d" % len(failed_model_compiles))
    for f in failed_model_compiles:
        print("   -", f)
    print("==========================================")


if __name__ == "__main__":
    main()