"""One-time, repeatable migration; preserve old runs and copy verified raw TIFFs.

Run from either Windows or WSL: python scripts/migrate_data_layout.py
No downloads, GDAL dependency, processing or deletion of historical runs.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dtm.paths import scoped_root, raw_directory, receipt_path

def relocate_references(value, replacements):
    if isinstance(value, str):
        for old, new in replacements:
            value = value.replace(str(old), str(new)).replace(old.as_posix(), new.as_posix())
        return value
    if isinstance(value, list):
        return [relocate_references(item, replacements) for item in value]
    if isinstance(value, dict):
        return {key: relocate_references(item, replacements) for key, item in value.items()}
    return value


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + '.tmp')
    part.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    part.replace(path)


def move(source, destination):
    source, destination = source.resolve(), destination.resolve()
    if not source.is_relative_to(ROOT) or not destination.is_relative_to(ROOT) or source == ROOT:
        raise ValueError(f'Move must stay inside the workspace: {source} -> {destination}')
    if source.is_relative_to(destination) or destination.is_relative_to(source):
        raise ValueError('Overlapping move paths.')
    if destination.exists():
        raise FileExistsError(f'Refusing to replace existing archive: {destination}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.rename(destination)


def repair(root, replacements):
    for path in root.rglob('*'):
        if path.suffix == '.json':
            value = json.loads(path.read_text(encoding='utf-8-sig'))
            changed = relocate_references(value, replacements)
            if value != changed:
                save(path, changed)
        elif path.suffix in ('.vrt', '.txt'):
            value = path.read_text(encoding='utf-8-sig')
            changed = relocate_references(value, replacements)
            if value != changed:
                path.write_text(changed, encoding='utf-8')


def remove_empty_containers():
    for root in (ROOT / 'data/prepared', ROOT / 'data/pilots'):
        if not root.exists():
            continue
        paths = sorted(root.rglob('*'), key=lambda p: len(p.parts), reverse=True) + [root]
        for path in paths:
            if path.is_dir() and not any(path.iterdir()):
                # OneDrive can preserve the DOS read-only bit on empty folders.
                if os.name == 'nt':
                    path.chmod(stat.S_IWRITE)
                path.rmdir()


def main():
    report = {'copied': [], 'reused': 0, 'skipped': [], 'moved': []}
    for config_path in sorted(ROOT.glob('config.*.json')):
        config = json.loads(config_path.read_text(encoding='utf-8-sig'))
        for key in ('cache_root', 'output_root', 'old_runs_root', 'logs_dir'):
            config[key] = str((ROOT / config[key]).resolve())
        scope = scoped_root(config, 'output_root')
        old = scoped_root(config, 'old_runs_root')
        logs = scoped_root(config, 'logs_dir')
        raw = raw_directory(config)
        for folder in (raw, logs / 'raw_receipts'):
            folder.mkdir(parents=True, exist_ok=True)
        prepared = ROOT / 'data' / 'prepared' / config['country']
        if config.get('region'):
            prepared /= config['region']
        if prepared.exists():
            for source in sorted(prepared.iterdir()):
                destination = old / source.name
                move(source, destination)
                report['moved'].append({'from': str(source), 'to': str(destination)})
        # Repair project-local references after moving the old run trees.
        replacements = [(prepared, old)]
        repair(old, replacements)
        latest = old / 'latest_run.json'
        if latest.exists() and not (logs / 'latest_run.json').exists():
            save(logs / 'latest_run.json', json.loads(latest.read_text(encoding='utf-8-sig')))
        # This is the only legacy discovery pass; runtime cache lookup is raw_tiles only.
        pilot = ROOT / 'data' / 'pilots' / config['country']
        if config.get('region'):
            pilot /= config['region']
        candidates = [p for base in (old, pilot) for p in base.rglob('*.tif')
                      if any(part.startswith('raw_') for part in p.relative_to(base).parts)]
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for source in candidates:
            sidecar = source.with_suffix('.json')
            if not sidecar.exists():
                report['skipped'].append({'path': str(source), 'reason': 'No provenance receipt'})
                continue
            record = json.loads(sidecar.read_text(encoding='utf-8-sig'))
            if record.get('sha256') != digest(source):
                report['skipped'].append({'path': str(source), 'reason': 'Checksum mismatch'})
                continue
            target = raw / source.name
            receipt = receipt_path(target, config)
            if target.exists():
                if digest(target) == record['sha256']:
                    if not receipt.exists():
                        save(receipt, record)
                    report['reused'] += 1
                else:
                    report['skipped'].append({'path': str(source), 'reason': 'Different same-name TIFF already cached'})
                continue
            staging = logs / 'download_work' / (source.name + '.migration')
            staging.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, staging)
            if digest(staging) != record['sha256']:
                raise ValueError(f'Copied TIFF checksum mismatch: {source}')
            staging.replace(target)
            save(receipt, record)
            report['copied'].append(str(target))
        # Move the old log-based package cache beside the regional raw cache.
        archive = logs / 'source_archive'
        if archive.exists():
            target = scoped_root(config, 'cache_root') / 'source_archive'
            move(archive, target)
            report['moved'].append({'from': str(archive), 'to': str(target)})
        replacements.append((archive, scoped_root(config, 'cache_root') / 'source_archive'))
        if pilot.exists():
            destination = old / 'pilots'
            move(pilot, destination)
            report['moved'].append({'from': str(pilot), 'to': str(destination)})
            replacements.append((pilot, destination))
        if config['country'] == 'netherlands':
            source = ROOT / 'data/pilots/hole_filling'
            if source.exists():
                destination = old / 'pilots/hole_filling'
                move(source, destination)
                report['moved'].append({'from': str(source), 'to': str(destination)})
                replacements.append((source, destination))
        repair(old, replacements)
        repair(logs, replacements)
        print(f"Migrated {config['country']}/{config.get('region', '')}: {len(list(raw.glob('*.tif')))} raw TIFFs", flush=True)
    save(ROOT / 'logs' / 'data_layout_migration.json', report)
    # Remove only empty legacy containers, never recursive deletion.
    remove_empty_containers()
    print(f"Copied {len(report['copied'])}; reused {report['reused']}; skipped {len(report['skipped'])}. See logs/data_layout_migration.json")


if __name__ == '__main__':
    main()
