"""Historical research baseline integrated into the current scanner, not another broker."""
from .research_config import Config
from .research_models import Snapshot
from .research_baseline import analyze

def evaluate(candidate, now, min_liquidity, stale_seconds):
    o=candidate.get('observation')
    if not o or not o['complete']:
        return {'state':'NO TRADE','market_score':None,'nova_score':None,'coverage':0,'components':{},'reasons':['Incomplete market observations'], 'strategy':None,'research_candidate':False}
    snap=Snapshot(mint=o['mint'],symbol=candidate['symbol'],pair=o['pool'],price=o['price'],liquidity=o['liquidity'],volume5m=o['volume5m'],volume1h=o['volume1h'],buys5m=int(o['buys5m']),sells5m=int(o['sells5m']),change5m=o['change5m'],change1h=o['change1h'],received_at=o['received_at'],market_cap=o['market_cap'],pair_created_at=o['pair_created_at'])
    result=analyze(snap,now,Config(min_liquidity=min_liquidity,stale_seconds=stale_seconds)).dict()
    result.update(model_version='research-market-v1',confidence=None,estimated_probability=None,weights={'liquidity':.3,'momentum':.3,'buy_count_pressure':.2,'activity':.2})
    result['coverage']=sum(v is not None for v in result['components'].values())/len(result['components'])
    return result
