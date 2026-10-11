"""Collect the registered CC0 archive; show structure, not model results."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import urllib.request
import libarchive

ROOT = Path('results/multidate_source_metadata')
META_URL = 'https://data.mendeley.com/public-api/datasets/hfd4b8zfw6/files?folder_id=root&version=2'
NAME = 'dump_deribit_09-18-dec-2018.rar'

def shape(value, depth=0):
    if depth >= 3:
        return type(value).__name__
    if isinstance(value, dict):
        return {key: shape(item, depth+1) for key, item in list(value.items())[:25]}
    if isinstance(value, list):
        return {'list_length': len(value), 'first_item_shape': shape(value[0], depth+1) if value else None}
    return type(value).__name__

def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(META_URL, headers={'User-Agent': 'academic-research-source-metadata/1.0'})
    with urllib.request.urlopen(request, timeout=30) as response:
        files = json.load(response)
    candidates = [f for f in files if f.get('filename') == NAME]
    if len(candidates) != 1:
        raise RuntimeError('Exact registered archive not uniquely present: '+json.dumps(files))
    metadata = candidates[0]
    url = metadata['content_details']['download_url']
    path = ROOT / NAME
    request = urllib.request.Request(url, headers={'User-Agent': 'academic-research-source-metadata/1.0'})
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read(50_000_001)
    if len(body) > 50_000_000:
        raise RuntimeError('Archive exceeds bounded registered-source collection')
    expected = metadata['content_details']['sha256_hash']
    if hashlib.sha256(body).hexdigest() != expected or len(body) != metadata['content_details']['size']:
        raise RuntimeError('Archive differs from authoritative size/hash')
    path.write_bytes(body)
    entries, previews = [], []
    with libarchive.file_reader(str(path)) as archive:
        for entry in archive:
            name = str(entry.pathname)
            entries.append({'name': name, 'bytes': entry.size, 'mtime': entry.mtime})
            if len(previews) < 2 and name.lower().endswith('.json'):
                data = b''.join(entry.get_blocks())
                previews.append({'name': name, 'structure': shape(json.loads(data))})
    proof = {'source_doi': '10.17632/hfd4b8zfw6.2', 'archive_name': NAME,
             'archive_bytes': len(body), 'archive_sha256': hashlib.sha256(body).hexdigest(),
             'returned_metadata': metadata, 'members': entries, 'schema_previews': previews,
             'model_execution': False}
    (ROOT/'archive_receipt.json').write_text(json.dumps(proof, indent=2)+'\n')
    print('MULTIDATE_ARCHIVE_STRUCTURE_JSON='+json.dumps({k:v for k,v in proof.items() if k!='members'}, separators=(',', ':')))
    print('MULTIDATE_MEMBER_NAMES_JSON='+json.dumps(entries[:30], separators=(',', ':')))
    print('MULTIDATE_ARCHIVE_MEMBERS='+str(len(entries)))

if __name__ == '__main__':
    main()
