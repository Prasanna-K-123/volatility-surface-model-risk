import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from vol_surface.shape_models import (SSVISurface, ssvi_variance, ssvi_as_raw,
    fit_joint_ssvi, fit_convex_call, ConvexCallSlice, normalized_call, call_to_variance)
from vol_surface.svi import svi_total_variance
from vol_surface.density import svi_density_factor

CONFIG = json.loads((Path(__file__).parents[1]/'reference/multidate_shape/design.json').read_text())


@pytest.mark.parametrize('rho',[-.9,-.4,0.,.4,.9])
def test_ssvi_formula_raw_equivalence_density_and_global_bounds(rho):
    eta = 1.998/(1+abs(rho))
    for theta in [1e-5,.01,.1,1.,100.]:
        k = np.linspace(-10.,10.,2001)
        w = ssvi_variance(k,theta,rho,eta)
        raw = ssvi_as_raw(theta,rho,eta)
        np.testing.assert_allclose(w,svi_total_variance(k,raw),rtol=1e-10,atol=1e-12)
        assert np.min(svi_density_factor(k,raw)) >= -1e-10
        phi = eta/np.sqrt(theta*(1+theta))
        assert theta*phi*(1+abs(rho)) < 4
        assert theta*phi**2*(1+abs(rho)) <= 4
        # Analytic derivative ratio checked against a separate finite difference.
        eps = theta*1e-5
        value = lambda x: x*eta/np.sqrt(x*(1+x))
        derivative = (value(theta+eps)-value(theta-eps))/(2*eps)
        np.testing.assert_allclose(derivative/phi,1/(2*(1+theta)),rtol=1e-7)


def make_surface():
    return SSVISurface(np.array([.1,.3,.5]),np.array([.02,.07,.12]),-.3,.9,
                       np.array([-.4,-.3,-.2]),np.array([.3,.4,.3]))


def test_ssvi_monotone_calendar_and_bounded_interpolation():
    surface = make_surface(); k = np.linspace(-3,3,1001)
    values = [ssvi_variance(k,surface.theta_at(t),surface.rho,surface.eta) for t in np.linspace(.1,.5,41)]
    assert np.min(np.diff(values,axis=0)) > 0
    assert surface.theta_at(.2) == pytest.approx(.045)
    assert surface.supported_variance(np.array([-.3,.3]),.2).shape == (2,)
    with pytest.raises(ValueError,match='strike'): surface.supported_variance(np.array([-.300001]),.2)
    with pytest.raises(ValueError,match='maturity'): surface.theta_at(.500001)
    with pytest.raises(ValueError,match='maturity'): surface.theta_at(.099999)
    with pytest.raises(ValueError): surface.supported_variance(np.array([np.nan]),.2)
    assert not surface.theta.flags.writeable


@pytest.mark.parametrize('problem',['theta','rho','eta','times','support'])
def test_ssvi_bad_certificates_refused(problem):
    data=dict(maturities=np.array([.1,.2]),theta=np.array([.02,.03]),rho=0.,eta=1.,
              support_min=np.array([-.3,-.3]),support_max=np.array([.3,.3]))
    if problem=='theta':data['theta']=np.array([.03,.02])
    if problem=='rho':data['rho']=.999
    if problem=='eta':data['eta']=1.999
    if problem=='times':data['maturities']=np.array([.2,.1])
    if problem=='support':data['support_min']=np.array([.4,-.3])
    with pytest.raises(ValueError):SSVISurface(**data)


def test_joint_fit_recovers_controlled_surface_without_test_data():
    k=np.linspace(-.4,.4,21);curves=[]
    for t,th in [(.1,.02),(.3,.07),(.5,.12)]:
        curves.append(pd.DataFrame(dict(k=k,total_variance=ssvi_variance(k,th,-.3,.9),T_years=t)))
    surface,attempts=fit_joint_ssvi(curves,CONFIG)
    assert surface is not None and len(attempts)==3
    for c in curves:
        pred=surface.supported_variance(c.k.to_numpy(),c.T_years.iloc[0])
        np.testing.assert_allclose(pred,c.total_variance,rtol=1e-6,atol=1e-9)


@pytest.mark.parametrize('k',[-.6,-.2,0.,.2,.6])
def test_call_variance_inverse_and_independent_put_call_bounds(k):
    for w in [.02,.05,.2,1.]:
        c=float(normalized_call(k,w))
        assert max(0,1-np.exp(k)) < c < 1
        assert call_to_variance(k,c)==pytest.approx(w,rel=1e-9,abs=1e-11)
    with pytest.raises(ValueError):call_to_variance(k,1.)
    with pytest.raises(ValueError):call_to_variance(k,max(0.,1-np.exp(k)))


def test_convex_call_preserves_valid_training_and_is_bounded():
    k=np.linspace(-.4,.4,17);w=np.full(17,.07)
    fit,info=fit_convex_call(k,w,CONFIG)
    assert fit is not None and info['success'] and info['constraint_error']<=1e-8
    np.testing.assert_allclose(fit.calls,normalized_call(k,w),atol=1e-6)
    np.testing.assert_allclose(fit.call(k),fit.calls,atol=1e-14)
    slopes=np.diff(fit.calls)/np.diff(np.exp(k))
    assert (slopes>=-1-1e-8).all() and (slopes<=1e-8).all() and (np.diff(slopes)>=-1e-8).all()
    with pytest.raises(ValueError,match='extrapolation'):fit.call(np.array([-.400001]))
    with pytest.raises(ValueError,match='extrapolation'):fit.call(np.array([.400001]))


def test_convex_fit_repairs_nonconvex_marks_and_retains_adjustment():
    k=np.linspace(-.3,.3,15);w=np.full(15,.05);w[7]=.5
    fit,info=fit_convex_call(k,w,CONFIG)
    assert fit is not None and info['mark_call_adjustment_rmse']>0
    assert fit.constraint_error()<=1e-8
    for left,right in zip(np.exp(k[:-1]),np.exp(k[1:])):
        mid=(left+right)/2
        i=np.searchsorted(np.exp(k),mid)-1
        assert fit.call(np.log(mid))==pytest.approx((fit.calls[i]+fit.calls[i+1])/2)


def test_invalid_variance_and_invalid_convex_knots_are_not_clipped():
    with pytest.raises(ValueError):normalized_call(np.array([0.]),np.array([-1.]))
    with pytest.raises(ValueError):ConvexCallSlice(np.array([-.2,0.,.2]),np.array([.1,.8,.1]))
    with pytest.raises(ValueError):fit_convex_call(np.array([0.,0.,.2]),np.array([.02]*3),CONFIG)
    with pytest.raises(ValueError):fit_joint_ssvi([],CONFIG)
