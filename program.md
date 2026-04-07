# IMC Prosperity Autoresearch — P3+P2 Cross-Competition Training

**Goal**: Build strategy archetypes that work on BOTH Prosperity 2 AND 3, proving they transfer to P4. The same `trader.py` handles both competitions via runtime product detection.

**Metric**: `composite_score` from eval.sh — weighted across P3 rounds, P2 rounds, stress tests, out-of-sample data, and transfer bonuses.

**Current baseline**: composite_score ~130,000 | 0 crashes | 2/3 archetypes transfer

## The Archetype Map

| Archetype | P2 Products | P3 Products |
|-----------|-------------|-------------|
| **MM (fixed)** | AMETHYSTS (10,000) | RAINFOREST_RESIN (10,000) |
| **MM (dynamic)** | STARFRUIT | KELP |
| **MM (volatile)** | — | SQUID_INK (currently skipped) |
| **Basket arb** | GIFT_BASKET = 4C+6S+1R | PB1 = 6CR+3J+1D, PB2 = 4CR+2J |
| **Options** | COCONUT_COUPON (K=10000) | VOLCANIC_ROCK_VOUCHER_* (5 strikes) |
| **Conversion** | ORCHIDS (sunlight, humidity) | MACARONS (sunlightIndex, sugarPrice) |
| **Insider** | Vladimir/Remy, Rihanna/Vinnie | Olivia |

## Setup

1. Read `trader.py` completely — 788 lines, clean archetype architecture.
2. Read `eval.sh`, `compute_score.py` — understand the 11-test scoring (NEVER modify).
3. Study reference traders:
   - P3: `../imc-prosperity-3/FrankfurtHedgehogs_polished.py` (200k options/day unhedged)
   - P3: `../chrispyroberts-prosperity-3/ROUND5/OLIVIA IS THE GOAT.py` (983k total, strong insider)
   - P2: `../imc-prosperity-2/src/submissions/round5.py` (9th place, BS options, signal trading)
4. Run `python3 prepare.py` to validate environment.
5. Begin the experiment loop.

## Evaluation Pipeline (11 tests, ~90 seconds)

| Test | What it measures | Current score |
|------|-----------------|---------------|
| P3 Round 1 | MM archetype (RESIN, KELP) | 69,469 |
| P3 Round 2 | + Basket arb (baskets, components) | 81,479 |
| P3 Round 3 | + Options (volcanic rock vouchers) | 55,644 |
| P3 Round 5 | Everything + insider + conversion | 52,560 |
| P3 R5 worse fills | Robustness (adversarial fills) | 27,750 |
| P3 R5 no trades | Hardmode (pure orderbook only) | 636 |
| P3 R6 day 3 | Out-of-sample (unseen data) | -873 |
| P2 Round 1 | MM on AMETHYSTS + STARFRUIT | 92,940 |
| P2 Round 3 | Basket on GIFT_BASKET + components | 2,604 |
| P2 Round 4 | Options on COCONUT_COUPON | 0 |
| P2 R7 day 2 | Out-of-sample | 11,982 |

**Composite formula**: 35% P3 in-sample + 10% P3 robustness + 30% P2 in-sample + 10% P2 OOS + 50k per transferring archetype - 100k per crash

## trader.py Architecture

```
Lines 1-73:    CONFIGURATION (position limits, baskets, options, params)
Lines 75-101:  UTILITIES (get_mid, get_best_bid/ask)  
Lines 103-144: BLACK-SCHOLES (call price, delta, vega, implied vol)
Lines 150-197: PRODUCT CLASSIFICATION (name-based + behavioral)
Lines 198-242: STRATEGY: Fixed MM (RESIN, AMETHYSTS)
Lines 244-306: STRATEGY: Dynamic MM (KELP, STARFRUIT)
Lines 308-380: STRATEGY: Basket Arb (PB1, PB2, GIFT_BASKET)
Lines 382-479: STRATEGY: Options (VOUCHER_*, COCONUT_COUPON)
Lines 481-540: STRATEGY: Conversion (MACARONS, ORCHIDS)
Lines 542-666: INSIDER DETECTION (behavioral, name-agnostic)
Lines 668-787: MAIN RUN (classify → strategize → validate → serialize)
```

## Speed Rules

Eval: ~90 seconds. Overhead budget: **1 minute max**.

## The Experiment Loop

LOOP FOREVER:

### 1. Decide
Check weakest archetype in results.tsv. Priority: crashes > hardmode robustness > P2 gaps > weakest archetype.

**STAGNATION DETECTION**: Before deciding, check the last 3-5 experiments in results.tsv. If composite_score improvements are consistently <2k (diminishing returns / stagnation), you MUST escalate to **Radical Mode** (see below) instead of continuing with small parameter tweaks.

### 2. Implement
Modify ONLY `trader.py`. Tag: `git commit -am "exp: [archetype] description"`

### 3. Evaluate
```bash
timeout 420 bash eval.sh > run.log 2>&1
grep "composite_score:" run.log
grep "_profit:" run.log
```

### 4. Record in results.tsv
```
commit	composite_score	p3_mm	p3_statarb	p3_options	p3_full	p3_stress	p3_hardmode	p3_oos	p3_crashes	p2_mm	p2_basket	p2_options	p2_oos	p2_crashes	status	description
```

### 5. Keep/Discard
**Keep** if composite improved AND crashes didn't increase. **Discard** otherwise.

### 6. Write Insights (after keeps)
Update `insights.md` with transferable principles.

### 7. Reflect (every 10 experiments)
`python3 summarize_results.py`

## Radical Mode (Triggered by Stagnation)

When 3+ consecutive experiments show <2k composite improvement, STOP doing parameter tweaks. Instead:

### Step 1: Research
Search arxiv, Google Scholar, and the web for papers and strategies relevant to the weakest archetype. Focus areas:
- **Market Making**: Avellaneda-Stoikov, GLFT, micro-price (Stoikov 2018), order flow imbalance, VPIN toxic flow detection, Bayesian fair value updating, Hawkes process order arrival
- **Basket/Stat Arb**: Component leg trading (trade components alongside baskets), lead-lag signals between basket and components, Ornstein-Uhlenbeck optimal entry/exit, cross-impact aware execution
- **Options**: Gamma scalping (realized vs implied vol), dispersion trading across strikes, SVI/eSSVI arbitrage-free vol surfaces, cross-strike delta-neutral portfolio management, risk-sensitive options MM
- **Insider/Information**: Adversarial bot pattern detection, Kyle/Glosten-Milgrom information models, classifier for ALL trader names (not just known insiders)
- **General**: HMM regime detection, reinforcement learning approaches, mean-field game models

### Step 2: Synthesize
Don't just pick one paper — look for combinations:
- Can two mediocre ideas compose into a strong one?
- Can an idea from one archetype transfer to another?
- Can a previously discarded idea work now that the baseline has changed?
- Re-read `insights.md` for near-misses that might work differently in combination.

### Step 3: Propose & Implement
Pick the single highest-expected-impact radical change. Prefer **structural** changes (new strategy architecture, new signal source, new product enablement) over **tuning** (parameter adjustments). Examples of radical vs incremental:
- **Radical**: Enable component leg trading (250-350 position limits vs 60-100 basket limits)
- **Radical**: Replace EMA+linear skew with Avellaneda-Stoikov optimal quoting
- **Radical**: Add OFI signal to enable SQUID_INK trading (currently 0 contribution)
- **Radical**: Add realized-vs-implied vol gamma scalping overlay to options
- **Incremental** (avoid during radical mode): changing a spread from 2 to 3, adjusting an EMA alpha, tweaking an edge threshold

### Step 4: If radical change fails
Don't revert to incremental mode immediately. Try 2-3 radical ideas before concluding the current approach is near-optimal. Radical changes may need supporting changes to work (e.g., component trading may need new position management logic).

### Step 5: Update Research Directions
After each radical experiment, update the "Research Directions" section below with what was tried, what worked, and what new directions opened up.

## Critical Weaknesses to Fix (Priority Order)

### 1. HARDMODE ROBUSTNESS: 636 (nearly zero)
With `--match-trades none`, the trader barely profits. This means strategies depend on matching against market trades for fills. In a real competition, you can't count on this.
**Fix**: Make resting orders more competitive — tighter spreads, better prices that get filled from the order book alone. The MM strategies need to cross the spread more aggressively.

### 2. P2 OPTIONS: 0 (COCONUT_COUPON disabled)
The options strategy skips COCONUT because it's "too risky." The 9th-place P2 finisher made 79-164k/day on this.
**Fix**: Enable COCONUT_COUPON trading. P2 ref used sigma=0.194, T=245/365, trade when |edge| > 2.

### 3. P3 OPTIONS LOSING MONEY (R3: options contribute negative)
P3 R3 total=55,644 but P3 R2=81,479. Options are SUBTRACTING value.
**Fix**: Options are losing because IV smoothing is too aggressive (0.3/0.7 weight), edge threshold of 4.0 is too tight causing bad fills, and conservative qty of 3-5 misses big moves. Study FrankfurtHedgehogs — they made 200k+/day unhedged.

### 4. P3 OOS NEGATIVE: -873 on R6 day 3
Slight loss on unseen data. Means some strategy is slightly overfit.
**Fix**: Investigate which product is losing. Likely basket arb premium drifting or options mispricing.

### 5. SQUID_INK SKIPPED (classified as "skip")
SQUID_INK has limit 50 but is completely ignored. The OLIVIA trader made 7-13k/day on it.
**Fix**: Enable with volatile MM or spike detection.

### 6. BASKET ARB WEAK: only ~12k P3, ~2.6k P2
Position limits are correct now (60/100/60) but basket_arb only trades qty 3 max.
**Fix**: Increase max qty, tune thresholds. P2 ref got 73-183k/day from GIFT_BASKET.

### 7. INSIDER DETECTION SLOW TO CONVERGE
Needs 8+ trades at 60% accuracy before following. By then, the edge may have decayed.
**Fix**: Lower thresholds, add signal to basket components. OLIVIA trader followed immediately.

### 8. CONVERSION WEAK: MACARONS ~1.5k/day
**Fix**: Study FrankfurtHedgehogs' conversion logic — they tracked arbitrage history.

## Research Directions

### Structural (high impact)
1. Enable COCONUT_COUPON (P2 options — 0 → potentially 100k+)
2. Fix P3 options (losing → should be 200k+ from FrankfurtHedgehogs reference)
3. Increase basket arb aggressiveness (qty 3 → 10+, tune thresholds)
4. Enable SQUID_INK trading (0 → 7-13k/day potential)
5. Improve hardmode fills (resting orders need to be competitive)

### Tuning (lower impact, do after structural)
6. MM spread width optimization (MM_FIXED_SPREAD, MM_DYNAMIC_SPREAD)
7. EMA alpha tuning (MM_DYNAMIC_EMA_ALPHA)
8. Options edge threshold (OPTIONS_EDGE_THRESHOLD)
9. Basket entry/exit thresholds
10. Insider detection sensitivity

### Investigation (insights for P4)
11. Why does unhedged options outperform hedged? Test both, document.
12. What's the optimal basket premium model?
13. How fast does insider signal decay?
14. What makes a product "mean-reverting" vs "volatile"?

## Constraints

- Order prices: `int`. Quantities: `int`.
- Position limits: HARD (backtester cancels ALL orders if exceeded).
- Return `(orders, conversions, trader_data)`.
- `numpy`, `math`, `statistics`, `json` available.
- **Trader must not crash on any round.** Crashes = -100k each.
- **P2 datamodel**: `sunlight`/`humidity`. P3: `sunlightIndex`/`sugarPrice`.

## NEVER STOP

Run indefinitely. Rotate archetypes. Document insights. The goal is a P4-ready playbook.

Once the experiment loop has begun (after the initial setup), do NOT pause to ask the human if you should continue. Do NOT ask "should I keep going?" or "is this a good stopping point?". The human might be asleep, or gone from a computer and expects you to continue working indefinitely until you are manually stopped. You are autonomous. If you run out of ideas, think harder — read papers referenced in the code, re-read the in-scope files for new angles, try combining previous near-misses, try more radical architectural changes. The loop runs until the human interrupts you, period.

As an example use case, a user might leave you running while they sleep. If each experiment takes you ~5 minutes then you can run approx 12/hour, for a total of about 100 over the duration of the average human sleep. The user then wakes up to experimental results, all completed by you while they slept!
