"""Atomic exact ledger integrated into V7. Core dependency is explicitly injected."""
import json, hashlib, time, uuid
from decimal import Decimal, localcontext
from sqlalchemy import select, func
from .schema import IntegrityBase, Intent, ExactPosition, Ledger, TokenObservation
from .money import dec, settle
from .risk import update_periods, assess_periods

class Integrity:
    def __init__(self, core):
        self.c=core
        IntegrityBase.metadata.create_all(core.engine)

    def next_position_id(self):
        c=self.c
        with c.SessionLocal() as s:
            value=max(int(c.getv('position_sequence','0')),s.scalar(select(func.max(ExactPosition.position_id))) or 0,s.scalar(select(func.max(c.Position.id))) or 0)+1
            c.setv('position_sequence',str(value))
            return value

    def cash_add(self, amount):
        c=self.c
        self.ensure_anchor()
        with localcontext() as ctx:
            ctx.prec=50
            result=dec(c.getv('cash'))+dec(amount)
            if result<0: raise ValueError('Negative cash rejected')
            c.setv('cash',str(result))
        return result

    def ensure_anchor(self):
        c=self.c
        if c.getv('ledger_cash_anchor') is None:
            c.setv('ledger_cash_anchor',str(dec(c.getv('cash'))))

    def import_position(self, p):
        c=self.c
        with c.SessionLocal() as s:
            exact=s.get(ExactPosition,p.id)
            if exact: return exact
            with localcontext() as ctx:
                ctx.prec=50
                exact=ExactPosition(position_id=p.id,mint=p.mint,entry=str(dec(p.entry_price)),
                    initial_quantity=str(dec(p.initial_notional)/dec(p.entry_price)),
                    quantity=str(dec(p.remaining_cost)/dec(p.entry_price)),cost=str(dec(p.remaining_cost)),
                    realized=str(dec(p.locked_pnl)),entry_fee='0',origin='LEGACY_FLOAT_IMPORT',mark_at=None,closed=0)
                s.add(exact);s.flush()
            return exact

    def entry(self,p,notional,fee,fill,now):
        c=self.c
        with localcontext() as ctx:
            ctx.prec=50
            cost,fee,price=map(dec,(notional,fee,fill));qty=cost/price
            with c.SessionLocal() as s:
                s.add(ExactPosition(position_id=p.id,mint=p.mint,entry=str(price),initial_quantity=str(qty),quantity=str(qty),
                    cost=str(cost),realized=str(-fee),entry_fee=str(fee),origin='DECIMAL_PAPER_V1',mark_at=now,closed=0))
                s.add(Ledger(event_key='entry:'+str(p.id)+':'+uuid.uuid4().hex,position_id=p.id,phase='ENTRY',cash_delta=str(-cost-fee),quantity_delta=str(qty),fee=str(fee),pnl=str(-fee),created_at=now))
                s.flush()

    def exit(self,p,candidate,fraction=1,final=False,event_key=None):
        """Caller owns account_transaction. Returns (current legacy position, net, total realized) or None."""
        c=self.c
        if not c.valid_market_mark(candidate): raise ValueError('Fresh matching exit price required')
        if not c.valid_execution_liquidity(candidate): raise ValueError('Executable liquidity unavailable for paper model')
        if candidate.get('mint')!=p.mint: raise ValueError('Exit mint mismatch')
        with c.SessionLocal() as s:
            current=s.get(c.Position,p.id)
            if current is None: return None
            exact=self.import_position(current)
            key=event_key or ('final:'+str(p.id) if final else 'partial:'+str(p.id)+':'+uuid.uuid4().hex)
            if s.scalar(select(Ledger).where(Ledger.event_key==key)): return None
            if exact.closed: return None
            with localcontext() as ctx:
                ctx.prec=50
                f=dec(fraction)
                if not 0<f<=1: raise ValueError('Exit fraction must be in (0,1]')
                remaining=dec(exact.quantity)
                qty=remaining if final else min(remaining,dec(exact.initial_quantity)*f)
                if qty<=0:return None
                basis=dec(exact.cost) if qty==remaining else dec(exact.cost)*qty/remaining
                estimated_notional=qty*dec(candidate['price'])
                if estimated_notional>dec(candidate['liquidity'])*Decimal('.01'):
                    raise ValueError('Paper exit exceeds 1% liquidity participation; fill unavailable')
                est=c.execution_cost_estimate(candidate,current.strategy,float(estimated_notional))
                fill=c.simulated_fill_price(candidate['price'],'LONG','EXIT',est['adverse_bps'])
                value=settle(qty,exact.entry,fill,est['fee_bps'])
                pnl=value.net-basis
                self.cash_add(value.net)
                exact.quantity=str(remaining-qty);exact.cost=str(dec(exact.cost)-basis)
                exact.realized=str(dec(exact.realized)+pnl);exact.mark_at=candidate['received_at']
                exact.closed=int(qty==remaining)
                current.remaining_cost=float(dec(exact.cost));current.locked_pnl=float(dec(exact.realized))
                current.last_price=candidate['price']
                s.add(Ledger(event_key=key,position_id=p.id,phase='EXIT' if final else 'PARTIAL_EXIT',cash_delta=str(value.net),quantity_delta=str(-qty),fee=str(value.fee),pnl=str(pnl),created_at=time.time()))
                c.record_execution_event(p.id,None,candidate,current.strategy,'EXIT' if final else 'PARTIAL_EXIT',float(value.gross),candidate['price'],float(fill),est)
                s.flush()
                return current,float(value.net),float(dec(exact.realized))

    def reconcile(self):
        c=self.c
        with c.SessionLocal() as s:
            entries=s.scalars(select(Ledger).order_by(Ledger.id)).all()
            with localcontext() as ctx:
                ctx.prec=50
                expected=dec(c.getv('ledger_cash_anchor',c.getv('cash')))+sum((dec(x.cash_delta) for x in entries),Decimal(0))
                actual=dec(c.getv('cash'));difference=actual-expected
                issues=[]
                if abs(difference)>Decimal('1e-24'):issues.append('cash ledger mismatch')
                live=s.scalars(select(c.Position)).all();ids={p.id for p in live}
                exacts=s.scalars(select(ExactPosition).where(ExactPosition.closed==0)).all()
                if ids!={p.position_id for p in exacts}:issues.append('position projection mismatch')
                for p in live:
                    exact=s.get(ExactPosition,p.id)
                    if exact and (dec(exact.quantity)<0 or dec(exact.cost)<0 or abs(dec(p.remaining_cost)-dec(exact.cost))>Decimal('1e-8')):
                        issues.append('position quantity/cost mismatch: '+str(p.id))
                return {'ok':not issues,'issues':issues,'cash_expected':str(expected),'cash_actual':str(actual),'difference':str(difference),
                    'ledger_events':len(entries),'legacy_imports':sum(x.origin=='LEGACY_FLOAT_IMPORT' for x in exacts),'kind':'PAPER_LEDGER_ONLY'}

    def recover(self):
        c=self.c
        @c.account_transaction
        def action():
            self.ensure_anchor()
            with c.SessionLocal() as s:
                for p in s.scalars(select(c.Position)).all():self.import_position(p)
            result=self.reconcile()
            c.setv('recovery_ok','true' if result['ok'] else 'false')
            c.setv('bot_enabled','false')
            if not result['ok']: c.setv('killed','true')
            c.setv('integrity_schema_version','1')
            return result
        return action()

    def periods(self):
        c=self.c
        @c.account_transaction
        def action():
            equity=c.metrics()['equity']
            prior=json.loads(c.getv('equity_periods','{}'))
            if equity<=0:return {'reasons':['Non-positive equity'],'state':prior}
            marks={x['mint']:x for x in c.runtime['candidates']}
            with c.SessionLocal() as s:positions=s.scalars(select(c.Position)).all()
            if any(not c.valid_market_mark(marks.get(p.mint,{})) for p in positions):
                return {'reasons':['Existing position mark is stale'],'state':prior}
            state=update_periods(prior,equity,time.time());c.setv('equity_periods',json.dumps(state))
            reasons=assess_periods(state,equity,c.f('daily_loss_limit_pct')/100,c.f('weekly_loss_limit_pct')/100,c.f('drawdown_hard_cut_pct')/100)
            return {'reasons':reasons,'state':state}
        return action()

    def request(self,key,payload,action):
        c=self.c
        if not isinstance(key,str) or not 8<=len(key)<=128:raise c.HTTPException(400,'Idempotency key must be 8-128 characters')
        fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        @c.account_transaction
        def execute():
            with c.SessionLocal() as s:
                prior=s.get(Intent,key)
                if prior:
                    if prior.fingerprint!=fingerprint: raise c.HTTPException(409,'Idempotency key reused with different payload')
                    return json.loads(prior.response)
                result=action()
                s.add(Intent(key=key,fingerprint=fingerprint,response=json.dumps(result,allow_nan=False),created_at=time.time()))
                s.flush()
                return result
        return execute()

    def observation(self,obs):
        c=self.c
        @c.account_transaction
        def record():
            with c.SessionLocal() as s:
                row=s.get(TokenObservation,obs.mint)
                if row and obs.received_at<=row.received_at:return row.first_seen
                if row:
                    row.received_at=obs.received_at;row.pair=obs.pool;row.snapshot=json.dumps(obs.dict(),allow_nan=False)
                else:
                    row=TokenObservation(mint=obs.mint,first_seen=obs.received_at,received_at=obs.received_at,source_time=None,pair=obs.pool,snapshot=json.dumps(obs.dict(),allow_nan=False));s.add(row)
                return row.first_seen
        return record()
