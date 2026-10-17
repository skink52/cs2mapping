import os
import shutil
import re

# --- CONFIG ---
LIST_FILE   = "ba_jail_seaside_refs.txt"          # your import list
SCAN_ROOT   = r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\content\csgo_addons\ba_jail_seaside\materials"                   # directory you already have (PNG, etc.)
SOURCE_ROOT = r"C:\source1\materials"       # where to search for missing .vtf files
DEST_ROOT   = r"C:\VTF\VTFInput\materials"  # where to copy found .vtf files
# -------------------------------------------------------------

# Regex to extract the path inside quotes
pattern = re.compile(r'"file"\s*"([^"]+)"')

# Step 1: Parse importfilelist.txt
wanted_entries = []

with open(LIST_FILE, "r") as f:
    for line in f:
        match = pattern.search(line)
        if match:
            full_path = match.group(1)
            if full_path.lower().endswith(".vmt"):
                # Extract relative path under materials/
                rel_path = full_path.replace("materials/", "", 1)
                wanted_entries.append(rel_path)

print(f"Found {len(wanted_entries)} .vmt entries in importfilelist.txt")

# Step 2: Scan SCAN_ROOT for existing basenames
existing_basenames = set()

for root, dirs, files in os.walk(SCAN_ROOT):
    for file in files:
        name, ext = os.path.splitext(file)
        existing_basenames.add(name.lower())

# Step 3: Determine missing textures
missing = []

for rel_path in wanted_entries:
    basename = os.path.splitext(os.path.basename(rel_path))[0].lower()
    if basename not in existing_basenames:
        missing.append(rel_path)

print(f"Missing textures: {len(missing)}")

# Step 4: Search SOURCE_ROOT for missing .vtf files
found_vtf_files = []

for root, dirs, files in os.walk(SOURCE_ROOT):
    for file in files:
        if file.lower().endswith(".vtf"):
            rel = os.path.relpath(os.path.join(root, file), SOURCE_ROOT)
            rel_norm = rel.replace("\\", "/").lower()

            # Convert missing .vmt path → .vtf path
            missing_vtf_paths = [
                m.lower().replace(".vmt", ".vtf") for m in missing
            ]

            if rel_norm in missing_vtf_paths:
                found_vtf_files.append(os.path.join(root, file))

print(f"Found {len(found_vtf_files)} .vtf files to copy")

# Step 5: Copy while preserving folder structure
for src_path in found_vtf_files:
    rel_path = os.path.relpath(src_path, SOURCE_ROOT)
    dest_path = os.path.join(DEST_ROOT, rel_path)

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    shutil.copy2(src_path, dest_path)

    print(f"Copied: {rel_path}")

print("\nDone.")
