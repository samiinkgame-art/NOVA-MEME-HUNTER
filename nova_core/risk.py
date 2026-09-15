"""UTC period protection using mark-to-liquidation equity. External cash flows unsupported."""
from datetime import datetime, timezone
from .money import dec

def update_periods(state:dict, equity, now:float) -> dict:
    e=dec(equity)
    if e<=0: raise ValueError('Equity must be positive')
    dt=datetime.fromtimestamp(now,timezone.utc)
    result=dict(state)
    day,week=dt.strftime('%Y-%m-%d'),dt.strftime('%G-%V')
    if result.get('day')!=day: result.update(day=day,day_start=str(e))
    if result.get('week')!=week: result.update(week=week,week_start=str(e))
    result['peak']=str(max(e,dec(result.get('peak',e))))
    return result

def assess_periods(state, equity, daily, weekly, drawdown):
    e=dec(equity);reasons=[]
    for name,base,limit in [('daily',state['day_start'],daily),('weekly',state['week_start'],weekly),('drawdown',state['peak'],drawdown)]:
        b,l=dec(base),dec(limit)
        if b<=0 or not 0<l<1: raise ValueError('Invalid risk baseline or limit')
        if e<=b*(1-l): reasons.append(name+' equity loss limit')
    return reasons
