"""Validate the applied source overlay and set the matching upstream wire version."""
import hashlib
import json
from pathlib import Path
import re
import sys

server, version_file, revision, version = sys.argv[1:]
server = Path(server)
if not re.fullmatch(r'[0-9a-f]{40}', revision):
    raise SystemExit('SOURCE_REVISION must be a full Git commit SHA')
if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9.-]+)?', version):
    raise SystemExit('Invalid Officier version')
manifest = json.loads((server.parent / 'patches/manifest.json').read_text())
for patch in manifest['components']['server']['patches']:
    for name, hashes in patch['files'].items():
        actual = hashlib.sha256((server / name).read_bytes()).hexdigest()
        if actual != hashes['after']:
            raise SystemExit(f'{name}: Officier patch is missing or source has changed')
package = Path(version_file).read_text().strip()
match = re.fullmatch(r'(9\.4\.0)-(\d+)(?:.*)?', package)
if not match:
    raise SystemExit(f'Unexpected upstream package version: {package}')
defines = server / 'Common/sources/commondefines.js'
text = defines.read_text()
text, count1 = re.subn(r"const buildVersion = '[^']*';", f"const buildVersion = '{match[1]}';", text)
text, count2 = re.subn(r'const buildNumber = \d+;', f'const buildNumber = {match[2]};', text)
if count1 != 1 or count2 != 1:
    raise SystemExit('Upstream build metadata layout changed')
defines.write_text(text)
build = {'name': 'Officier', 'version': version, 'revision': revision, 'upstreamPackage': package,
         'serverRevision': manifest['components']['server']['revision'],
         'source': f'https://github.com/baken667/officier/tree/{revision}',
         'scope': 'Patched source-built Node server; upstream editor assets and native converter'}
(server / 'officier-build.json').write_text(json.dumps(build, indent=2) + '\n')
