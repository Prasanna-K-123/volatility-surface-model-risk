"""Registered SSVI and bounded convex-call alternatives.

Mathematical shape conditions do not verify executable market quotes or tails.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from scipy.optimize import least_squares, minimize, LinearConstraint, Bounds, brentq
from scipy.special import expit, ndtr
from .svi import SVIParams


def normalized_call(k, w):
    k, w = np.broadcast_arrays(np.asarray(k, float), np.asarray(w, float))
    if not np.isfinite(k).all() or not np.isfinite(w).all() or np.any(w <= 0):
        raise ValueError('Finite k and strictly positive variance required')
    root = np.sqrt(w)
    d1 = -k/root + root/2
    return ndtr(d1) - np.exp(k)*ndtr(d1-root)


def call_to_variance(k: float, call: float) -> float:
    if not np.isfinite([k, call]).all():
        raise ValueError('Finite call and moneyness required')
    lower = max(0., 1.-np.exp(k))
    if not lower < call < 1.:
        raise ValueError('Call has no finite strictly positive implied variance')
    fn = lambda w: float(normalized_call(k, w))-call
    if fn(1e-12) >= 0 or fn(100.) <= 0:
        raise ValueError('Variance inversion outside registered [1e-12,100] bracket')
    return float(brentq(fn, 1e-12, 100., xtol=1e-14))


def ssvi_variance(k, theta, rho, eta):
    k, theta = np.broadcast_arrays(np.asarray(k, float), np.asarray(theta, float))
    if (not np.isfinite(k).all() or not np.isfinite(theta).all() or
            np.any(theta <= 0) or not np.isfinite([rho, eta]).all() or
            abs(rho) >= 1 or eta <= 0):
        raise ValueError('Invalid SSVI arguments')
    phi = eta/np.sqrt(theta*(1.+theta))
    z = phi*k
    return theta/2.*(1.+rho*z+np.hypot(z+rho, np.sqrt(1.-rho*rho)))


def ssvi_as_raw(theta: float, rho: float, eta: float) -> SVIParams:
    # Exact algebraic conversion permits reuse of the independent raw-SVI g(k).
    ssvi_variance(np.array([0.]), theta, rho, eta)
    phi = eta/np.sqrt(theta*(1.+theta))
    return SVIParams(theta*(1.-rho*rho)/2., theta*phi/2., rho,
                     -rho/phi, np.sqrt(1.-rho*rho)/phi)


@dataclass(frozen=True)
class SSVISurface:
    maturities: np.ndarray
    theta: np.ndarray
    rho: float
    eta: float
    support_min: np.ndarray
    support_max: np.ndarray

    def __post_init__(self):
        for name in ('maturities', 'theta', 'support_min', 'support_max'):
            arr = np.array(getattr(self, name), dtype=float, copy=True)
            arr.setflags(write=False)
            object.__setattr__(self, name, arr)
        n = len(self.theta)
        if (n < 1 or any(x.shape != (n,) for x in
                       (self.maturities,self.theta,self.support_min,self.support_max)) or
            not all(np.isfinite(x).all() for x in
                    (self.maturities,self.theta,self.support_min,self.support_max)) or
            np.any(self.maturities <= 0) or np.any(np.diff(self.maturities) <= 0) or
            np.any(self.theta <= 0) or np.any(np.diff(self.theta) < 0) or
            np.any(self.support_min >= self.support_max) or
            not np.isfinite([self.rho,self.eta]).all() or abs(self.rho) >= .999 or
            self.eta <= 0 or self.eta*(1+abs(self.rho)) >= 1.999):
            raise ValueError('Invalid constrained SSVI surface')

    def theta_at(self, maturity: float) -> float:
        if not np.isfinite(maturity) or maturity < self.maturities[0] or maturity > self.maturities[-1]:
            raise ValueError('Unsupported maturity extrapolation')
        return float(np.interp(maturity, self.maturities, self.theta))

    def supported_variance(self, k, maturity: float):
        theta = self.theta_at(maturity)
        exact = np.flatnonzero(self.maturities == maturity)
        if len(exact):
            ids = exact
        else:
            right = int(np.searchsorted(self.maturities, maturity))
            ids = np.array([right-1, right])
        lo, hi = float(self.support_min[ids].max()), float(self.support_max[ids].min())
        values = np.asarray(k, float)
        if lo >= hi or not np.isfinite(values).all() or np.any(values < lo) or np.any(values > hi):
            raise ValueError('Unsupported strike extrapolation')
        return ssvi_variance(values, theta, self.rho, self.eta)

    def certificate(self):
        phi = self.eta/np.sqrt(self.theta*(1+self.theta))
        return {'rho': self.rho, 'eta': self.eta,
                'eta_times_one_plus_abs_rho': self.eta*(1+abs(self.rho)),
                'max_theta_phi_times_skew': float(np.max(self.theta*phi*(1+abs(self.rho)))),
                'max_theta_phi_squared_times_skew': float(np.max(self.theta*phi**2*(1+abs(self.rho)))),
                'theta_nondecreasing': bool(np.all(np.diff(self.theta) >= 0)),
                'theorem_scope': 'Idealized SSVI; all k, fitted/interpolated maturities; not venue execution or tail validation'}


def fit_joint_ssvi(curves, config):
    """Fit only supplied training curves; retain each fixed optimizer start."""
    curves = sorted(curves, key=lambda c: float(c.T_years.iloc[0]))
    if not curves or any(len(c) < 5 for c in curves):
        raise ValueError('At least five training strikes in each SSVI expiry required')
    for c in curves:
        if not np.isfinite(c[['k','total_variance','T_years']].to_numpy()).all() or (c.total_variance <= 0).any():
            raise ValueError('Invalid SSVI training values')
    times = np.array([c.T_years.iloc[0] for c in curves], float)
    if np.any(times <= 0) or np.any(np.diff(times) <= 0):
        raise ValueError('Distinct increasing maturities required')
    theta0 = np.maximum.accumulate(np.array([
        np.median(c.iloc[np.argsort(np.abs(c.k.to_numpy()))[:3]].total_variance)
        for c in curves], float))
    increments = np.maximum(np.diff(np.r_[0., theta0]), 1e-7)
    scales = [float(np.median(c.total_variance)) for c in curves]
    n = len(curves)
    lower = np.r_[np.full(n, np.log(1e-9)), -5., -12.]
    upper = np.r_[np.full(n, np.log(4.)), 5., 12.]

    def decode(z):
        theta = np.cumsum(np.exp(z[:n]))
        rho = .999*np.tanh(z[n])
        eta = config['ssvi_eta_rho_ceiling']*expit(z[n+1])/(1+abs(rho))
        return theta, float(rho), float(eta)

    def residual(z):
        theta,rho,eta = decode(z)
        return np.concatenate([(ssvi_variance(c.k.to_numpy(), th, rho, eta)-c.total_variance.to_numpy())/
                               (scale*np.sqrt(len(c)))
                               for c,th,scale in zip(curves,theta,scales)])

    attempts, best = [], None
    for i, (start_rho, fraction) in enumerate(config['ssvi_starts']):
        seed = np.r_[np.log(increments),np.arctanh(start_rho/.999),np.log(fraction/(1-fraction))]
        seed = np.clip(seed, lower+1e-9, upper-1e-9)
        try:
            tol = config['ssvi_solver_tolerance']
            result = least_squares(residual, seed, bounds=(lower, upper), x_scale='jac',
                                   max_nfev=config['ssvi_max_nfev'],xtol=tol,ftol=tol,gtol=tol)
            attempts.append({'start': i, 'success': bool(result.success), 'status': int(result.status),
                             'cost': float(result.cost), 'nfev': int(result.nfev), 'message': str(result.message)})
            if result.success and np.isfinite(result.cost) and (best is None or result.cost < best.cost):
                best = result
        except (ValueError,RuntimeError,FloatingPointError) as exc:
            attempts.append({'start': i, 'success': False, 'error': str(exc)})
    if best is None:
        return None, attempts
    theta,rho,eta = decode(best.x)
    surface = SSVISurface(times,theta,rho,eta,np.array([c.k.min() for c in curves]),np.array([c.k.max() for c in curves]))
    return surface, attempts


@dataclass(frozen=True)
class ConvexCallSlice:
    k: np.ndarray
    calls: np.ndarray

    def __post_init__(self):
        for name in ('k','calls'):
            value = np.array(getattr(self,name), dtype=float, copy=True)
            value.setflags(write=False);object.__setattr__(self,name,value)
        if (self.k.ndim != 1 or self.calls.shape != self.k.shape or len(self.k)<3 or
            not np.isfinite(self.k).all() or not np.isfinite(self.calls).all() or
            np.any(np.diff(self.k) <= 0)):
            raise ValueError('Invalid convex call knots')
        if self.constraint_error() > 1e-8:
            raise ValueError('Convex call constraints violated')

    @property
    def x(self):
        return np.exp(self.k)

    def constraint_error(self):
        slopes = np.diff(self.calls)/np.diff(self.x)
        return float(max(0.,np.max(np.maximum(0,1-self.x)-self.calls),np.max(self.calls-1),
                         np.max(slopes),np.max(-1-slopes),np.max(-np.diff(slopes))))

    def call(self, k):
        k = np.asarray(k,float)
        if not np.isfinite(k).all():
            raise ValueError('Finite moneyness required')
        if np.any(k < self.k[0]) or np.any(k > self.k[-1]):
            raise ValueError('Unsupported convex call extrapolation')
        x = np.exp(k)
        return np.interp(x,self.x,self.calls)


def fit_convex_call(k, w, config):
    k,w = np.asarray(k,float),np.asarray(w,float)
    if k.ndim != 1 or w.shape!=k.shape or len(k)<3 or np.any(np.diff(k)<=0):
        raise ValueError('Ordered distinct training strikes required')
    target = normalized_call(k,w); x = np.exp(k); n = len(k)
    D = np.zeros((n-1,n))
    for i,dx in enumerate(np.diff(x)):
        D[i,i]=-1/dx;D[i,i+1]=1/dx
    A = np.vstack([D,np.diff(D,axis=0)])
    lb = np.r_[np.full(n-1,-1.),np.zeros(n-2)]
    ub = np.r_[np.zeros(n-1),np.full(n-2,np.inf)]
    scale = max(.01,float(np.median(target)))
    objective = lambda c: float(np.mean(((c-target)/scale)**2))
    gradient = lambda c: 2*(c-target)/(n*scale**2)
    seed = normalized_call(k,np.full(n,float(np.median(w))))
    result = minimize(objective,seed,jac=gradient,method='SLSQP',
                      bounds=Bounds(np.maximum(0,1-x),np.ones(n)),
                      constraints=[LinearConstraint(A,lb,ub)],
                      options={'maxiter': config['convex_maxiter'],'ftol': config['convex_ftol']})
    info = {'success': bool(result.success),'status': int(result.status),'iterations': int(result.nit),
            'message': str(result.message),'objective': float(result.fun)}
    if not result.success or not np.isfinite(result.x).all():
        return None,info
    try:
        fit = ConvexCallSlice(k,result.x)
    except ValueError as exc:
        info.update(success=False,error=str(exc));return None,info
    info.update(constraint_error=fit.constraint_error(),
                mark_call_adjustment_rmse=float(np.sqrt(np.mean((result.x-target)**2))))
    return fit,info
