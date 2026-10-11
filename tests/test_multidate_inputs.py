from pathlib import Path
import gzip,hashlib,json
import numpy as np
import pytest
from scipy.special import ndtr
from vol_surface.multidate_data import decode_snapshot,build_curves

ROOT=Path(__file__).parents[1]
CONFIG=json.loads((ROOT/'reference/multidate_shape/design.json').read_text())

def test_selected_raw_bytes_and_missing_date_are_preserved():
    receipt=json.loads((ROOT/'reference/multidate_shape/source_receipt.json').read_text())
    path=ROOT/'reference/multidate_shape/selected_snapshots.json.gz'
    assert hashlib.sha256(path.read_bytes()).hexdigest()==receipt['input_sha256']
    body=gzip.decompress(path.read_bytes());assert hashlib.sha256(body).hexdigest()==receipt['selected_source_sha256']
    rows=json.loads(body);assert len(rows)==9
    assert receipt['selected_members']['2018-12-09'] is None
    assert [r['day'] for r in rows]==CONFIG['days'][1:]
    for row in rows:
        raw=row['raw_utf8'].encode();assert hashlib.sha256(raw).hexdigest()==row['sha256']
        assert len(raw)==row['bytes']
        date=json.loads(raw)['date'];assert date in row['member']
        assert '1200' in date or date=='20181218-120504'

def synthetic_source(premium):
    option=dict(instrumentName='BTC-28DEC18-100-C',openInterest=0,bidPrice=.01,askPrice=.05,
        markPrice=premium,uPx=100.,uIx='BTC-28DEC18',iR=0,created='2018-12-10 11:00:03 GMT')
    payload=dict(date='20181210-120003',options=json.dumps({'0':option}),
        futures=json.dumps({'0':dict(estDelPrice=100.)}),libor=[])
    raw=json.dumps(payload).encode()
    return dict(day='2018-12-10',member='deribit_data_20181210-120003.txt',bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest(),raw_utf8=raw.decode())

def test_atm_price_inversion_known_variance_and_explicit_gmt():
    # Independent ATM Black formula: C/F=2*Phi(sqrt(w)/2)-1.
    w=.02;premium=2*ndtr(np.sqrt(w)/2)-1
    ledger,meta=decode_snapshot(synthetic_source(premium),CONFIG)
    assert ledger.status.iloc[0]=='eligible'
    assert ledger.total_variance.iloc[0]==pytest.approx(w,abs=1e-11)
    assert ledger.created_summary_utc.iloc[0]=='2018-12-10T11:00:03+00:00'
    assert meta['filename_timezone']=='undocumented'
    assert not meta['mark_iv_field_present']
    curves,expiry=build_curves(ledger,CONFIG)
    assert not curves and expiry[0]['status']=='insufficient_distinct_strikes'

@pytest.mark.parametrize('premium',[0.,-1.,1.,float('nan')])
def test_invalid_premium_is_recorded_and_never_clipped(premium):
    ledger,_=decode_snapshot(synthetic_source(premium),CONFIG)
    assert ledger.status.iloc[0]!='eligible'

def test_source_hash_refusal_precedes_any_conversion():
    source=synthetic_source(.01);source['sha256']='0'*64
    with pytest.raises(ValueError,match='hash'):decode_snapshot(source,CONFIG)
