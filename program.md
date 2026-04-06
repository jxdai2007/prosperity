# IMC Prosperity Autoresearch — P3+P2 Cross-Competition Training

**Goal**: Build strategy archetypes that work on BOTH IMC Prosperity 2 AND Prosperity 3 — proving they'll transfer to Prosperity 4. The same `trader.py` must handle both competitions without knowing which one it's in.

**The test**: eval.sh runs your trader on P3 rounds 1/2/3/5 AND P2 rounds 1/3/4. If it only profits on P3, it's overfit to P3 product names. If it profits on both, the archetypes are truly general.

## The Archetype Map

Products change names every year. The archetypes never change:

| Archetype | P2 Products | P3 Products | P4 Products |
|-----------|-------------|-------------|-------------|
| **MM (fixed)** | AMETHYSTS (10,000) | RAINFOREST_RESIN (10,000) | ??? |
| **MM (dynamic)** | STARFRUIT | KELP | ??? |
| **MM (volatile)** | — | SQUID_INK | ??? |
| **Basket arb** | GIFT_BASKET = 4C+6S+1R | PB1 = 6CR+3J+1D | ??? |
| **Basket components** | CHOCOLATE, STRAWBERRIES, ROSES | CROISSANTS, JAMS, DJEMBES | ??? |
| **Options** | COCONUT_COUPON (K=10000 on COCONUT) | VOLCANIC_ROCK_VOUCHER_* | ??? |
| **Conversion** | ORCHIDS (sunlight, humidity) | MACARONS (sunlightIndex, sugarPrice) | ??? |
| **Insider** | Vladimir↔Remy, Rihanna↔Vinnie | Olivia | ??? |

**Your trader must detect archetypes at runtime from `state.order_depths` product names and market behavior.** It cannot hardcode P3-specific or P2-specific product names as the only path.

## Setup

1. Read `trader.py` completely.
2. Read `eval.sh`, `compute_score.py` — understand the dual-competition scoring (NEVER modify).
3. Read `datamodel.py` for the TradingState API.
4. Study reference traders for archetype implementations:
   - P3: `../imc-prosperity-3/FrankfurtHedgehogs_polished.py`
   - P2: `../imc-prosperity-2/src/submissions/round5.py` (9th place, by jmerle)
5. Run `python3 prepare.py` to validate environment.
6. Begin the experiment loop.

## Architecture: Product Detection

The trader needs a detection layer that maps unknown product names to archetypes. Approaches:

### Option A: Name pattern matching (pragmatic)
```python
def classify_product(self, name, order_depth, state):
    # Fixed-value MM: tight spread, stable mid near round number
    # Options: name contains "VOUCHER", "COUPON", or a strike price
    # Basket: name contains "BASKET", "GIFT"
    # Conversion: has conversionObservations
    # etc.
```

### Option B: Runtime behavior detection (general)
```python
def classify_product(self, name, price_history):
    # Fixed-value: std(mid) < threshold, mid near round number
    # Mean-reverting: autocorrelation < 0
    # Volatile: std(mid) > threshold
    # Options: price << underlying, always positive
    # Basket: price ≈ weighted sum of other products
```

### Option C: Hybrid (recommended)
Use name patterns as hints, verify with behavior. This is what you'd do on P4 day 1 — look at names for clues, then confirm from data.

**IMPORTANT**: The P2 and P3 datamodels have minor differences:
- P2 ConversionObservation: `sunlight`, `humidity`
- P3 ConversionObservation: `sunlightIndex`, `sugarPrice`
- Your code must handle both (use `getattr` or try/except)

## CRITICAL FIRST TASK: Make trader.py work on both P2 and P3

Current state:
- Crashes on P3 rounds 1 and 2 (accesses missing products)
- Will crash on ALL P2 rounds (hardcoded P3 product names)
- P2 scores: 0, 0, 0

The trader must:
1. **Guard all product accesses** — check `if product in state.order_depths`
2. **Detect which products exist** and apply the right strategy
3. **Handle unknown products gracefully** — at minimum, do basic market making on anything

This is the #1 priority. Until this works, the composite score is crushed by crash penalties.

## The 5 Archetypes — What to Master

### Archetype 1: Market Making
**The universal strategy.** Works on any product with a bid-ask spread.

P3: RAINFOREST_RESIN (fixed ~10000), KELP (dynamic), SQUID_INK (volatile)
P2: AMETHYSTS (fixed ~10000), STARFRUIT (dynamic)

**What the agent must discover and document in insights.md:**
- Optimal spread width as function of volatility
- Inventory skew formula (how to adjust quotes based on position)
- When to detect "fixed fair value" vs "mean-reverting" from runtime data
- Edge from market making on AMETHYSTS vs STARFRUIT (P2 ref: ~16k/day each)

**Current position limits in trader.py:**
- SQUID_LIMIT=15 but actual limit=50 (70% capacity unused)

### Archetype 2: Statistical Arbitrage (Basket/ETF)
**Always the same structure:** basket = weighted sum of components.

P3: PB1 = 6×CROISSANTS + 3×JAMS + 1×DJEMBES
P2: GIFT_BASKET = 4×CHOCOLATE + 6×STRAWBERRIES + 1×ROSES

**What the agent must discover:**
- How to detect basket composition at runtime (ratio estimation)
- Optimal z-score entry/exit thresholds
- Premium tracking (baskets trade at premium to fair value)
- P2 ref: GIFT_BASKET made 73k-183k/day with threshold-based trading

**Current state:** BASKET1_LIMIT=10 (actual: 60), BASKET2_LIMIT=10 (actual: 100). No real arb logic.

### Archetype 3: Options / Volatility Trading
**Always Black-Scholes.** Call options on some underlying.

P3: VOLCANIC_ROCK_VOUCHER_* (5 strikes, 9500-10500)
P2: COCONUT_COUPON (1 strike, K=10000)

**What the agent must discover:**
- Why unhedged outperforms hedged (Frankfurt Hedgehogs made 200k+/day unhedged)
- Vol smile fitting vs simple IV average
- Which strikes are profitable and why
- P2 ref: COCONUT_COUPON made 79-164k/day with BS fair value ± 2 threshold

**Current state:** Window-average IV, losing money on strikes 10250/10500, delta hedging disabled.

### Archetype 4: Conversion Arbitrage
**Cross-exchange with fees.** Always has hidden mechanics in the fee structure.

P3: MAGNIFICENT_MACARONS (sunlightIndex, sugarPrice, tariffs)
P2: ORCHIDS (sunlight, humidity, tariffs)

**What the agent must discover:**
- Fee structure exploitation patterns
- When conversion is profitable
- What the environmental observations predict
- P2 ref: Orchids strategy existed but made ~0 in later rounds

**Current state:** MACARONS strategy exists but is COMMENTED OUT.

### Archetype 5: Insider Following
**"Find them. Copy them. Go to max position."**

P3: Olivia trades SQUID_INK, KELP, CROISSANTS
P2: Vladimir↔Remy (CHOCOLATE), Rihanna↔Vinnie (ROSES)

**What the agent must discover:**
- General signal detection: who trades consistently ahead of moves?
- Speed of response after signal
- Signal decay rate
- Whether to follow on the signaled product only, or related products too

**Current state:** Olivia detection works for P3. No P2 insider detection. KELP signal tracked but unused.

## Speed Rules

Full eval takes ~70 seconds (P3 rounds + P2 rounds). Overhead budget: **1 minute max**.

## The Experiment Loop

LOOP FOREVER:

### 1. Decide what to try

Check which archetype is weakest across BOTH competitions. Fix the weakest link.

Tag experiments by archetype: `git commit -am "exp: [mm] add P2 AMETHYSTS detection"`

**Priority order:**
1. Fix crashes (any crash = -100k in composite)
2. Enable archetypes on P2 (currently all 0)
3. Improve weakest archetype
4. Document insights

### 2. Implement

Modify ONLY `trader.py`. NEVER modify eval.sh, compute_score.py, prepare.py, datamodel.py.

### 3. Commit & Evaluate

```bash
git commit -am "exp: [archetype] description"
timeout 360 bash eval.sh > run.log 2>&1
```

### 4. Extract results

```bash
grep "composite_score:" run.log
grep "_profit:" run.log
grep "_crashes:" run.log
grep "transfers:" run.log
```

### 5. Record

Append to results.tsv (tab-separated):
```
commit	composite_score	p3_mm	p3_statarb	p3_options	p3_full	p3_stress	p3_crashes	p2_mm	p2_basket	p2_options	p2_crashes	status	description
```

### 6. Keep or discard

**Keep** if composite_score improved AND total crashes didn't increase.
**Discard** otherwise: `git reset --hard HEAD~1`

Exception: if crashes decreased, keep even if score dropped slightly.

### 7. Write Insights (after every KEEP)

Update `insights.md` with transferable principles:
```markdown
## [Archetype Name]
### What works on BOTH P2 and P3
### What's P3-specific (won't transfer)
### What's P2-specific (won't transfer)
### Transferable principle for P4
```

### 8. Reflect (every 10 experiments)

`python3 summarize_results.py` — check transfer score, crash rate, archetype balance.

## Research Directions

### URGENT: Cross-competition compatibility
1. **Make trader round-agnostic**: Guard ALL product accesses. Must not crash on any round of either P2 or P3.
2. **Add product detection layer**: Classify products into archetypes at runtime. Start simple (name matching), evolve to behavior-based.
3. **Handle datamodel differences**: P2 has `humidity`, P3 has `sugarPrice`. Use try/except or getattr.

### Low-hanging fruit
4. **Enable MACARONS** (line ~1315): Uncomment `self.trade_macaroni(state)`.
5. **Increase position limits**: BASKET1_LIMIT 10→60, BASKET2_LIMIT 10→100, SQUID_LIMIT 15���50.
6. **Remove losing P3 option strikes** (10250, 10500).

### Archetype generalization
7. **Generic MM**: single MM function that works on ANY product. Takes fair_value_estimate and spread_width as params.
8. **Generic basket arb**: detect composition weights at runtime, trade spread when z-score exceeds threshold.
9. **Generic options**: BS pricing that works with any strike/underlying pair.
10. **Generic insider detection**: scan market_trades for trader names that correlate with subsequent price moves.

### Deep investigations
11. **Why unhedged options work**: test on both P2 (COCONUT_COUPON) and P3 (vouchers). Document the mechanism.
12. **Basket premium dynamics**: compare P2 GIFT_BASKET premium to P3 PB1 premium. Same pattern?
13. **Conversion fee patterns**: compare ORCHIDS fees to MACARONS fees. Hidden mechanics?

## Constraints

- All order prices: `int`. All quantities: `int`.
- Position limits are HARD (backtester cancels all orders if exceeded).
- `Trader` class with `run(self, state: TradingState)` → `(orders, conversions, trader_data)`.
- `numpy`, `math`, `statistics` available. No other packages.
- Must work on both P2 and P3 datamodels.
- **Crashes = -100,000 each in composite score.**

## NEVER STOP

Run indefinitely. Rotate archetypes. The goal: walk into P4 with a playbook that works on day 1 with zero code changes beyond product name detection.
