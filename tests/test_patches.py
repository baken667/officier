import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('patches', ROOT / 'scripts/patches.py')
patches = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patches)


class PatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.server = self.root / 'server'
        self.server.mkdir()
        (self.root / 'patches').mkdir()
        subprocess.run(['git', 'init', '-q', str(self.server)], check=True)
        patches.git(self.server, 'config', 'user.name', 'Patch test')
        patches.git(self.server, 'config', 'user.email', 'test@example.invalid')
        for name in ('a', 'b'):
            (self.server / name).write_text('before\n')
        patches.git(self.server, 'add', '.')
        patches.git(self.server, 'commit', '-qm', 'fixture')
        self.manifest = {'schema': 1, 'components': {'server': {
            'revision': patches.git(self.server, 'rev-parse', 'HEAD'), 'patches': []
        }}}
        for name in ('a', 'b'):
            file = f'patches/{name}.patch'
            (self.root / file).write_text(f'--- a/{name}\n+++ b/{name}\n@@ -1 +1 @@\n-before\n+after\n')
            self.manifest['components']['server']['patches'].append({
                'patch': file, 'files': {name: {
                    key: hashlib.sha256((key + '\n').encode()).hexdigest()
                    for key in ('before', 'after')
                }}
            })
        self.write_manifest()

    def write_manifest(self):
        (self.root / 'patches/manifest.json').write_text(json.dumps(self.manifest))

    def test_round_trip_and_repeated_apply(self):
        patches.run(self.root, 'check')
        patches.run(self.root, 'apply')
        patches.run(self.root, 'apply')
        self.assertEqual((self.server / 'a').read_text(), 'after\n')
        patches.run(self.root, 'revert')
        patches.run(self.root, 'revert')
        self.assertEqual(patches.git(self.server, 'status', '--porcelain'), '')

    def test_preserves_local_edits_before_any_mutation(self):
        (self.server / 'b').write_text('user work\n')
        with self.assertRaisesRegex(RuntimeError, 'unexpected contents'):
            patches.run(self.root, 'apply')
        self.assertEqual((self.server / 'a').read_text(), 'before\n')
        self.assertEqual((self.server / 'b').read_text(), 'user work\n')

    def test_rejects_wrong_revision(self):
        self.manifest['components']['server']['revision'] = '0' * 40
        self.write_manifest()
        with self.assertRaisesRegex(RuntimeError, 'expected'):
            patches.run(self.root, 'apply')
        self.assertEqual((self.server / 'a').read_text(), 'before\n')

    def test_preflights_all_patches(self):
        (self.root / 'patches/b.patch').write_text('invalid patch\n')
        with self.assertRaises(RuntimeError):
            patches.run(self.root, 'apply')
        self.assertEqual((self.server / 'a').read_text(), 'before\n')

    def test_bad_result_is_rolled_back(self):
        (self.root / 'patches/b.patch').write_text('--- a/b\n+++ b/b\n@@ -1 +1 @@\n-before\n+wrong\n')
        with self.assertRaisesRegex(RuntimeError, 'unexpected contents'):
            patches.run(self.root, 'apply')
        self.assertEqual(patches.git(self.server, 'status', '--porcelain'), '')

    def test_new_file_can_be_changed_by_later_patch(self):
        (self.root / 'patches/c-create.patch').write_text(
            'diff --git a/c b/c\n'
            'new file mode 100644\n'
            'index 0000000..a403026\n'
            '--- /dev/null\n'
            '+++ b/c\n'
            '@@ -0,0 +1 @@\n'
            '+created\n'
        )
        (self.root / 'patches/c-update.patch').write_text(
            'diff --git a/c b/c\n'
            'index a403026..181b4d5 100644\n'
            '--- a/c\n'
            '+++ b/c\n'
            '@@ -1 +1 @@\n'
            '-created\n'
            '+updated\n'
        )
        self.manifest['components']['server']['patches'].extend([
            {'patch': 'patches/c-create.patch', 'files': {'c': {
                'before': None,
                'after': hashlib.sha256(b'created\n').hexdigest()
            }}},
            {'patch': 'patches/c-update.patch', 'files': {'c': {
                'before': hashlib.sha256(b'created\n').hexdigest(),
                'after': hashlib.sha256(b'updated\n').hexdigest()
            }}}
        ])
        self.write_manifest()

        patches.run(self.root, 'apply')
        self.assertEqual((self.server / 'c').read_text(), 'updated\n')
        patches.run(self.root, 'revert')
        self.assertEqual(patches.git(self.server, 'status', '--porcelain'), '')


if __name__ == '__main__':
    unittest.main()
