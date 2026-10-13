"""Probe official AOI-selected Hessen ZIP URLs without downloading the packages."""
import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dtm.runtime import bootstrap


def main():
    from dtm.coordinator import load_config
    from dtm.geo import read_aoi
    from dtm.countries.germany import hessen
    from dtm.countries.germany.hessen.acquisition import package_url
    import requests

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', nargs='?', default='config.germany.hessen.json')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--limit', type=int, help='Probe only the first N planned districts.')
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error('--limit must be positive')
    config = load_config(args.config)
    geometry, _, _ = read_aoi(config['aoi'], config['layer'])
    plan = hessen.plan(geometry, config)
    checks = []
    with requests.Session() as session:
        session.headers['User-Agent'] = 'repeatable-dtm-comparison/1.0'
        for region in plan['regions'][:args.limit]:
            url = package_url(config['source'], region)
            record = {'district': region, 'url': url}
            try:
                with session.get(url, headers={'Range': 'bytes=0-3', 'Accept-Encoding': 'identity'},
                                 stream=True, timeout=(30, 30)) as response:
                    response.raise_for_status()
                    record['http_status'] = response.status_code
                    content_range = response.headers.get('Content-Range', '')
                    match = re.fullmatch(r'bytes 0-3/(\d+)', content_range)
                    if response.status_code != 206 or not match:
                        raise ValueError(f'Expected a four-byte partial ZIP response, got {content_range!r}')
                    record['archive_bytes'] = int(match[1])
                    signature = response.raw.read(4)
                    if signature != b'PK\x03\x04':
                        raise ValueError(f'Unexpected ZIP signature: {signature!r}')
                    record['passed'] = True
            except Exception as exc:
                record.update(passed=False, error=f'{type(exc).__name__}: {exc}')
            checks.append(record)
    result = {'source': 'Official Hessen Geodaten online', 'download_date': config['source']['download_date'],
              'planned_district_count': len(plan['regions']), 'checks': checks,
              'passed': all(c['passed'] for c in checks),
              'limitations': 'ZIP signature and range availability only; full downloads, CRC and raster validation occur during acquisition.'}
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered+'\n', encoding='utf-8')
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    bootstrap(__file__, 'config.germany.hessen.json')
    main()
