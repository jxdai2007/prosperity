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

## 7. SQUID_INK profits come from insider (Olivia) signals
- Despite being "skipped" as a product archetype, SQUID_INK makes +15k from Olivia following
- The insider system trades it because archetype="skip" is in the insider follow list
- Direct mean-reversion trading SQUID_INK loses money (-8k in R1)
