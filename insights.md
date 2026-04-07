# Strategy Insights for P4

## 1. P2 COCONUT_COUPON: Fixed sigma works great
- sigma=0.194, T=245/365, edge threshold=2 yields 421k profit
- Fixed vol is better than smoothed IV for long-dated options with stable vol
- Key: the 9th-place P2 reference used exactly this approach
- Aggressive qty (20 per take, 15 per MM) works because limit is 600

## 2. Known insider fast-follow is massive
- Olivia (P3) yields +25k across Full/Stress/Hardmode when followed immediately
- P2 insiders (Vladimir, Remy, Rhianna, Vinnie) are unreliable on basket components — following them causes -83k losses
- Key: check market_trades for known names, follow with confidence=0.9 immediately
- This works even in hardmode because insider trades create orderbook movement

## 3. P3 options position cap critical
- Capping P3 options at 75 (vs limit of 200) dramatically improves robustness
- Day 4 (near expiry) options lose ~80k if fully loaded from day 3
- Vol smile pricing degrades near expiry, causing adverse fills
- Smaller positions = smaller drawdowns from pricing errors

## 4. Options: take-only beats MM for P3
- Removing P3 options MM resting orders improves hardmode and reduces adverse selection
- Only take when clearly mispriced (edge > threshold and price > fair)
- COCONUT_COUPON still benefits from MM with wide spread (0.8% of fair)

## 5. MACARONS conversion actively loses money
- Despite looking profitable in theory, MACARONS conversion lost -20k in R5
- The conversion costs (transport + tariffs) exceed the arb spread
- Disabling it improved P3 Full/Stress/Hardmode by 3.6k each

## 6. Product-specific spreads matter
- KELP benefits from tighter spread (1 vs 2): +4k P3 MM
- STARFRUIT needs wider spread (2): tighter spread costs -10k P2 MM
- RESIN/AMETHYSTS need spread=2: spread=1 causes adverse selection (-14k)

## 8. Basket exit logic is counterproductive
- Removing the basket position exit (deviation < 10 → close position) improved P2 basket from 46k to 80k
- The premium mean-reverts naturally; exiting early gives up significant profit
- Let positions ride and accumulate on new entries only

## 12. Running mean for basket premium is vastly superior to EMA
- Online running mean (n += 1, mean += (x - mean) / n) converges to true structural premium
- With no denominator cap, the mean becomes very stable after 1000+ samples
- This improved P2 basket from 150k to 336k and P3 baskets from 106k to 192k
- With running mean, optimal basket entry threshold shifted from 25 to 35

## 13. IV scalping with mean edge adjustment is the biggest single options win
- Track running mean of (option_mid - model_fair) per option
- Adjust fair value by this mean edge: fair_adjusted = fair + mean_edge
- Then trade deviations from adjusted fair
- This captures structural model mispricing and trades the residual
- Improved P3 options by 184k and OOS by 14k (not overfit!)
- The key insight: the vol smile model has a time-varying bias, and the mean edge captures it

## 11. Vol smile base IV was underestimated
- Original Frankfurt coefficients had base IV = 0.149
- Adding +0.016 offset (base = 0.165) improved P3 options by 100k+
- The market-implied vol was consistently above the smile fit
- This is likely because the smile was fitted on historical data, but realized vol was higher
- The optimal offset (+0.016) was found by grid search: +0.015=314k, +0.016=316k, +0.017=314k

## 14. Mean edge also fixes near-expiry pricing
- Previously, day 4 (near expiry) options were losing -80k due to vol smile mispricing
- With mean edge adjustment, day 4 now makes +363k — the running mean corrects for expiry distortion
- This removed the need for any position cap or expiry guard

## 15. Underlyings must NOT be traded directly
- VOLCANIC_ROCK dynamic MM: composite dropped from 508k to 32k
- COCONUT dynamic MM: P2 options went from +456k to -56k  
- The underlying position interferes with options pricing and fills
- Key insight: for options underlyings, keep them as pure reference prices only

## 16. COCONUT edge threshold scales with max_take
- With max_take=1, optimal edge is 5.0 (up from 2.0 with max_take=20)
- Smaller takes + wider edge = high-conviction, best-fill-only trades
- This is analogous to "be picky when you can only take 1 contract"

## 9. COCONUT_COUPON: max_take=1 is optimal
- Reducing max_take from 20 to 1 improved P2 options from 420k to 474k
- Only taking the single best-priced contract per tick avoids adverse fills
- The MM resting orders (spread=1%, qty=15) handle larger position building passively
- This is counterintuitive but consistent: smaller takes = better average fills

## 10. Basket entry threshold 25 with no exit is the sweet spot
- Lowering basket entry from 50 to 25 dramatically improved both P3 and P2
- Removing exit logic (let positions ride) was the key enabler — without it, low thresholds cause losses
- The slow premium EMA (alpha=0.05) provides the structural mean, deviations > 25 are high-conviction

## 7. SQUID_INK profits come from insider (Olivia) signals
- Despite being "skipped" as a product archetype, SQUID_INK makes +15k from Olivia following
- The insider system trades it because archetype="skip" is in the insider follow list
- Direct mean-reversion trading SQUID_INK loses money (-8k in R1)
