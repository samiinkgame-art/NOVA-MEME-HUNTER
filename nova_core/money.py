"""Decimal financial arithmetic; floats only at legacy/UI projection boundaries."""
from decimal import Decimal, InvalidOperation, localcontext
from dataclasses import dataclass

def dec(value) -> Decimal:
    if isinstance(value, bool):
        raise ValueError('Boolean is not money')
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError('Invalid financial value') from None
    if not d.is_finite():
        raise ValueError('Non-finite financial value')
    return d

@dataclass(frozen=True)
class Settlement:
    quantity: Decimal
    gross: Decimal
    fee: Decimal
    net: Decimal
    cost: Decimal
    pnl: Decimal

def settle(quantity, entry, fill, fee_bps) -> Settlement:
    q, e, f, b = map(dec, (quantity, entry, fill, fee_bps))
    if q <= 0 or e <= 0 or f <= 0 or not 0 <= b < 10000:
        raise ValueError('Invalid settlement')
    with localcontext() as ctx:
        ctx.prec = 50
        gross, cost = q*f, q*e
        fee = gross*b/10000
        return Settlement(q, gross, fee, gross-fee, cost, gross-fee-cost)

def size(equity, cash, exposure, risk_fraction, stop_fraction, roundtrip_cost,
         max_position, max_exposure, liquidity_cap):
    e,c,x,r,s,k,p,t,l=map(dec,(equity,cash,exposure,risk_fraction,stop_fraction,roundtrip_cost,max_position,max_exposure,liquidity_cap))
    if min(e,c,r,s,p,t,l)<=0 or x<0 or k<0 or max(r,s,p,t)>1:
        return Decimal(0)
    return max(Decimal(0),min(e*r/(s+k),c/(1+k),e*p,max(Decimal(0),e*t-x),l))
