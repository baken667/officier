#!/usr/bin/env bash
set -euo pipefail
root=/var/www/onlyoffice/documentserver

write_launcher() {
  local executable="$1" source="$2"
  cat > "$root/server/$executable" <<EOF
#!/bin/sh
export NODE_CONFIG_DIR="\${NODE_CONFIG_DIR:-/etc/onlyoffice/documentserver}"
exec /usr/local/bin/officier-node "$root/server/$source" "\$@"
EOF
  chmod 755 "$root/server/$executable"
}
write_launcher DocService/docservice DocService/sources/server.js
write_launcher DocService/gc DocService/sources/gc.js
write_launcher DocService/prepare4shutdown DocService/sources/shutdown.js
write_launcher FileConverter/converter FileConverter/sources/convertermaster.js
write_launcher Metrics/metrics Metrics/node_modules/statsd/bin/statsd

welcome=/var/www/onlyoffice/documentserver-example/welcome
test -d "$welcome"
cp /tmp/officier-welcome.html "$welcome/officier.html"
cp /tmp/officier-welcome.html "$welcome/docker.html"
cp /usr/share/officier/LICENSE "$welcome/officier-license.txt"
cp /usr/share/officier/build.json "$welcome/officier-build.json"

# Make the modification/source notice reachable from every editor, preserving upstream notices.
/usr/local/bin/officier-node <<'JS'
const fs = require('fs');
const path = require('path');
const base = '/var/www/onlyoffice/documentserver/web-apps/apps';
let changed = 0;
function walk(dir) {
  for (const file of fs.readdirSync(dir, {withFileTypes: true})) {
    const name = path.join(dir, file.name);
    if (file.isDirectory()) walk(name);
    else if (file.name === 'index.html') {
      const original = fs.readFileSync(name, 'utf8');
      if (!original.includes('</body>')) continue;
      const notice = '<a href="/welcome/officier.html" target="_blank" rel="noopener" aria-label="Officier: source and license" style="position:fixed;bottom:2px;left:3px;z-index:10000;font:10px sans-serif;background:#fff;color:#333;padding:1px 3px;border-radius:3px;opacity:.85">Officier · source</a>';
      fs.writeFileSync(name, original.replace('</body>', notice + '</body>'));
      changed++;
    }
  }
}
for (const editor of ['documenteditor', 'spreadsheeteditor', 'presentationeditor', 'pdfeditor', 'visioeditor']) {
  const dir = path.join(base, editor);
  if (fs.existsSync(dir)) walk(dir);
}
if (changed === 0) throw new Error('Editor notice was not installed');
console.log(`Installed Officier source notice in ${changed} editor pages`);
JS
