// build.mjs: assembles a cs_script game from source folders into
//   (1) build/core_test.cjs   the game core + data as a CommonJS module, for Node tests and sims (no CS2 API in it)
//   (2) <out>/maps/scripts/<name>.js   the CS2 point_script: one import line, the core, the data, the CS2 adapter
//
// usage: node build.mjs <config.json> [--name NAME]
// config (paths are relative to the config file's folder):
// {
//   "name": "mygame",                       script name -> maps/scripts/mygame.js (env CS2_SCRIPT_NAME or --name override)
//   "coreDir": "src/core",                  plain JS, no CS2 API; files joined in sorted order (00_defs.js, 10_util.js ...)
//   "adapterDir": "src/cs2",                the CS2 side (Instance.*, HUD, players); sorted; skipped if missing
//   "data": { "LEVELS": "out/addon/_gen/levels.json", "MUSIC": {"path": "_gen/music.json", "default": []} },
//                                           each becomes `const NAME = <json>;` after the core; a missing file is an
//                                           error unless it has a default
//   "imports": ["Instance", "CSInputs", ...],   names imported from "cs_script/point_script"
//   "exports": ["LEVELS", "Arena", ...],    what core_test.cjs exports (names from the core or data)
//   "testOut": "build/core_test.cjs",       optional
//   "out": "out/addon"                      addon content root (env CS2_ADDON_OUT overrides)
// }
//
// From space-racer-cs2/tools/build.mjs and hellmatch-cs2/tools/build.mjs (MIT), made project-neutral.
import fs from 'node:fs';
import path from 'node:path';

const args = process.argv.slice(2);
if (!args[0]) { console.error('usage: node build.mjs <config.json> [--name NAME]'); process.exit(2); }
const cfgPath = path.resolve(args[0]);
const base = path.dirname(cfgPath);
const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
const at = (p) => path.resolve(base, p);
const ni = args.indexOf('--name');
const name = ni > 0 ? args[ni + 1] : (process.env.CS2_SCRIPT_NAME || cfg.name);
if (!name || !/^[\w-]+$/.test(name)) { console.error('build: no valid script name (config "name" or --name)'); process.exit(2); }

// every .js file in a folder, sorted, each with a marker line so errors can be traced back to the file
const cat = (dir) => fs.readdirSync(dir).filter((f) => f.endsWith('.js')).sort()
  .map((f) => `// ---- ${f}\n` + fs.readFileSync(path.join(dir, f), 'utf8')).join('\n');

const coreDir = at(cfg.coreDir || 'src/core');
if (!fs.existsSync(coreDir)) { console.error('build: no core folder ' + coreDir); process.exit(1); }
const core = cat(coreDir);

// data constants from JSON files
let data = '';
for (const [k, v] of Object.entries(cfg.data || {})) {
  const spec = typeof v === 'string' ? { path: v } : v;
  const p = at(spec.path);
  let json;
  if (fs.existsSync(p)) json = JSON.stringify(JSON.parse(fs.readFileSync(p, 'utf8')));
  else if ('default' in spec) json = JSON.stringify(spec.default);
  else { console.error(`build: data file for ${k} missing: ${p}`); process.exit(1); }
  data += `const ${k} = ${json};\n`;
}

// (1) the test module
const exportsList = cfg.exports || [];
const testOut = at(cfg.testOut || 'build/core_test.cjs');
const testMod = core + '\n' + data + `module.exports = { ${exportsList.join(', ')} };\n`;
fs.mkdirSync(path.dirname(testOut), { recursive: true });
fs.writeFileSync(testOut, testMod);
console.log('test module', (testMod.length / 1024).toFixed(0), 'KB ->', path.relative(process.cwd(), testOut));

// (2) the CS2 script
const adapterDir = at(cfg.adapterDir || 'src/cs2');
if (fs.existsSync(adapterDir)) {
  const imports = cfg.imports || ['Instance'];
  const head = `import { ${imports.join(', ')} } from "cs_script/point_script";\n`;
  const out = head + core + '\n' + data + cat(adapterDir);
  const addon = process.env.CS2_ADDON_OUT ? path.resolve(process.env.CS2_ADDON_OUT) : at(cfg.out || 'out/addon');
  const dst = path.join(addon, 'maps/scripts', name + '.js');
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  fs.writeFileSync(dst, out);
  console.log('cs2 script', (out.length / 1024).toFixed(0), 'KB ->', path.relative(process.cwd(), dst));
} else {
  console.log('no adapter folder (' + adapterDir + '): test module only');
}
