# IMC Prosperity 3→4 Strategy Autoresearch

**Goal**: Build and master 5 transferable strategy archetypes that will work in IMC Prosperity 4. We optimize on P3 data but the real deliverable is UNDERSTANDING — documented in `insights.md`.

**Why P3 matters for P4**: The products change names but the archetypes are ALWAYS the same:
- Round 1: Fixed-fair-value + mean-reverting + noisy/volatile → **Market Making**
- Round 2: ETF basket + constituents → **Statistical Arbitrage**
- Round 3: Options on underlying → **Volatility Trading**
- Round 4: Cross-exchange with conversion costs → **Conversion Arbitrage**
- Round 5: Trader IDs revealed, insider present → **Insider Following**

**Metric**: `composite_score` from eval.sh — tests each archetype in its natural round, plus stress test with adversarial fills. NOT just round 5 total profit.

## Setup

1. Read `trader.py` completely. Understand every strategy, every constant, every product.
2. Read `prepare.py`, `eval.sh`, `compute_score.py` to understand evaluation (NEVER modify them).
3. Read `datamodel.py` for the TradingState API.
4. Study reference traders for ideas:
   - `../imc-prosperity-3/FrankfurtHedgehogs_polished.py` — vol smile, ETF arb, commodity
   - `../chrispyroberts-prosperity-3/ROUND5/OLIVIA IS THE GOAT.py` — our starting point
5. Run `python3 prepare.py` to validate environment.
6. Begin the experiment loop.

## CRITICAL FIRST TASK: Make trader.py round-agnostic

The current trader.py CRASHES on rounds 1 and 2 because it tries to access products that don't exist in those rounds (e.g., `state.order_depths['PICNIC_BASKET2']` in round 1).

**Before any optimization, fix this.** Every product access must be guarded:
- Check `if product in state.order_depths` before accessing
- Wrap round-specific logic in try/except or product-existence checks
- The trader must produce valid output on rounds 1, 2, 3, and 5

This is non-negotiable. A strategy that crashes in competition = 0 for that round.

## The 5 Archetypes

### Archetype 1: Market Making (tested on Round 1)
**P3 products**: RAINFOREST_RESIN (fixed fair ~10000), KELP (mean-reverting), SQUID_INK (volatile)
**P4 equivalent**: Will have different names but identical mechanics.
**What to master**:
- Fair value estimation (fixed vs dynamic)
- Spread setting (tighter = more fills, wider = more profit/fill)
- Inventory management (skew quotes when position is large)
- When to take vs when to make

**Current state in trader.py**:
- RESIN: market making around 10000, works well (~35k/day)
- KELP: MM with Olivia signal, ~5-7k/day
- SQUID_INK: spike trading + MM, SQUID_LIMIT=15 but actual limit=50

**Key insight to discover**: What's the optimal relationship between spread width, position size, and inventory skew? Document this in insights.md.

### Archetype 2: Statistical Arbitrage (tested on Round 2)
**P3 products**: PICNIC_BASKET1 (6C+3J+1D), PICNIC_BASKET2 (4C+2J), components
**P4 equivalent**: Always an ETF with known composition.
**What to master**:
- Z-score the spread between basket price and component fair value
- Optimal hedge ratios
- Entry/exit thresholds
- Premium tracking (baskets typically trade at a premium to fair value)

**Current state in trader.py**:
- BASKET1_LIMIT=10 (actual: 60), BASKET2_LIMIT=10 (actual: 100)
- Only simple MM + Olivia signals, NO actual basket arb
- Crashes on Round 2 (accesses missing products)

**Key insight to discover**: What z-score threshold maximizes Sharpe? Is it better to trade basket vs components, or just market-make the basket? Document in insights.md.

### Archetype 3: Volatility Trading (tested on Round 3)
**P3 products**: VOLCANIC_ROCK (underlying), 5 call options (strikes 9500-10500)
**P4 equivalent**: Always options on some underlying. BS pricing.
**What to master**:
- Implied volatility estimation and smile fitting
- Why unhedged works (Frankfurt Hedgehogs made 200k+/day unhedged)
- Which strikes are profitable and why
- Market making around theoretical value

**Current state in trader.py**:
- IV-based market making on all 5 vouchers
- VOUCHER_10000 dominates (~150k/day), 9750 strong (~50k/day)
- VOUCHER_10250 and 10500 LOSE money
- Delta hedging exists but disabled (dont_hedge=True)
- Window-average IV, no vol smile model

**Key insight to discover**: Why does unhedged beat hedged? Is it because delta hedging has execution costs that exceed the variance reduction? What's the optimal vol smile model? Document in insights.md.

### Archetype 4: Conversion Arbitrage (tested on Round 4/5)
**P3 products**: MAGNIFICENT_MACARONS (cross-exchange, fees, tariffs, sunlight, sugar)
**P4 equivalent**: Always a cross-exchange product with conversion costs and hidden fee mechanics.
**What to master**:
- Fee structure exploitation
- When to convert vs when to trade locally
- Hidden mechanics in the observation data

**Current state in trader.py**:
- trade_macaroni() EXISTS but is COMMENTED OUT (line ~1315)
- Currently 0 profit from this entire archetype
- The function sells locally then converts position back, with break-even pricing

**Key insight to discover**: What's the actual profitable edge? Is it sell local + convert back, or buy local + convert away? What role do sunlight/sugar observations play? Document in insights.md.

### Archetype 5: Insider Following (tested on Round 5)
**P3 products**: All — Olivia is the insider
**P4 equivalent**: ALWAYS has an insider. "Find them. Copy them. Go to max position."
**What to master**:
- Signal detection (who trades consistently in the right direction?)
- Speed of response (how quickly to go max position after signal)
- Which products the insider trades most profitably
- Signal decay (how long does the edge last after detection?)

**Current state in trader.py**:
- Olivia detection on SQUID_INK, KELP, CROISSANTS
- Goes max position on croissants + baskets on signal
- Goes max position on squid ink on signal
- KELP signal tracked but NEVER ACTED ON
- Signal-based basket trading makes ~20-30k/day

**Key insight to discover**: What's the optimal time to follow vs when has the signal decayed? Should you follow on ALL products or only the signaled one? Document in insights.md.

## Speed Rules

Eval takes ~60 seconds (4 rounds + stress test). Overhead budget: **1 minute max**.

## The Experiment Loop

LOOP FOREVER:

### 1. Decide what to try

Focus on ONE ARCHETYPE per experiment. Use results.tsv to see which archetypes are weakest — improve the weakest link.

**Escalation**: Distance from last keep → boldness of next experiment.

**Deduplication**: Check results.tsv. Don't retry failed experiments unless codebase has changed significantly.

### 2. Implement

Modify ONLY `trader.py`.

Do NOT modify `prepare.py`, `eval.sh`, `compute_score.py`, `datamodel.py`.

### 3. Commit

`git commit -am "exp: [archetype] <short description>"`

Example: `git commit -am "exp: [options] remove losing strikes 10250+10500"`

### 4. Evaluate

```bash
timeout 360 bash eval.sh > run.log 2>&1
```

### 5. Extract results

```bash
grep "composite_score:" run.log
grep "_profit:" run.log
grep "crash_count:" run.log
```

If crashes > 0, that's priority #1 to fix.

Also examine per-archetype scores to understand WHERE the change had impact.

### 6. Record

Append to results.tsv (tab-separated):
```
commit	composite_score	mm_profit	statarb_profit	options_profit	full_profit	stress_profit	crashes	status	description
```
Do NOT commit results.tsv to git.

### 7. Keep or discard

**Keep** (composite_score > current best AND crashes == 0):
- Note the per-archetype changes

**Discard** (composite_score <= current best OR crashes > 0):
- `git reset --hard HEAD~1`

Exception: if crashes decreased (e.g., 2→0) even if score dropped slightly, KEEP — stability is more important than marginal profit.

### 8. Write Insights

After every KEEP, update `insights.md` with what you learned:
```markdown
## [Archetype Name]

### What works
- <specific finding with evidence from results.tsv>

### What doesn't work
- <specific finding>

### Open questions
- <what to investigate next>

### Transferable principle
- <the general rule for P4, not P3-specific details>
```

This is the REAL deliverable. The profit number is just validation.

### 9. Reflect (every 10 experiments)

Run `python3 summarize_results.py` and review:
- Which archetype is weakest? Focus there.
- Which archetype is strongest? Document why in insights.md, then move on.
- Are you spending too much time on one archetype?

Go to step 1.

## Structural Change Bias

The biggest gains come from:
- Making the trader round-agnostic (FIRST PRIORITY — eliminates crashes)
- Enabling disabled archetypes (macarons = 0 profit)
- Fixing position limits (baskets at 10 vs 60/100, squid at 15 vs 50)
- Adding real basket arbitrage (currently missing entirely)
- Fixing/removing losing option strikes

**Rule: structural experiments should outnumber tuning experiments 2:1.**

## Diversity Requirement

Rotate through archetypes. Never spend more than 3 CONSECUTIVE experiments on the same archetype. The weakest archetype always gets priority.

## Research Directions

### URGENT (crash fixes)
1. **Make trader round-agnostic**: Guard all product accesses with `if product in state.order_depths`. The trader must not crash on ANY round.

### Starting Points (LOW HANGING FRUIT)
2. **Enable MAGNIFICENT_MACARONS** (line ~1315): Uncomment `self.trade_macaroni(state)`. Currently 0 profit from this entire archetype.

3. **Increase position limits**: BASKET1_LIMIT 10→60, BASKET2_LIMIT 10→100, SQUID_LIMIT 15→50.

4. **Remove losing option strikes** (10250, 10500): Stop bleeding money.

### Archetype Deep Dives
5. **Implement real basket arbitrage**: Calculate PB1 fair value = 6×CROISSANTS_mid + 3×JAMS_mid + 1×DJEMBES_mid. Trade when spread exceeds threshold. FrankfurtHedgehogs had this (with a bug on line 435).

6. **Vol smile model for options**: FrankfurtHedgehogs used fitted coefficients `[0.27362531, 0.01007566, 0.14876677]` for IV as function of moneyness. Replace simple window average.

7. **Test hedged vs unhedged options**: Enable delta hedging (line 688, `dont_hedge=True`), measure impact. Document WHY the winner wins in insights.md.

8. **Act on Kelp Olivia signal**: `self.kelp_signal` is tracked but never used.

9. **Macaron fee structure investigation**: Study the observation data (sunlight, sugar, tariffs). Is there a predictive signal?

### Speculative
10. **Inventory-skewed market making**: Shift quotes based on current position to manage risk.
11. **Adaptive spread width**: Widen spreads in high-volatility regimes, tighten in calm markets.
12. **Cross-archetype synergy**: Olivia signals on croissants should inform basket arb direction.

## Constraints

- All order prices must be `int`. All quantities must be `int`.
- Position limits are HARD — backtester cancels ALL orders if exceeded.
- trader.py must have a `Trader` class with `run(self, state: TradingState)` returning `(orders, conversions, trader_data)`.
- `numpy` and `math` available. No other external packages.
- MAGNIFICENT_MACARONS conversion limit: 10 per timestamp.
- **Trader must not crash on any round (1, 2, 3, 5)**. Crashes = -100,000 in composite score.

## NEVER STOP

Run indefinitely. Rotate archetypes. Document insights. The goal is to walk into P4 with a playbook, not just a P3 score.
