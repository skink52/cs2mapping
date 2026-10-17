import os
import shutil
import re

# CONFIG
CSGO_ROOT = r"C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\csgo"
CSGO_MODELS = os.path.join(CSGO_ROOT, "models")
CSGO_MATERIALS = os.path.join(CSGO_ROOT, "materials")

OUTPUT_ROOT = os.path.join(CSGO_ROOT, "ba_jail_seaside")
OUTPUT_MODELS = os.path.join(OUTPUT_ROOT, "models")
OUTPUT_MATERIALS = os.path.join(OUTPUT_ROOT, "materials")

# Find the _refs.txt file
refs_file = None
for f in os.listdir(os.getcwd()):
    if f.endswith("_refs.txt"):
        refs_file = os.path.join(os.getcwd(), f)
        break

if refs_file is None:
    print("ERROR: No _refs.txt file found.")
    exit(1)

print(f"Using refs file: {refs_file}")

# Parse model paths
mdl_paths = []
with open(refs_file, "r") as f:
    for line in f:
        if ".mdl" not in line:
            continue

        match = re.search(r'"file"\s*"([^"]+)"', line)
        if not match:
            continue

        path = match.group(1).replace("\\", "/").strip()

        if not path.endswith(".mdl"):
            continue

        if path.startswith("models/"):
            path = path[len("models/"):]

        mdl_paths.append(path)

print(f"Found {len(mdl_paths)} model references.")

# Extensions
std_exts = [".mdl", ".vvd", ".phy"]
vtx_exts = [
    "dx90.vtx", "dx80.vtx", "sw.vtx", "vtx",
    "dx90", "dx80", "sw"
]

missing_models = []
missing_materials = []

def copy_file(src, dst_dir):
    if os.path.exists(src):
        shutil.copy2(src, dst_dir)
        print(f"Copied {src}")
        return True
    return False

def copy_companion_files(src_dir, base, dst_dir):
    for ext in std_exts:
        copy_file(os.path.join(src_dir, base + ext), dst_dir)

    for ext in vtx_exts:
        copy_file(os.path.join(src_dir, base + "." + ext), dst_dir)

def scan_includemodels(mdl_path):
    includes = []
    try:
        with open(mdl_path, "rb") as f:
            data = f.read().decode(errors="ignore")
            matches = re.findall(r'\$includemodel\s+"([^"]+)"', data, re.IGNORECASE)
            for m in matches:
                includes.append(m.replace("\\", "/"))
    except:
        pass
    return includes

def scan_materials_from_mdl(mdl_path):
    materials = []
    try:
        with open(mdl_path, "rb") as f:
            data = f.read().decode(errors="ignore")
            matches = re.findall(r'materials/[^"\0]+\.vmt', data, re.IGNORECASE)
            for m in matches:
                materials.append(m.replace("\\", "/"))
    except:
        pass
    return materials

def scan_textures_from_vmt(vmt_path):
    textures = []
    try:
        with open(vmt_path, "r", errors="ignore") as f:
            for line in f:
                line = line.strip().lower()
                if "$basetexture" in line or "$bumpmap" in line or "$normalmap" in line:
                    match = re.search(r'"([^"]+)"', line)
                    if match:
                        textures.append(match.group(1).replace("\\", "/"))
    except:
        pass
    return textures

# Process each model
for mdl_rel in mdl_paths:
    print(f"\nProcessing: {mdl_rel}")

    src_mdl_path = os.path.join(CSGO_MODELS, mdl_rel.replace("/", os.sep))
    src_dir = os.path.dirname(src_mdl_path)
    dst_dir = os.path.join(OUTPUT_MODELS, os.path.dirname(mdl_rel))

    base = os.path.splitext(os.path.basename(mdl_rel))[0]

    if not os.path.exists(src_mdl_path):
        print(f"WARNING: Missing model: {src_mdl_path}")
        missing_models.append(mdl_rel)
        continue

    os.makedirs(dst_dir, exist_ok=True)

    copy_companion_files(src_dir, base, dst_dir)

    includes = scan_includemodels(src_mdl_path)
    for inc in includes:
        print(f"Found includemodel dependency: {inc}")
        inc_path = inc
        if inc_path.startswith("models/"):
            inc_path = inc_path[len("models/"):]
        inc_src_mdl = os.path.join(CSGO_MODELS, inc_path.replace("/", os.sep))
        inc_src_dir = os.path.dirname(inc_src_mdl)
        inc_base = os.path.splitext(os.path.basename(inc_path))[0]
        inc_dst_dir = os.path.join(OUTPUT_MODELS, os.path.dirname(inc_path))
        os.makedirs(inc_dst_dir, exist_ok=True)
        if os.path.exists(inc_src_mdl):
            copy_companion_files(inc_src_dir, inc_base, inc_dst_dir)
        else:
            print(f"WARNING: Missing includemodel: {inc_src_mdl}")

    materials = scan_materials_from_mdl(src_mdl_path)
    for mat in materials:
        print(f"Material: {mat}")
        mat_rel = mat[len("materials/"):] if mat.startswith("materials/") else mat
        mat_src = os.path.join(CSGO_MATERIALS, mat_rel.replace("/", os.sep))
        mat_dst_dir = os.path.join(OUTPUT_MATERIALS, os.path.dirname(mat_rel))
        os.makedirs(mat_dst_dir, exist_ok=True)

        if os.path.exists(mat_src):
            shutil.copy2(mat_src, mat_dst_dir)
            print(f"Copied VMT: {mat_src}")

            textures = scan_textures_from_vmt(mat_src)
            for tex in textures:
                tex_rel = tex + ".vtf"
                tex_src = os.path.join(CSGO_MATERIALS, tex_rel.replace("/", os.sep))
                tex_dst_dir = os.path.join(OUTPUT_MATERIALS, os.path.dirname(tex_rel))
                os.makedirs(tex_dst_dir, exist_ok=True)
                if os.path.exists(tex_src):
                    shutil.copy2(tex_src, tex_dst_dir)
                    print(f"Copied VTF: {tex_src}")
                else:
                    print(f"Missing VTF: {tex_src}")
                    missing_materials.append(tex_rel)
        else:
            print(f"Missing VMT: {mat_src}")
            missing_materials.append(mat_rel)

print("\nDone.")
print(f"Output folder: {OUTPUT_ROOT}")

if missing_models:
    print("\nMissing models:")
    for m in missing_models:
        print(" -", m)

if missing_materials:
    print("\nMissing materials/textures:")
    for m in missing_materials:
        print(" -", m)
