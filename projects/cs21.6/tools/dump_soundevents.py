"""Extract CS2 stock soundevents (*.vsndevts_c) from the VPK and dump them as JSON + KV3 text.

usage: python3 dump_soundevents.py [pak01_dir.vpk] [out_dir] [name ...]
names default to: weapons ui player   (soundevents/game_sounds_<name>.vsndevts_c)
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kv3bin
from vpk import VPK

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_VPK = '/mnt/user-data/uploads/game/csgo/pak01_dir.vpk'
DEFAULT_OUT = os.path.join(os.path.dirname(HERE), 'build')


def main():
    args = sys.argv[1:]
    vpk_path = args[0] if args else DEFAULT_VPK
    out_dir = args[1] if len(args) > 1 else DEFAULT_OUT
    names = args[2:] or ['weapons', 'ui', 'player']
    os.makedirs(out_dir, exist_ok=True)

    v = VPK(vpk_path)
    base = re.sub(r'_dir\.vpk$', '', vpk_path)
    archives = {}
    for arc in {e[0] for e in v.files.values()}:
        p = '%s_%03d.vpk' % (base, arc)
        if os.path.exists(p):
            archives[arc] = p

    for name in names:
        path = 'soundevents/game_sounds_%s.vsndevts_c' % name
        if not v.has(path):
            print('%s: not in VPK' % path)
            continue
        arc = v.archive_of(path)
        if arc != 0x7fff and arc not in archives:
            print('%s: skipped, archive %03d not available' % (path, arc))
            continue
        data = v.read(path, archives)
        events = kv3bin.decode_resource(data, keep_flags=True)
        with open(os.path.join(out_dir, 'soundevents_%s.json' % name), 'w') as f:
            json.dump(events, f, indent=1)
        with open(os.path.join(out_dir, 'soundevents_%s.vsndevts.txt' % name), 'w') as f:
            f.write(kv3bin.to_kv3_text(events))
        print('%s: %d events -> soundevents_%s.json / .vsndevts.txt' % (path, len(events), name))


if __name__ == '__main__':
    main()
