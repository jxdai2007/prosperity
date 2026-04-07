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
