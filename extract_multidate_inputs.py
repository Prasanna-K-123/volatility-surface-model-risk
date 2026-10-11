"""Extract the fixed source-clock selections without calculating variance."""
from __future__ import annotations
import argparse
from datetime import datetime, time
import gzip
import hashlib
import json
from pathlib import Path
import re
import libarchive

ARCHIVE_SHA='69bb91c9640376a9065b97b2b472bc60c11819b8ffba6c1d66ac66d9291ab9e2'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('archive',type=Path)
    args=parser.parse_args();root=Path(__file__).resolve().parent
    config=json.loads((root/'reference/multidate_shape/design.json').read_text())
    if hashlib.sha256(args.archive.read_bytes()).hexdigest()!=ARCHIVE_SHA:
        raise ValueError('Archive differs from registered authoritative hash')
    entries=[]
    with libarchive.file_reader(str(args.archive)) as archive:
        for entry in archive:
            m=re.fullmatch(r'deribit_data_(\d{8})-(\d{6})\.txt',str(entry.pathname))
            if not m:continue
            stamp=datetime.strptime(''.join(m.groups()),'%Y%m%d%H%M%S')
            if time(12)<=stamp.time()<time(12,15):
                entries.append((stamp,str(entry.pathname)))
    choices={}
    for day in config['days']:
        candidates=sorted((s,n) for s,n in entries if s.strftime('%Y-%m-%d')==day)
        choices[day]=candidates[0][1] if candidates else None
    selected={name:day for day,name in choices.items() if name}
    rows=[]
    with libarchive.file_reader(str(args.archive)) as archive:
        for entry in archive:
            if entry.pathname not in selected:continue
            raw=b''.join(entry.get_blocks());payload=json.loads(raw)
            if payload['date'] not in str(entry.pathname):raise ValueError('Source/member date mismatch')
            rows.append({'day':selected[entry.pathname],'member':str(entry.pathname),
                         'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'raw_utf8':raw.decode()})
    rows.sort(key=lambda r:r['day'])
    if len(rows)!=len(selected):raise ValueError('Selected source member missing')
    out=root/'reference/multidate_shape';out.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(rows,separators=(',',':')).encode()
    (out/'selected_snapshots.json.gz').write_bytes(gzip.compress(raw,mtime=0))
    receipt={'source_doi':'10.17632/hfd4b8zfw6.2','licence':'CC0-1.0',
             'archive_bytes':args.archive.stat().st_size,'archive_sha256':ARCHIVE_SHA,
             'target_days':config['days'],'selected_members':choices,
             'source_clock_window':'[12:00,12:15), timezone undocumented; explicit created GMT used separately',
             'selected_source_sha256':hashlib.sha256(raw).hexdigest(),
             'input_sha256':hashlib.sha256((out/'selected_snapshots.json.gz').read_bytes()).hexdigest(),
             'selected_member_proofs':[{k:v for k,v in r.items() if k!='raw_utf8'} for r in rows],
             'model_execution':False}
    (out/'source_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='selected_member_proofs'},indent=2))

if __name__=='__main__':main()
