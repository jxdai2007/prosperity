# IMC Prosperity 3 Trader Autoresearch

**Goal**: Maximize total profit across all 16 products on round 5 (3 days) of the IMC Prosperity 3 backtester. Current baseline: ~982,760 seashells.

## Setup

1. Read `trader.py` completely. Understand every strategy, every constant, every product.
2. Read `prepare.py` to understand evaluation (but NEVER modify it).
3. Read `eval.sh` to understand how profit is measured (NEVER modify it).
4. Read `datamodel.py` for the TradingState API.
5. Study the reference traders for ideas:
   - `../imc-prosperity-3/FrankfurtHedgehogs_polished.py` — ETF arb, options vol smile, commodity strategy
   - `../chrispyroberts-prosperity-3/ROUND5/OLIVIA IS THE GOAT.py` — our starting point
6. Run `python3 prepare.py` to validate environment and establish baseline.
7. Begin the experiment loop.

## Context: IMC Prosperity 3 Trading Competition

16 products traded simultaneously. Backtester runs 10,000 timestamps per day × 3 days.

### Products & Position Limits
| Product | Limit | Current Strategy | Approx Profit/Day |
|---------|-------|-----------------|-------------------|
| RAINFOREST_RESIN | 50 | Market making around 10000 | ~35,000 |
| KELP | 50 | Market making + Olivia signal | ~5,000-7,000 |
| SQUID_INK | 50 | Spike trading + MM (LIMIT=15!) | ~7,000-13,000 |
| CROISSANTS | 250 | Olivia signal following | ~13,000-25,000 |
| JAMS | 350 | Olivia signal hedge | ~0-28,000 |
| DJEMBES | 60 | Olivia signal hedge | ~-2,000-0 |
| PICNIC_BASKET1 | 60 | MM (LIMIT=10!) + Olivia | ~4,000-8,000 |
| PICNIC_BASKET2 | 100 | MM (LIMIT=10!) + Olivia | ~4,000-6,000 |
| VOLCANIC_ROCK | 400 | Not traded (hedging disabled) | 0 |
| VOUCHER_9500 | 200 | IV market making | ~6,000-20,000 |
| VOUCHER_9750 | 200 | IV market making | ~42,000-76,000 |
| VOUCHER_10000 | 200 | IV market making | ~142,000-165,000 |
| VOUCHER_10250 | 200 | IV market making | ~-4,000 (LOSING) |
| VOUCHER_10500 | 200 | IV market making | ~-578 (LOSING) |
| MAGNIFICENT_MACARONS | 75 | DISABLED | 0 |

### Key Mechanics
- **Olivia** is an insider trader. When she buys/sells SQUID_INK, KELP, or CROISSANTS, following her signal is profitable.
- **Baskets**: PB1 = 6×CROISSANTS + 3×JAMS + 1×DJEMBES. PB2 = 4×CROISSANTS + 2×JAMS.
- **Options**: VOLCANIC_ROCK_VOUCHER_* are call options with strikes 9500-10500. Black-Scholes pricing with implied vol.
- **Macarons**: can be converted from external market (import/export with fees/tariffs).
- Order prices must be integers. Quantities must be integers.
- Trader class persists across timestamps (self.* state survives).
- `traderData` is a string that persists but currently unused (set to "SAMPLE").

## Speed Rules

Your #1 job is to MAXIMIZE EXPERIMENTS PER HOUR.

Eval takes ~20 seconds. Your overhead budget is **30 seconds max** between experiments.

That means: decide what to try, implement it, commit, run. No multi-paragraph deliberation. Learn from results, not speculation.

## The Experiment Loop

LOOP FOREVER:

### 1. Decide what to try

Use ALL inputs: your own analysis of trader.py, results.tsv, research_queue.md, domain knowledge about market making and options trading.

You are the strategist AND the executor. Don't blindly pull from the research queue — evaluate, combine, modify, reject.

**Escalation**: The further you are from your last keep, the bolder your next experiment should be.
- Recent keep → nearby: tune parameters, adjust thresholds
- Several discards → moderate: change strategy logic, add/remove components
- Many discards → significant: rewrite a product strategy, try a completely different approach

**Deduplication**: Check results.tsv. Don't retry failed experiments unless the codebase has changed significantly.

### 2. Implement

Modify ONLY `trader.py`.

Do NOT modify `prepare.py`, `eval.sh`, `compute_score.py`, `datamodel.py`, or any data files.

### 3. Commit

`git commit -am "exp: <short description>"`

### 4. Evaluate

```bash
timeout 120 bash eval.sh > run.log 2>&1
```

### 5. Extract results

```bash
grep "total_profit:" run.log
```

If empty → crashed. `tail -n 50 run.log`.
- Fixable (typo, import): fix, re-commit, re-run. Max 2 attempts.
- Fundamental (OOM, impossible): log crash, revert, move on.

Also check per-product breakdown to understand WHERE profit changed.

### 6. Record

Append to results.tsv (tab-separated):
```
commit	total_profit	status	description
```
Do NOT commit results.tsv to git.

### 7. Keep or discard

**Keep** (total_profit > current best):
- Note: compare against the BEST KEPT result, not just the last one

**Discard** (total_profit <= current best):
- `git reset --hard HEAD~1`

### 8. Re-evaluation after major keeps

After any keep that improves profit by MORE THAN 50,000 (roughly 5%), scan recent discards. Ideas that failed before might work in the new context.

### 9. Reflect (every 10 experiments)

Run `python3 summarize_results.py` and review:
- What directions are fruitful? Double down.
- What directions are exhausted? Abandon.
- Are you being too incremental? Go bolder.
- Structural vs tuning ratio — aim for 2:1 structural.

Go to step 1.

## Structural Change Bias

Parameter tuning has a LOW improvement ceiling. The biggest gains come from:
- Enabling disabled products (MACARONS = 0 profit currently)
- Fixing the position limits (baskets at 10 vs 60/100, squid at 15 vs 50)
- Adding new strategies (basket arbitrage, better vol smile)
- Removing losing strategies (VOUCHER_10250, VOUCHER_10500)

**Rule: structural experiments should outnumber tuning experiments 2:1.**

## Diversity Requirement

Never spend more than 2 CONSECUTIVE experiments in the same category:
- Market making parameters (spreads, edges)
- Options strategy (IV, BS, hedging)
- Basket/ETF strategy
- Olivia signal trading
- Position sizing / limits
- New product activation
- Squid ink strategy

## Research Directions

### Starting Points (LOW HANGING FRUIT)
1. **Enable MAGNIFICENT_MACARONS** (line ~1315): `self.trade_macaroni(state)` is commented out. Uncomment and tune. FrankfurtHedgehogs' strategy made ±2k-14k/day. The conversion logic already exists.

2. **Increase BASKET1_LIMIT from 10 to 60, BASKET2_LIMIT from 10 to 100** (line 15-16): These are the ACTUAL position limits. The current code artificially caps at 10. More position = more MM profit.

3. **Increase SQUID_LIMIT from 15 to 50** (line 17): Actual limit is 50. Currently leaving 70% of capacity unused.

4. **Remove losing vouchers** (10250, 10500 consistently lose): In `initialize_round_3()` line ~450, filter self.vouchers to only include 9500, 9750, 10000.

### Medium Structural Changes
5. **Implement basket arbitrage**: Calculate fair value of PB1 = 6×CROISSANTS_mid + 3×JAMS_mid + 1×DJEMBES_mid. When PB1 market price deviates from fair value by >threshold, trade the spread. FrankfurtHedgehogs had this but with a bug.

6. **Use vol smile for options pricing**: FrankfurtHedgehogs used fitted coefficients `[0.27362531, 0.01007566, 0.14876677]` for IV as function of moneyness. Currently using simple window average.

7. **Enable delta hedging**: `trade_underlying` has `dont_hedge=True` (line 688). Enabling it reduces variance. May improve or hurt depending on hedge ratio.

8. **Act on Kelp Olivia signals**: `self.kelp_signal` is tracked but never acted on in `run()`.

### Deeper Ideas
9. **Better options market making**: Instead of simple ±eps around fair value, use different spreads per strike based on liquidity and Greeks.

10. **Adaptive basket premium**: Track running mean of basket premium (like FrankfurtHedgehogs) instead of static approach.

11. **Use traderData for state persistence**: Currently set to "SAMPLE" and never read. Could persist price history, IV estimates, etc. across days.

12. **Combine Olivia signals across products**: If Olivia buys CROISSANTS, this is bullish for baskets AND components. Currently only baskets react to croissant signal.

### Speculative
13. **Machine-learning-style feature engineering**: Use price ratios, spreads, volumes as features for directional prediction.
14. **Pairs trading** between correlated products (e.g., KELP vs SQUID_INK).
15. **Optimal execution**: Instead of market orders, use limit orders with smart pricing for large Olivia-signal trades.

## Constraints

- All order prices must be `int`. All quantities must be `int`.
- Position limits are HARD — the backtester cancels ALL orders if you exceed.
- trader.py must have a `Trader` class with a `run(self, state: TradingState)` method.
- Return `(orders_dict, conversions_int, trader_data_str)`.
- `numpy` and `math` available. No other external packages.
- MAGNIFICENT_MACARONS conversion limit: 10 per timestamp.

## NEVER STOP

Run indefinitely. If out of ideas: re-read FrankfurtHedgehogs for strategy ideas, retry discarded ideas in new context, try combinations of keeps, try radical departures. The loop runs until the human interrupts you.
