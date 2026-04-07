# Strategy Insights for P4

## 1. P2 COCONUT_COUPON: Fixed sigma works great
- sigma=0.194, T=245/365, edge threshold=2 yields 421k profit
- Fixed vol is better than smoothed IV for long-dated options with stable vol
- Key: the 9th-place P2 reference used exactly this approach
- Aggressive qty (20 per take, 15 per MM) works because limit is 600
