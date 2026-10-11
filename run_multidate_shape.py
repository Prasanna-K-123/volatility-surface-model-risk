"""Execute the registered retrospective four-method shape comparison."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import gzip,hashlib,json,platform
from pathlib import Path
import numpy as np
import pandas as pd
import scipy
from vol_surface.svi import fit_svi,svi_total_variance
from vol_surface.density import svi_density_factor
from vol_surface.shape_models import (fit_joint_ssvi,fit_convex_call,ssvi_variance,
    ssvi_as_raw,normalized_call,call_to_variance)
from vol_surface.multidate_data import decode_snapshot,build_curves

ROOT=Path(__file__).resolve().parent
METHODS=['raw_svi','quadratic','convex_call','joint_ssvi']

def clean_json(value):
    if isinstance(value,dict):return {k:clean_json(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean_json(v) for v in value]
    if isinstance(value,np.generic):value=value.item()
    if isinstance(value,float) and not np.isfinite(value):return None
    return value

def write_json(path,value):path.write_text(json.dumps(clean_json(value),indent=2,allow_nan=False)+'\n')

def method_guard():
    lock=json.loads((ROOT/'reference/multidate_shape/method_manifest.json').read_text())
    for name,sha in lock['sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha:
            raise ValueError('Registered method hash changed: '+name)
    return lock

def fit_individual(curve,model,config):
    k,w=curve.k.to_numpy(),curve.total_variance.to_numpy()
    try:
        if model=='raw_svi':return fit_svi(k,w),{'success':True}
        if model=='quadratic':return np.polyfit(k,w,2),{'success':True}
        return fit_convex_call(k,w,config)
    except (ValueError,RuntimeError,FloatingPointError,np.linalg.LinAlgError) as exc:
        return None,{'success':False,'error_type':type(exc).__name__,'error':str(exc)}

def evaluate_variance(model,fit,k,expiry_index):
    if model=='raw_svi':return svi_total_variance(k,fit)
    if model=='quadratic':return np.polyval(fit,k)
    if model=='joint_ssvi':return ssvi_variance(k,fit.theta[expiry_index],fit.rho,fit.eta)
    calls=fit.call(k)
    return np.array([call_to_variance(float(a),float(c)) for a,c in zip(np.atleast_1d(k),np.atleast_1d(calls))])

def parameter_record(model,fit,curve,info,phase,index):
    row={'day':str(curve.day.iloc[0]),'expiry':str(curve.expiry.iloc[0]),'model':model,'phase':phase,
         'status':'ok' if fit is not None else 'fit_failed','solver':info,
         'T_years':float(curve.T_years.iloc[0]),'support_min':float(curve.k.min()),'support_max':float(curve.k.max())}
    if fit is None:return row
    if model=='raw_svi':row['params']=asdict(fit)
    elif model=='quadratic':row['coefficients']=fit.tolist()
    elif model=='convex_call':row.update(k=fit.k.tolist(),calls=fit.calls.tolist())
    else:row.update(theta=float(fit.theta[index]),rho=fit.rho,eta=fit.eta,certificate=fit.certificate())
    return row

def density_scan(model,fit,index,grid,tolerance):
    if model=='convex_call':
        return {'status':'discrete_convex_measure; smooth_g_not_applicable',
                'constraint_error':fit.constraint_error(),'grid_points':0}
    w=evaluate_variance(model,fit,grid,index)
    valid=np.isfinite(w)&(w>0);g=np.full(len(grid),np.nan)
    if model=='quadratic':
        wp=2*fit[0]*grid+fit[1];wpp=2*fit[0]
        a=grid[valid];b=w[valid];bp=wp[valid]
        g[valid]=(1-a*bp/(2*b))**2-bp**2/4*(1/b+.25)+wpp/2
    else:
        raw=fit if model=='raw_svi' else ssvi_as_raw(fit.theta[index],fit.rho,fit.eta)
        g=svi_density_factor(grid,raw)
    finite=np.isfinite(g);i=int(np.nanargmin(g)) if finite.any() else None
    return {'status':'diagnostic_only','grid_points':len(grid),'nonpositive_or_nonfinite_variance_points':int((~valid).sum()),
            'negative_density_points':int(np.sum(g < -tolerance)),
            'minimum_g':float(g[i]) if i is not None else None,'k_at_minimum_g':float(grid[i]) if i is not None else None}

def day_study(source,config,output):
    ledger,source_meta=decode_snapshot(source,config);curves,eligibility=build_curves(ledger,config)
    curves=sorted(curves,key=lambda c:c.T_years.iloc[0]);train=[c.iloc[::2].copy() for c in curves]
    test=[c.iloc[1::2].copy() for c in curves]
    predictions=[];parameters=[];shape=[];calendar=[];splits=[];phases={}
    for phase,parts in [('holdout',train),('full',curves)]:
        fits={m:[] for m in METHODS};info={m:[] for m in METHODS}
        for c in parts:
            for model in METHODS[:3]:
                fit,details=fit_individual(c,model,config);fits[model].append(fit);info[model].append(details)
        if parts:
            try:surface,attempts=fit_joint_ssvi(parts,config)
            except (ValueError,RuntimeError,FloatingPointError) as exc:surface,attempts=None,[{'success':False,'error':str(exc)}]
            fits['joint_ssvi']=[surface]*len(parts);info['joint_ssvi']=[{'success':surface is not None,'attempts':attempts}]*len(parts)
        for index,c in enumerate(parts):
            for model in METHODS:
                parameters.append(parameter_record(model,fits[model][index],c,info[model][index],phase,index))
        phases[phase]=fits
        if phase=='holdout':
            for index,(training,testing) in enumerate(zip(train,test)):
                lo,hi=float(training.k.min()),float(training.k.max())
                splits.append({'day':source['day'],'expiry':str(training.expiry.iloc[0]),'train_strikes':len(training),
                    'test_strikes':len(testing),'train_k_min':lo,'train_k_max':hi,
                    'interior_test_strikes':int(testing.k.between(lo,hi).sum()),
                    'boundary_test_strikes':int((~testing.k.between(lo,hi)).sum())})
                for row in testing.itertuples(index=False):
                    for model in METHODS:
                        record={'day':source['day'],'expiry':row.expiry,'strike':row.strike,'k':row.k,
                            'T_years':row.T_years,'true_variance':row.total_variance,
                            'true_iv':row.iv,'true_call':float(normalized_call(row.k,row.total_variance)),
                            'model':model,'domain':'interior' if lo<=row.k<=hi else 'boundary'}
                        fit=fits[model][index]
                        if fit is None:record['status']='fit_failed'
                        elif model=='convex_call' and record['domain']=='boundary':record['status']='unsupported_extrapolation'
                        else:
                            try:
                                pred=float(evaluate_variance(model,fit,np.array([row.k]),index)[0])
                                record['pred_variance']=pred
                                if not np.isfinite(pred) or pred<=0:record['status']='nonpositive_or_nonfinite_variance'
                                else:
                                    iv=float(np.sqrt(pred/row.T_years));call=float(normalized_call(row.k,pred))
                                    record.update(status='ok',pred_iv=iv,pred_call=call,
                                        variance_error=pred-row.total_variance,iv_error_pp=100*(iv-row.iv),
                                        call_error=call-record['true_call'])
                            except (ValueError,FloatingPointError) as exc:record.update(status='prediction_refused',error=str(exc))
                        predictions.append(record)
            # Persist recorded held-out predictions before any full refit.
            interim=output/'date_recordings'/source['day'];interim.mkdir(parents=True,exist_ok=True)
            pd.DataFrame(predictions).to_csv(interim/'heldout_predictions.csv',index=False)
            write_json(interim/'heldout_parameters.json',parameters)
        else:
            for index,c in enumerate(curves):
                for model in METHODS:
                    fit=fits[model][index]
                    for label,grid in [('observed',np.linspace(c.k.min(),c.k.max(),config['observed_grid_points'])),
                        ('stress',np.linspace(config['stress_k_min'],config['stress_k_max'],config['stress_grid_points']))]:
                        row={'day':source['day'],'expiry':str(c.expiry.iloc[0]),'model':model,'domain':label}
                        if fit is None:row['status']='fit_failed'
                        elif model=='convex_call' and label=='stress':row['status']='unsupported_extrapolation'
                        else:row.update(density_scan(model,fit,index,grid,config['negative_tolerance']))
                        shape.append(row)
            for index in range(max(0,len(curves)-1)):
                near,far=curves[index:index+2]
                lo,hi=max(near.k.min(),far.k.min()),min(near.k.max(),far.k.max())
                for model in METHODS:
                    left,right=fits[model][index:index+2]
                    for label,grid in [('common_observed',np.linspace(lo,hi,config['observed_grid_points'])),
                         ('stress',np.linspace(config['stress_k_min'],config['stress_k_max'],config['stress_grid_points']))]:
                        row={'day':source['day'],'near_expiry':str(near.expiry.iloc[0]),'far_expiry':str(far.expiry.iloc[0]),
                             'model':model,'domain':label,'common_k_min':float(lo),'common_k_max':float(hi)}
                        if left is None or right is None:row['status']='fit_failed'
                        elif label=='common_observed' and lo>=hi:row['status']='no_common_support'
                        elif model=='convex_call' and label=='stress':row['status']='unsupported_extrapolation'
                        else:
                            if model=='convex_call':
                                a,b=left.call(grid),right.call(grid);valid=np.ones(len(grid),bool);metric='normalized_call_increment'
                            else:
                                a=evaluate_variance(model,left,grid,index);b=evaluate_variance(model,right,grid,index+1)
                                valid=np.isfinite(a)&np.isfinite(b)&(a>0)&(b>0);metric='total_variance_increment'
                            diff=b-a
                            row.update(status='diagnostic_only',metric=metric,grid_points=len(grid),
                                invalid_variance_points=int((~valid).sum()),
                                negative_points=int(np.sum(valid&(diff < -config['negative_tolerance']))),
                                minimum_increment=float(np.min(diff[valid])) if valid.any() else None)
                        calendar.append(row)
    return {'ledger':ledger.to_dict('records'),'source_meta':source_meta,'eligibility':eligibility,
            'splits':splits,'predictions':predictions,'parameters':parameters,'shape':shape,'calendar':calendar}

def metric_rows(frame):
    rows=[]
    if frame.empty:return rows
    for (day,expiry,model,domain),part in frame.groupby(['day','expiry','model','domain'],sort=True):
        scored=part[part.status=='ok'];row={'day':day,'expiry':expiry,'model':model,'domain':domain,
            'n_expected':len(part),'n_scored':len(scored),'n_refused':len(part)-len(scored)}
        for column,label in [('variance_error','total_variance'),('iv_error_pp','iv_pp'),('call_error','normalized_call')]:
            v=scored[column].to_numpy() if column in scored else np.array([])
            row['rmse_'+label]=float(np.sqrt(np.mean(v*v))) if len(v) else None
            row['mae_'+label]=float(np.mean(np.abs(v))) if len(v) else None
        rows.append(row)
    return rows

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'results/multidate_shape')
    parser.add_argument('--workers',type=int,default=4);args=parser.parse_args()
    if not 1<=args.workers<=4:raise ValueError('Registered bounded workers 1..4')
    lock=method_guard();config=json.loads((ROOT/'reference/multidate_shape/design.json').read_text())
    args.output.mkdir(parents=True,exist_ok=True)
    path=ROOT/'reference/multidate_shape/selected_snapshots.json.gz'
    sources=json.loads(gzip.decompress(path.read_bytes()))
    receipt=json.loads((ROOT/'reference/multidate_shape/source_receipt.json').read_text())
    if hashlib.sha256(path.read_bytes()).hexdigest()!=receipt['input_sha256']:raise ValueError('Selected input changed')
    expected=[d for d in config['days'] if receipt['selected_members'][d] is not None]
    if [s['day'] for s in sources]!=expected:raise ValueError('Registered date accounting mismatch')
    if args.workers==1:results=[day_study(s,config,args.output) for s in sources]
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures=[pool.submit(day_study,s,config,args.output) for s in sources]
            results=[f.result() for f in futures]
    for key in ['ledger','eligibility','splits','predictions','shape','calendar']:
        rows=[r for result in results for r in result[key]]
        pd.DataFrame(rows).to_csv(args.output/(key+'.csv'),index=False)
    parameters=[p for result in results for p in result['parameters']]
    write_json(args.output/'parameters.json',parameters)
    source_meta=[r['source_meta'] for r in results]
    write_json(args.output/'source_observations.json',source_meta)
    predictions=pd.DataFrame([r for result in results for r in result['predictions']])
    metrics=metric_rows(predictions)
    interior=predictions[predictions.domain=='interior'] if not predictions.empty else predictions
    keys=['day','expiry','strike']
    if not interior.empty:
        counts=interior[interior.status=='ok'].groupby(keys).model.nunique()
        common=counts[counts==len(METHODS)].reset_index()[keys]
        paired=interior.merge(common,on=keys,how='inner');paired['domain']='common_interior'
        metrics+=metric_rows(paired)
    else:paired=interior
    metric_frame=pd.DataFrame(metrics);metric_frame.to_csv(args.output/'metrics.csv',index=False)
    aggregated=[]
    for (model,domain),part in metric_frame.groupby(['model','domain'],sort=True):
        aggregated.append({'model':model,'domain':domain,'date_expiry_groups':len(part),
            'scored_groups':int((part.n_scored>0).sum()),'n_expected':int(part.n_expected.sum()),
            'n_scored':int(part.n_scored.sum()),'n_refused':int(part.n_refused.sum()),
            'macro_mean_rmse_total_variance':float(part.rmse_total_variance.mean()),
            'macro_mean_rmse_iv_pp':float(part.rmse_iv_pp.mean()),
            'macro_mean_rmse_normalized_call':float(part.rmse_normalized_call.mean())})
    summary={'study':config['study'],'registered_days':len(config['days']),'observed_days':len(sources),
        'missing_days':[d for d in config['days'] if receipt['selected_members'][d] is None],
        'source_doi':config['source_doi'],'source_licence':'CC0-1.0','input_sha256':receipt['input_sha256'],
        'raw_option_rows':sum(r['input_rows'] for r in source_meta),
        'eligible_option_rows':sum(r['eligible_rows'] for r in source_meta),
        'eligible_date_expiries':sum(len(r['splits']) for r in results),
        'heldout_strikes':sum(r['test_strikes'] for result in results for r in result['splits']),
        'interior_strikes':sum(r['interior_test_strikes'] for result in results for r in result['splits']),
        'boundary_strikes':sum(r['boundary_test_strikes'] for result in results for r in result['splits']),
        'common_interior_strikes':int(len(paired)//len(METHODS)),
        'fit_records':len(parameters),'failed_fit_records':sum(p['status']!='ok' for p in parameters),
        'methods':METHODS,'aggregated_metrics':aggregated,
        'prediction_status_counts':predictions.groupby(['model','status']).size().reset_index(name='rows').to_dict('records'),
        'method_manifest_sha256':hashlib.sha256((ROOT/'reference/multidate_shape/method_manifest.json').read_bytes()).hexdigest(),
        'environment':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__},
        'scope':'Retrospective adjacent-day convenience archive; reconstructed variance under zero USD discount and recorded underlying convention; not venue mark-IV, forecasts, executable arbitrage or realized PnL',
        'theorem_scope':'SSVI mathematical sufficient conditions under idealized assumptions; observed market forwards/discounting/tails unverified',
        'uncertainty':'No independent-date inferential intervals or significance claims',
        'prior_results':'Original September 2026 calibration/density/27 hedge scenarios unchanged'}
    write_json(args.output/'summary.json',summary)
    print('MULTIDATE_STUDY_JSON='+json.dumps(clean_json(summary),separators=(',',':'),allow_nan=False))

if __name__=='__main__':main()
