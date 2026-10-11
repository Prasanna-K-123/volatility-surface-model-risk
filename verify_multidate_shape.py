"""Audit every result row and compare a full replay with frozen evidence."""
from __future__ import annotations
import argparse
import gzip,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import ndtr
from run_multidate_shape import method_guard

ROOT=Path(__file__).resolve().parent
FILES=['ledger.csv','eligibility.csv','splits.csv','predictions.csv','shape.csv','calendar.csv','metrics.csv']

def black_call(k,w):
    root=np.sqrt(w);d1=-k/root+root/2
    return ndtr(d1)-np.exp(k)*ndtr(d1-root)

def expected_variance(record,k):
    model=record['model']
    if model=='raw_svi':
        p=record['params'];x=k-p['m']
        return p['a']+p['b']*(p['rho']*x+np.sqrt(x*x+p['sigma']**2))
    if model=='quadratic':return sum(c*k**(2-i) for i,c in enumerate(record['coefficients']))
    if model=='joint_ssvi':
        th,rho,eta=record['theta'],record['rho'],record['eta']
        phi=eta/np.sqrt(th*(1+th));z=phi*k
        return th/2*(1+rho*z+np.sqrt((z+rho)**2+1-rho*rho))
    return None

def audit(output):
    method_guard()
    frames={name:pd.read_csv(output/name) for name in FILES}
    summary=json.loads((output/'summary.json').read_text())
    params=json.loads((output/'parameters.json').read_text())
    sources=json.loads(gzip.decompress((ROOT/'reference/multidate_shape/selected_snapshots.json.gz').read_bytes()))
    receipt=json.loads((ROOT/'reference/multidate_shape/source_receipt.json').read_text())
    ledger=frames['ledger.csv'];pred=frames['predictions.csv'];splits=frames['splits.csv']
    raw_count=sum(len(json.loads(json.loads(s['raw_utf8'])['options'])) for s in sources)
    assert len(ledger)==raw_count==summary['raw_option_rows']
    assert summary['observed_days']==9 and summary['missing_days']==['2018-12-09']
    assert [s['day'] for s in sources]==receipt['target_days'][1:]
    assert not ledger[['day','source_row']].duplicated().any()
    raw_lookup={}
    for s in sources:
        data=json.loads(s['raw_utf8']);options=json.loads(data['options'])
        for identity,row in options.items():raw_lookup[(s['day'],str(identity))]=row
    inverse_rows=0
    for row in ledger.itertuples(index=False):
        raw=raw_lookup[(row.day,str(row.source_row))]
        digest=hashlib.sha256(json.dumps(raw,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        assert digest==row.row_sha256
        if np.isfinite(row.total_variance) if hasattr(row,'total_variance') else False:
            price=float(raw['markPrice'])*row.index_proxy_usd/float(raw['uPx'])
            if raw['instrumentName'].endswith('-P'):price+=1.-row.strike/row.underlying_usd
            recovered=float(black_call(row.k_row,row.total_variance))
            assert abs(recovered-price)<1e-10
            np.testing.assert_allclose(row.iv,np.sqrt(row.total_variance/row.T_years),rtol=1e-12,atol=1e-12)
            inverse_rows+=1
    assert int((ledger.status=='eligible').sum())==summary['eligible_option_rows']
    assert len(splits)==summary['eligible_date_expiries']
    assert int(splits.test_strikes.sum())==summary['heldout_strikes']
    assert len(pred)==4*summary['heldout_strikes']
    assert not pred[['day','expiry','strike','model']].duplicated().any()
    lookup={(p['day'],p['expiry'],p['model'],p['phase']):p for p in params}
    holdout_params=sum(p['phase']=='holdout' for p in params)
    assert holdout_params==4*len(splits) and len(params)==8*len(splits)
    checked_predictions=0
    for row in pred.itertuples(index=False):
        parameter=lookup[(row.day,row.expiry,row.model,'holdout')]
        inside=parameter['support_min']<=row.k<=parameter['support_max']
        assert row.domain==('interior' if inside else 'boundary')
        if row.model=='convex_call' and not inside:assert row.status=='unsupported_extrapolation'
        if row.status!='ok':continue
        expected=expected_variance(parameter,row.k)
        if row.model=='convex_call':
            call=np.interp(np.exp(row.k),np.exp(parameter['k']),parameter['calls'])
            assert abs(float(black_call(row.k,row.pred_variance))-call)<1e-10
        else:
            np.testing.assert_allclose(row.pred_variance,expected,rtol=1e-10,atol=1e-12)
        np.testing.assert_allclose(row.variance_error,row.pred_variance-row.true_variance,atol=1e-14)
        np.testing.assert_allclose(row.iv_error_pp,100*(np.sqrt(row.pred_variance/row.T_years)-row.true_iv),atol=1e-10)
        np.testing.assert_allclose(row.call_error,black_call(row.k,row.pred_variance)-row.true_call,atol=1e-12)
        checked_predictions+=1
    interior=pred[pred.domain=='interior']
    counts=interior[interior.status=='ok'].groupby(['day','expiry','strike']).model.nunique()
    common_keys=counts[counts==4].reset_index()[['day','expiry','strike']]
    common=interior.merge(common_keys,on=['day','expiry','strike'])
    assert len(common_keys)==summary['common_interior_strikes']
    for row in frames['metrics.csv'].itertuples(index=False):
        source=common if row.domain=='common_interior' else pred[pred.domain==row.domain]
        part=source[(source.day==row.day)&(source.expiry==row.expiry)&(source.model==row.model)]
        valid=part[part.status=='ok']
        assert len(part)==row.n_expected and len(valid)==row.n_scored
        assert row.n_refused==len(part)-len(valid)
        if len(valid):
            for field,metric in [('variance_error','total_variance'),('iv_error_pp','iv_pp'),('call_error','normalized_call')]:
                errors=valid[field].to_numpy()
                np.testing.assert_allclose(getattr(row,'rmse_'+metric),np.sqrt(np.mean(errors**2)),rtol=1e-10,atol=1e-12)
                np.testing.assert_allclose(getattr(row,'mae_'+metric),np.mean(np.abs(errors)),rtol=1e-10,atol=1e-12)
    # Verify theorem inequalities and bounded convex knot slopes for every fit.
    certificates=convex_certificates=0
    for p in params:
        if p['status']!='ok':continue
        if p['model']=='joint_ssvi':
            th,rho,eta=p['theta'],p['rho'],p['eta'];phi=eta/np.sqrt(th*(1+th))
            assert th>0 and eta*(1+abs(rho))<1.999
            assert th*phi*(1+abs(rho))<4 and th*phi**2*(1+abs(rho))<=4
            certificates+=1
        elif p['model']=='convex_call':
            x=np.exp(p['k']);c=np.array(p['calls']);slopes=np.diff(c)/np.diff(x)
            assert np.max(np.maximum(0,1-x)-c)<=1e-8 and np.max(c-1)<=1e-8
            assert np.max(slopes)<=1e-8 and np.min(slopes)>=-1-1e-8 and np.min(np.diff(slopes))>=-1e-8
            convex_certificates+=1
    return {'raw_rows_checked':raw_count,'inversion_residuals_checked':inverse_rows,
            'prediction_rows_accounted':len(pred),'successful_predictions_checked':checked_predictions,
            'metric_rows_checked':len(frames['metrics.csv']),'ssvi_certificates_checked':certificates,
            'convex_certificates_checked':convex_certificates,'all_registered_days_accounted':True,
            'full_nine_date_execution':True}

def compare(output,reference):
    # Predeclared numerical replay tolerance; all identities/status/counts exact.
    # Optimizer evaluations/weakly identified coordinates are not bit-identity promises.
    for name in FILES:
        actual,expected=pd.read_csv(output/name),pd.read_csv(reference/name)
        assert actual.columns.tolist()==expected.columns.tolist(),name
        assert actual.shape==expected.shape,name
        for column in actual.columns:
            a,b=actual[column],expected[column]
            if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
                discrete=(pd.api.types.is_bool_dtype(a) or column.endswith('_points') or column.startswith('n_')
                          or column in ['strike','source_row','source_options','distinct_strikes','train_strikes',
                              'test_strikes','interior_test_strikes','boundary_test_strikes','grid_points'])
                np.testing.assert_allclose(a.to_numpy(),b.to_numpy(),rtol=0 if discrete else 2e-4,
                                          atol=0 if discrete else 1e-8,equal_nan=True,err_msg=name+':'+column)
            else:assert a.fillna('<NA>').astype(str).tolist()==b.fillna('<NA>').astype(str).tolist(),name+':'+column
    a=json.loads((output/'summary.json').read_text());b=json.loads((reference/'summary.json').read_text())
    for key in ['registered_days','observed_days','missing_days','input_sha256','raw_option_rows',
        'eligible_option_rows','eligible_date_expiries','heldout_strikes','interior_strikes','boundary_strikes',
        'common_interior_strikes','fit_records','failed_fit_records','prediction_status_counts','method_manifest_sha256']:
        assert a[key]==b[key],key

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'results/multidate_shape')
    parser.add_argument('--reference',type=Path,default=ROOT/'reference/multidate_shape/results')
    args=parser.parse_args();proof=audit(args.output)
    if (args.reference/'summary.json').exists():compare(args.output,args.reference);proof['frozen_reference_equal']=True
    else:proof['frozen_reference_equal']=None;proof['reference_status']='SKIPPED: registration has no stored result yet'
    (args.output/'verification.json').write_text(json.dumps(proof,indent=2)+'\n')
    print('MULTIDATE_VERIFICATION_JSON='+json.dumps(proof,separators=(',',':')))

if __name__=='__main__':main()
