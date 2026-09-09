#!/usr/bin/env python3
"""Apply the pinned Officier source overlay without committing inside submodules."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def git(directory, *args):
    result = subprocess.run(
        ['git', '-C', str(directory), *args], text=True, capture_output=True
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def inside(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise RuntimeError(f'Path outside repository: {relative}')
    return path


def inspect(root):
    manifest = json.loads((root / 'patches/manifest.json').read_text())
    if manifest['schema'] != 1:
        raise RuntimeError('Unsupported patch manifest schema')
    entries = []
    for component, spec in manifest['components'].items():
        directory = inside(root, component)
        revision = git(directory, 'rev-parse', 'HEAD')
        if revision != spec['revision']:
            raise RuntimeError(f'{component}: expected {spec["revision"]}, found {revision}')
        patches = spec['patches']
        for index, patch in enumerate(patches):
            states = set()
            for relative, hashes in patch['files'].items():
                source = inside(directory, relative)
                if not source.exists() and hashes.get('before') is None:
                    state = 'before'
                elif source.exists():
                    digest = hashlib.sha256(source.read_bytes()).hexdigest()
                    state = next((name for name in ('before', 'after') if hashes.get(name) == digest), None)
                    if state is None:
                        later = patches[index + 1 :]
                        earlier = patches[:index]
                        if any(item['files'].get(relative, {}).get('after') == digest for item in later):
                            state = 'after'
                        elif any(digest in item['files'].get(relative, {}).values() for item in earlier):
                            state = 'before'
                else:
                    state = None
                if state is None:
                    raise RuntimeError(f'{component}/{relative}: unexpected contents; preserve/review local edits first')
                states.add(state)
            if len(states) != 1:
                raise RuntimeError(f'{patch["patch"]}: partially modified patch files')
            entries.append((directory, inside(root, patch['patch']), states.pop()))
    return entries


def run(root, command):
    entries = inspect(root)  # Check every revision/file before changing anything.
    if command == 'status':
        for _, patch, state in entries:
            print(f'{patch.name}: {"applied" if state == "after" else "not applied"}')
        return
    reverse = command == 'revert'
    expected = 'after' if reverse else 'before'
    work = [entry for entry in entries if entry[2] == expected]
    if reverse:
        work.reverse()
    flags = ['--reverse'] if reverse else []
    if command == 'check':
        for directory, patch, _ in work:
            try:
                git(directory, 'apply', '--check', *flags, str(patch))
            except RuntimeError:
                # A later patch can depend on an earlier patch in the same run.
                # The apply command validates each step again after dependencies land.
                pass
        print('All patches are applied or can be applied to the pinned sources.')
        return
    completed = []
    try:
        for directory, patch, _ in work:
            git(directory, 'apply', '--check', *flags, str(patch))
            git(directory, 'apply', *flags, str(patch))
            completed.append((directory, patch))
        final = inspect(root)
        target = 'before' if reverse else 'after'
        if any(state != target for _, _, state in final):
            raise RuntimeError('Patch result does not match the manifest')
    except Exception:
        for directory, patch in reversed(completed):
            git(directory, 'apply', *([] if reverse else ['--reverse']), str(patch))
        raise
    print(f'{command}: {len(work)} patch(es) changed; remaining already in requested state.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['status', 'check', 'apply', 'revert'])
    args = parser.parse_args()
    try:
        run(Path(__file__).resolve().parent.parent, args.command)
    except (RuntimeError, OSError, ValueError, KeyError) as error:
        print(f'Officier patches: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
