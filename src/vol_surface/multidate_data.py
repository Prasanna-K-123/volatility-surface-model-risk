"""Auditable conversion of CC0 historical BTC marks under a stated convention."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import re
import numpy as np
import pandas as pd
from .shape_models import call_to_variance, normalized_call

INSTRUMENT=re.compile(r'BTC-(\d{1,2}[A-Z]{3}\d{2})-(\d+(?:\.\d+)?)-([CP])')

def number(value):
    try:return float(value)
    except (ValueError,TypeError):return float('nan')

def decode_snapshot(source, config):
    raw=source['raw_utf8'].encode()
    if hashlib.sha256(raw).hexdigest()!=source['sha256'] or len(raw)!=source['bytes']:
        raise ValueError('Selected raw member hash/size mismatch')
    payload=json.loads(raw)
    options=json.loads(payload['options']);futures=json.loads(payload['futures'])
    if not isinstance(options,dict) or not isinstance(futures,dict):
        raise ValueError('Registered historical record shape changed')
    index_values=np.array([number(r.get('estDelPrice')) for r in futures.values()])
    index_values=index_values[np.isfinite(index_values)&(index_values>0)]
    if not len(index_values):raise ValueError('Missing positive historical index proxy')
    index=float(np.median(index_values));ledger=[]
    for identity,row in sorted(options.items(),key=lambda kv:int(kv[0])):
        record={'day':source['day'],'member':source['member'],'source_row':identity,
                'instrument':row.get('instrumentName'),
                'row_sha256':hashlib.sha256(json.dumps(row,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                'underlying_index':row.get('uIx'), 'mark_btc':number(row.get('markPrice')),
                'underlying_usd':number(row.get('uPx')),'index_proxy_usd':index,
                'recorded_interest_rate':number(row.get('iR')),'discount_rate_assumption':0.,
                'bid_btc':number(row.get('bidPrice')),'ask_btc':number(row.get('askPrice')),
                'open_interest':number(row.get('openInterest')),
                'iv_source':'reconstructed Black-forward variance under zero USD discount rate',
                'negative_bid_or_ask':bool(number(row.get('bidPrice'))<0 or number(row.get('askPrice'))<0),
                'crossed_quotes':bool(number(row.get('bidPrice'))>number(row.get('askPrice')))}
        try:
            match=INSTRUMENT.fullmatch(row['instrumentName'])
            if match is None:raise ValueError('Unrecognized BTC option identifier')
            expiry=datetime.strptime(match[1],'%d%b%y').replace(hour=8,tzinfo=timezone.utc)
            created=datetime.strptime(row['created'],'%Y-%m-%d %H:%M:%S GMT').replace(tzinfo=timezone.utc)
            strike=float(match[2]);underlying=record['underlying_usd']
            T=(expiry-created).total_seconds()/(365.25*86400)
            k=float(np.log(strike/underlying)) if strike>0 and underlying>0 else float('nan')
            record.update(created_summary_utc=created.isoformat(),expiry=expiry.isoformat(),
                option_type='call' if match[3]=='C' else 'put',strike=strike,T_years=T,dte=T*365.25,k_row=k,
                underlying_matches_expiry=bool(row.get('uIx')=='BTC-'+match[1]),
                recorded_nonzero_interest=bool(np.isfinite(record['recorded_interest_rate']) and record['recorded_interest_rate']!=0))
            reasons=[]
            if not (config['min_dte']<=record['dte']<=config['max_dte']):reasons.append('outside_dte')
            if not np.isfinite([strike,underlying,k]).all() or strike<=0 or underlying<=0:reasons.append('invalid_strike_underlying')
            elif abs(k)>config['abs_k_max']:reasons.append('outside_moneyness')
            if not np.isfinite([record['bid_btc'],record['ask_btc']]).all():reasons.append('missing_quotes')
            if not np.isfinite(record['open_interest']) or record['open_interest']<0:reasons.append('invalid_open_interest')
            if not np.isfinite(record['mark_btc']) or record['mark_btc']<=0:reasons.append('invalid_mark')
            if not reasons:
                normalized=record['mark_btc']*index/underlying
                equivalent=normalized if match[3]=='C' else normalized+1.-strike/underlying
                record.update(normalized_original_premium=normalized,call_equivalent=equivalent)
                try:
                    w=call_to_variance(k,equivalent);iv=float(np.sqrt(w/T))
                    record.update(total_variance=w,iv=iv,
                                  inversion_call_residual=float(normalized_call(k,w))-equivalent)
                    if not (config['iv_decimal_min']<=iv<=config['iv_decimal_max']):reasons.append('outside_derived_iv')
                except ValueError as exc:
                    reasons.append('inversion_refused');record['inversion_error']=str(exc)
            record['status']='eligible' if not reasons else ';'.join(reasons)
        except (ValueError,KeyError,OverflowError) as exc:
            record.update(status='source_schema_refused',error=str(exc))
        ledger.append(record)
    frame=pd.DataFrame(ledger)
    return frame, {'day':source['day'],'member':source['member'],'input_rows':len(frame),
                   'eligible_rows':int((frame.status=='eligible').sum()),'index_proxy_usd':index,
                   'index_proxy_relative_range':float(np.ptp(index_values)/index),
                   'created_summary_min':str(frame.get('created_summary_utc',pd.Series(dtype=str)).min()),
                   'created_summary_max':str(frame.get('created_summary_utc',pd.Series(dtype=str)).max()),
                   'filename_date_time':payload['date'],'filename_timezone':'undocumented',
                   'mark_iv_field_present':any('markIv' in r or 'mark_iv' in r for r in options.values()),
                   'negative_quote_rows':int(frame.negative_bid_or_ask.sum()),'crossed_quote_rows':int(frame.crossed_quotes.sum())}

def build_curves(ledger,config):
    eligible=ledger[ledger.status=='eligible'].copy();curves=[];expiry_rows=[]
    for expiry,part in eligible.groupby('expiry',sort=True):
        underlying=float(part.underlying_usd.median())
        curve=part.groupby('strike',as_index=False).agg(total_variance=('total_variance','mean'),
            T_years=('T_years','median'),n_source_options=('instrument','size'),
            mean_row_k=('k_row','mean')).sort_values('strike').reset_index(drop=True)
        curve['k']=np.log(curve.strike/underlying);curve['underlying_usd']=underlying
        curve['expiry']=expiry;curve['day']=part.day.iloc[0]
        curve['iv']=np.sqrt(curve.total_variance/curve.T_years)
        row={'day':part.day.iloc[0],'expiry':expiry,'source_options':len(part),'distinct_strikes':len(curve),
             'T_years':float(curve.T_years.median()),'underlying_usd':underlying,
             'underlying_relative_range':float(np.ptp(part.underlying_usd)/underlying),
             'underlying_reference_mismatch_options':int((~part.underlying_matches_expiry).sum()),
             'status':'eligible' if len(curve)>=config['min_strikes'] else 'insufficient_distinct_strikes'}
        expiry_rows.append(row)
        if row['status']=='eligible':curves.append(curve)
    return curves,expiry_rows
