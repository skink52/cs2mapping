"""stage_c passes on the current (already cleaned) vmap, appending to the existing cleanup log.  run_pass.py <addon> <root> pass[,pass]"""
import sys, os, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stage_c
addon, root, passes = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
lp = os.path.join(root, 'content', addon, 'maps', addon + '_cleanup_log.txt')
old = open(lp, encoding='utf-8').read() if os.path.exists(lp) else ''
c = stage_c.run(addon, root, passes)
c.files['maps/%s_cleanup_log.txt' % addon] = (old.rstrip() + '\n\nFollow-up pass (%s): %s\n' % (datetime.date.today(), ', '.join(passes)) +
    '\n'.join('- ' + l for l in c.log) + '\n' + '\n'.join('- TO CHECK: ' + t for t in c.todo) + '\n').encode()
for rel, data in c.files.items():
    p = os.path.join(c.out, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'wb').write(data)
for rel, data in c.game_files.items():
    p = os.path.join(root, 'out', addon + '_game', rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'wb').write(data)
print('\n'.join(['- ' + l for l in c.log] + ['TO CHECK: ' + t for t in c.todo]))
if c.need: print('NEED CS:GO archives:', sorted(c.need), '(or these files from the extracted CS:GO content, copied into <root>/embedded/<addon>/:', ', '.join(sorted(c.need_paths)) + ')')
print('FILES:', sorted(c.files))
