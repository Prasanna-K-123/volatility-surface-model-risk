"""Read public archive metadata only; do not download observations or fit models."""
from __future__ import annotations
import json
import urllib.request
from pathlib import Path

URLS = [
    'https://data.mendeley.com/public-api/datasets/hfd4b8zfw6/versions/2',
    'https://data.mendeley.com/public-api/datasets/hfd4b8zfw6/files?version=2',
    'https://data.mendeley.com/public-api/datasets/hfd4b8zfw6/versions/2/files',
]

def main():
    rows = []
    for url in URLS:
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'academic-research-source-metadata/1.0'})
            with urllib.request.urlopen(request, timeout=30) as response:
                content = response.read(500_000).decode('utf-8')
                try:
                    value = json.loads(content)
                except json.JSONDecodeError:
                    value = {'non_json_excerpt': content[:2000]}
                rows.append({'url': url, 'status': response.status, 'metadata': value})
        except Exception as exc:
            rows.append({'url': url, 'error_type': type(exc).__name__, 'error': str(exc)})
    Path('results/multidate_source_metadata').mkdir(parents=True, exist_ok=True)
    Path('results/multidate_source_metadata/metadata.json').write_text(json.dumps(rows, indent=2)+'\n')
    print('MULTIDATE_SOURCE_METADATA_JSON='+json.dumps(rows, separators=(',', ':')))
    if not any(row.get('status') == 200 for row in rows):
        raise RuntimeError('No public source metadata resolved; no data downloaded')

if __name__ == '__main__':
    main()
