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

## 17. Volume-weighted mid (wmid) improves basket component and option pricing
- wmid = (best_bid * ask_vol + best_ask * bid_vol) / total_vol
- Helps for basket components: +500 composite
- Helps for option mid: +1.7k composite (better edge estimation)
- Does NOT help for: fixed MM (pegged products), dynamic MM, options underlying
- The volume imbalance in components/options gives useful directional information

## 18. Rhianna is a reliable ROSES insider, Vladimir/Remy are NOT reliable
- Rhianna/Rihanna fast-follow on ROSES: +19k P2 basket
- Vladimir/Remy fast-follow on CHOCOLATE: -163k (catastrophic)
- Only use name-specific insiders when you have evidence they work
- Product-specific insider mapping is crucial — not all insiders work on all products

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
- Direct mean-reversion trading SQUID_INK loses money (-30k in R1, -130k in R5)

## 19. Vol smile base IV was STILL underestimated after first calibration
- Original +0.016 offset brought base IV to 0.165, but optimal is +0.027 (base = 0.176)
- With mean-edge adjustment, higher base IV + running mean correction captures market vol better
- This improved P3 options from 632k to 836k, P3 full from 933k to 1.09M
- The improvement held on OOS (32k → 34k), confirming not overfit

## 20. Vol smile quadratic coefficient overestimated
- Original Frankfurt coefficient 0.274 was too steep — options at extreme strikes overpriced
- Optimal quadratic is 0.18 (34% lower), giving a flatter smile
- This improved P3 full from 1.04M to 1.09M, hardmode crossed 1M
- The interaction with mean-edge is key: flatter smile + running mean correction = better pricing

## 21. Options MM inventory skew 0.9 is optimal (not 0.5)
- Higher skew (0.9) means MM prices shift more aggressively against inventory
- This reduces time spent at large positions (which are expensive near expiry)
- Must be P3-specific: P2 COCONUT_COUPON is optimal at 0.5 (different dynamics)

## 22. P2 GIFT_BASKET threshold=50 (vs P3=35)
- P2 and P3 baskets have different premium dynamics
- GIFT_BASKET (4C+6S+1R) has wider premium swings → higher threshold reduces false entries
- Per-basket thresholds add +14k to P2 basket with zero P3 impact

## 23. Component leg trading DESTROYS basket arb
- Buying/selling components alongside basket arb lost 150-180k
- Components don't move inverse to basket premium — the premium is structural
- Frankfurt's 50% hedge worked in their framework but not ours (different position management)

## 24. MACARONS conversion still loses money
- The Frankfurt "taker bot at int(externalBid + 0.5)" approach lost money in backtester
- Conversion costs (transport + tariffs) exceed any achievable sell price
- Keep MACARONS disabled

## 25. Options edge threshold: 0.5 is optimal for high-vega strikes
- Was 0.3 (too aggressive, taking marginally mispriced options)
- 0.5 reduces adverse selection on ITM/ATM options with high vega
- Low-vega threshold (0.8) has zero effect — all P3 options have high enough vega

## 27. Order prioritization in position validation is a structural win (+4k composite)
- Sort orders by profitability before clipping at position limits
- Buys sorted by ascending price (cheapest first), sells by descending price
- When multiple strategies generate orders for same product (taking + MM + insider),
  the order matters for which survive clipping
- Improved P3 MM by 6.4k and P2 MM by 5.5k — the cheapest buys and highest sells get priority
- This is a free structural improvement that works across all products

## 26. P2 COCONUT_COUPON sigma=0.194 is a SHARP optimum
- ±0.001 causes 20-46k drops, ±0.004 causes 200k+ drops
- Never tune this without extreme precision — it's the most sensitive parameter
