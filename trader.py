"""
IMC Prosperity Trading Bot - Compatible with both P2 and P3 backtesters.
Strategies: Market Making (fixed/dynamic), Basket Arb, Options, Conversion, Insider Detection.
"""
import json
import math
import os
from statistics import NormalDist
from datamodel import Order, OrderDepth, TradingState, Trade, Observation, Listing, ProsperityEncoder, Symbol

# ============================================================
# SECTION 1: CONFIGURATION (agent tunes these values)
# ============================================================

POSITION_LIMITS = {
    # P3 products
    "RAINFOREST_RESIN": 50, "KELP": 50, "SQUID_INK": 50,
    "CROISSANTS": 250, "JAMS": 350, "DJEMBES": 60,
    "PICNIC_BASKET1": 60, "PICNIC_BASKET2": 100,
    "VOLCANIC_ROCK": 400,
    "VOLCANIC_ROCK_VOUCHER_9500": 200, "VOLCANIC_ROCK_VOUCHER_9750": 200,
    "VOLCANIC_ROCK_VOUCHER_10000": 200, "VOLCANIC_ROCK_VOUCHER_10250": 200,
    "VOLCANIC_ROCK_VOUCHER_10500": 200,
    "MAGNIFICENT_MACARONS": 75,
    # P2 products
    "AMETHYSTS": 20, "STARFRUIT": 20,
    "CHOCOLATE": 250, "STRAWBERRIES": 350, "ROSES": 60,
    "GIFT_BASKET": 60,
    "COCONUT": 300, "COCONUT_COUPON": 600,
    "ORCHIDS": 100,
}

BASKET_COMPOSITIONS = {
    "PICNIC_BASKET1": {"CROISSANTS": 6, "JAMS": 3, "DJEMBES": 1},
    "PICNIC_BASKET2": {"CROISSANTS": 4, "JAMS": 2},
    "GIFT_BASKET":    {"CHOCOLATE": 4, "STRAWBERRIES": 6, "ROSES": 1},
}

# Products that are basket components -- do NOT independently trade these
BASKET_COMPONENTS = {"CROISSANTS", "JAMS", "DJEMBES", "CHOCOLATE", "STRAWBERRIES", "ROSES"}

# Options underlying -- do NOT market-make directly (too risky at high limits)
OPTIONS_UNDERLYINGS = {"VOLCANIC_ROCK", "COCONUT"}

OPTIONS_CONFIG = {
    "VOLCANIC_ROCK_VOUCHER_9500":  {"underlying": "VOLCANIC_ROCK", "strike": 9500},
    "VOLCANIC_ROCK_VOUCHER_9750":  {"underlying": "VOLCANIC_ROCK", "strike": 9750},
    "VOLCANIC_ROCK_VOUCHER_10000": {"underlying": "VOLCANIC_ROCK", "strike": 10000},
    "VOLCANIC_ROCK_VOUCHER_10250": {"underlying": "VOLCANIC_ROCK", "strike": 10250},
    "VOLCANIC_ROCK_VOUCHER_10500": {"underlying": "VOLCANIC_ROCK", "strike": 10500},
    "COCONUT_COUPON": {"underlying": "COCONUT", "strike": 10000},
}

FIXED_FAIR_VALUES = {
    "RAINFOREST_RESIN": 10000,
    "AMETHYSTS": 10000,
}

CONVERSION_PRODUCTS = {"ORCHIDS"}  # MACARONS conversion loses money, disabled
INSIDER_EXCLUDE = {"MAGNIFICENT_MACARONS", "ORCHIDS", "JAMS", "CHOCOLATE", "STRAWBERRIES"}  # Products where insider following loses money

# Strategy parameters (agent tunes these)
MM_FIXED_SPREAD = 2          # half-spread for fixed-value market making
MM_DYNAMIC_SPREAD = 2        # half-spread for dynamic market making
MM_DYNAMIC_EMA_ALPHA = 0.15  # EMA smoothing for dynamic fair value
BASKET_ENTRY_THRESHOLD = 35  # premium deviation to enter basket arb
BASKET_EXIT_THRESHOLD = 10   # (unused - no exit logic)
OPTIONS_EDGE_THRESHOLD = 4.0 # min edge to trade options
INSIDER_THRESHOLD = 0.70     # accuracy threshold to follow an insider
INSIDER_MIN_TRADES = 7       # min trades before trusting insider score
INSIDER_WINDOW = 50          # rolling window for insider scoring
CONVERSION_MAX = 10          # max conversion per tick

DEFAULT_LIMIT = 20           # conservative default for unknown products

# ============================================================
# SECTION 2: UTILITY FUNCTIONS
# ============================================================

def get_mid(od: OrderDepth) -> float:
    if not od.buy_orders or not od.sell_orders:
        if od.buy_orders:
            return float(max(od.buy_orders.keys()))
        if od.sell_orders:
            return float(min(od.sell_orders.keys()))
        return 0.0
    return (max(od.buy_orders.keys()) + min(od.sell_orders.keys())) / 2.0

def get_wmid(od: OrderDepth) -> float:
    """Volume-weighted mid price using top of book"""
    if not od.buy_orders or not od.sell_orders:
        return get_mid(od)
    best_bid = max(od.buy_orders.keys())
    best_ask = min(od.sell_orders.keys())
    bid_vol = od.buy_orders[best_bid]
    ask_vol = -od.sell_orders[best_ask]
    total = bid_vol + ask_vol
    if total == 0:
        return (best_bid + best_ask) / 2.0
    # More volume on bid side → mid shifts toward ask (imbalance)
    return (best_bid * ask_vol + best_ask * bid_vol) / total

def get_best_bid(od: OrderDepth):
    if not od.buy_orders:
        return 0, 0
    p = max(od.buy_orders.keys())
    return p, od.buy_orders[p]

def get_best_ask(od: OrderDepth):
    if not od.sell_orders:
        return 0, 0
    p = min(od.sell_orders.keys())
    return p, od.sell_orders[p]  # negative volume

def clamp(val, lo, hi):
    return max(lo, min(hi, val))

# ============================================================
# SECTION 3: BLACK-SCHOLES
# ============================================================

_norm = NormalDist(0, 1)

def bs_call_price(S, K, T, sigma):
    if T <= 0 or sigma <= 0 or S <= 0:
        return max(0.0, S - K)
    d1 = (math.log(S / K) + 0.5 * sigma * sigma * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return S * _norm.cdf(d1) - K * _norm.cdf(d2)

def bs_delta(S, K, T, sigma):
    if T <= 0 or sigma <= 0 or S <= 0:
        return 1.0 if S > K else 0.0
    d1 = (math.log(S / K) + 0.5 * sigma * sigma * T) / (sigma * math.sqrt(T))
    return _norm.cdf(d1)

def bs_vega(S, K, T, sigma):
    if T <= 0 or sigma <= 0 or S <= 0:
        return 0.0
    d1 = (math.log(S / K) + 0.5 * sigma * sigma * T) / (sigma * math.sqrt(T))
    return S * math.sqrt(T) * _norm.pdf(d1)

def implied_vol(market_price, S, K, T, initial_guess=0.3, tol=1e-6, max_iter=50):
    if T <= 0 or S <= 0:
        return initial_guess
    intrinsic = max(0.0, S - K)
    if market_price <= intrinsic + 0.01:
        return 0.01
    sigma = initial_guess
    for _ in range(max_iter):
        price = bs_call_price(S, K, T, sigma)
        v = bs_vega(S, K, T, sigma)
        if v < 1e-10:
            break
        sigma = sigma - (price - market_price) / v
        sigma = max(0.01, min(5.0, sigma))
        if abs(price - market_price) < tol:
            break
    return sigma

# ============================================================
# SECTION 4: TRADER CLASS
# ============================================================

class Trader:
    def __init__(self):
        self.ema = {}
        self.classified = {}
        self.iv_estimates = {}

    # ----------------------------------------------------------
    # Product classification
    # ----------------------------------------------------------
    def classify_product(self, product: str) -> str:
        if product in self.classified:
            return self.classified[product]

        archetype = "skip"  # default: don't trade unknown products
        if product in FIXED_FAIR_VALUES:
            archetype = "fixed"
        elif product in BASKET_COMPOSITIONS:
            archetype = "basket"
        elif product in OPTIONS_CONFIG:
            archetype = "option"
        elif product in CONVERSION_PRODUCTS:
            archetype = "conversion"
        elif product in BASKET_COMPONENTS:
            archetype = "component"  # don't trade independently
        elif product in OPTIONS_UNDERLYINGS:
            archetype = "underlying"  # don't trade directly
        elif "BASKET" in product or "GIFT" in product:
            archetype = "basket"
        elif "VOUCHER" in product or "COUPON" in product:
            archetype = "option"
        elif "RESIN" in product or "AMETHYST" in product:
            archetype = "fixed"
        elif product in ("KELP", "STARFRUIT"):
            archetype = "dynamic"
        elif product in ("SQUID_INK",):
            archetype = "skip"  # too volatile, skip for now
        else:
            archetype = "skip"

        self.classified[product] = archetype
        return archetype

    def get_limit(self, product: str) -> int:
        return POSITION_LIMITS.get(product, DEFAULT_LIMIT)

    def get_position(self, product: str, state: TradingState) -> int:
        return state.position.get(product, 0)

    # ----------------------------------------------------------
    # Strategy: Fixed Fair Value Market Making
    # ----------------------------------------------------------
    def mm_fixed(self, product: str, state: TradingState) -> list:
        orders = []
        if product not in state.order_depths:
            return orders

        od = state.order_depths[product]
        fixed_fair = FIXED_FAIR_VALUES.get(product, 10000)
        mid = get_mid(od)

        # Use weighted combination of fixed fair and mid for robustness
        fair = fixed_fair  # pure fixed value (RESIN/AMETHYSTS are pegged)
        limit = self.get_limit(product)
        pos = self.get_position(product, state)

        # Take mispriced orders: buy BELOW fair, sell ABOVE fair (strict edge only)
        for ask_price in sorted(od.sell_orders.keys()):
            if ask_price < fair:
                ask_vol = -od.sell_orders[ask_price]
                can_buy = limit - pos
                qty = min(ask_vol, can_buy)
                if qty > 0:
                    orders.append(Order(product, ask_price, qty))
                    pos += qty

        for bid_price in sorted(od.buy_orders.keys(), reverse=True):
            if bid_price > fair:
                bid_vol = od.buy_orders[bid_price]
                can_sell = limit + pos
                qty = min(bid_vol, can_sell)
                if qty > 0:
                    orders.append(Order(product, bid_price, -qty))
                    pos -= qty

        # Resting orders at three levels: tight(1), medium(2), wide(3)
        buy_qty = limit - pos
        sell_qty = limit + pos

        # Level 1: fair ± 1 (tightest, small qty)
        l1_bq = max(1, buy_qty // 3)
        l1_sq = max(1, sell_qty // 3)
        if buy_qty > 0:
            orders.append(Order(product, int(fair - 1), l1_bq))
            buy_qty -= l1_bq
        if sell_qty > 0:
            orders.append(Order(product, int(fair + 1), -l1_sq))
            sell_qty -= l1_sq

        # Level 2: fair ± 2
        l2_bq = max(1, buy_qty // 2) if buy_qty > 0 else 0
        l2_sq = max(1, sell_qty // 2) if sell_qty > 0 else 0
        if l2_bq > 0:
            orders.append(Order(product, int(fair - 2), l2_bq))
            buy_qty -= l2_bq
        if l2_sq > 0:
            orders.append(Order(product, int(fair + 2), -l2_sq))
            sell_qty -= l2_sq

        # Level 3: fair ± 3 (widest, remaining qty)
        if buy_qty > 0:
            orders.append(Order(product, int(fair - 3), buy_qty))
        if sell_qty > 0:
            orders.append(Order(product, int(fair + 3), -sell_qty))

        return orders

    # ----------------------------------------------------------
    # Strategy: Dynamic (Mean-Reverting) Market Making
    # ----------------------------------------------------------
    def mm_dynamic(self, product: str, state: TradingState, saved: dict) -> list:
        orders = []
        if product not in state.order_depths:
            return orders

        od = state.order_depths[product]
        mid = get_mid(od)
        if mid == 0:
            return orders

        # Order Flow Imbalance: track bid/ask volume changes as directional signal
        best_bid, bid_vol = get_best_bid(od)
        best_ask, ask_vol = get_best_ask(od)
        ask_vol = -ask_vol if ask_vol < 0 else ask_vol
        ofi_key = f"ofi_{product}"
        prev_bid_vol = saved.get(f"bv_{product}", bid_vol)
        prev_ask_vol = saved.get(f"av_{product}", ask_vol)
        saved[f"bv_{product}"] = bid_vol
        saved[f"av_{product}"] = ask_vol
        ofi = (bid_vol - prev_bid_vol) - (ask_vol - prev_ask_vol)
        # EMA of OFI for smoothing
        ofi_alpha = 0.3
        prev_ofi = saved.get(ofi_key, 0)
        ofi_ema = ofi_alpha * ofi + (1 - ofi_alpha) * prev_ofi
        saved[ofi_key] = ofi_ema

        # Update EMA with OFI adjustment
        alpha = MM_DYNAMIC_EMA_ALPHA
        key = f"ema_{product}"
        prev_ema = saved.get(key, mid)
        ema = alpha * mid + (1 - alpha) * prev_ema
        saved[key] = ema
        self.ema[product] = ema

        # OFI adjusts fair value slightly: positive flow → price going up
        ofi_mult = 0.02 if product == "KELP" else 0.01
        ofi_adjustment = ofi_ema * ofi_mult
        fair = ema + ofi_adjustment
        limit = self.get_limit(product)
        pos = self.get_position(product, state)
        spread = MM_DYNAMIC_SPREAD  # all dynamic products use spread=2 (dual-level handles tight)

        # Take mispriced orders
        for ask_price in sorted(od.sell_orders.keys()):
            if ask_price < fair - 0.5:
                ask_vol = -od.sell_orders[ask_price]
                can_buy = limit - pos
                qty = min(ask_vol, can_buy)
                if qty > 0:
                    orders.append(Order(product, ask_price, qty))
                    pos += qty

        for bid_price in sorted(od.buy_orders.keys(), reverse=True):
            if bid_price > fair + 0.5:
                bid_vol = od.buy_orders[bid_price]
                can_sell = limit + pos
                qty = min(bid_vol, can_sell)
                if qty > 0:
                    orders.append(Order(product, bid_price, -qty))
                    pos -= qty

        # Inventory skew (stronger to clear positions faster)
        skew = -pos * 0.7 / limit * spread if limit > 0 else 0
        buy_price = int(round(fair - spread + skew))
        sell_price = int(round(fair + spread + skew))

        if buy_price >= sell_price:
            buy_price = int(fair) - 1
            sell_price = int(fair) + 1

        buy_qty = limit - pos
        sell_qty = limit + pos

        if spread >= 2 and buy_qty > 1 and sell_qty > 1:
            # Two levels: tight (half qty at spread-1) + wide (half at spread)
            tight_bq = buy_qty // 2
            tight_sq = sell_qty // 2
            tight_buy = int(round(fair - (spread - 1) + skew))
            tight_sell = int(round(fair + (spread - 1) + skew))
            if tight_buy < tight_sell:
                orders.append(Order(product, tight_buy, tight_bq))
                orders.append(Order(product, tight_sell, -tight_sq))
                buy_qty -= tight_bq
                sell_qty -= tight_sq

        if buy_qty > 0:
            orders.append(Order(product, buy_price, buy_qty))
        if sell_qty > 0:
            orders.append(Order(product, sell_price, -sell_qty))

        return orders

    # ----------------------------------------------------------
    # Strategy: Basket/Statistical Arbitrage
    # ----------------------------------------------------------
    def basket_arb(self, basket: str, state: TradingState, saved: dict) -> dict:
        all_orders = {}
        if basket not in BASKET_COMPOSITIONS:
            return all_orders

        comp = BASKET_COMPOSITIONS[basket]

        if basket not in state.order_depths:
            return all_orders
        for c in comp:
            if c not in state.order_depths:
                return all_orders

        # Calculate component fair value
        comp_fair = 0.0
        for c, weight in comp.items():
            c_mid = get_wmid(state.order_depths[c])
            if c_mid == 0:
                return all_orders
            comp_fair += weight * c_mid

        basket_mid = get_mid(state.order_depths[basket])
        if basket_mid == 0:
            return all_orders

        premium = basket_mid - comp_fair

        # Track premium with running mean (Frankfurt approach — converges to true structural premium)
        pkey = f"basket_prem_{basket}"
        nkey = f"basket_n_{basket}"
        n = saved.get(nkey, 0) + 1
        saved[nkey] = n
        if n == 1:
            saved[pkey] = premium
        else:
            # Online mean update, capped denominator for stability
            denom = n  # no cap, true running mean
            saved[pkey] = saved.get(pkey, premium) + (premium - saved.get(pkey, premium)) / denom
        mean_prem = saved[pkey]

        deviation = premium - mean_prem
        entry_thr = 50 if basket == "GIFT_BASKET" else BASKET_ENTRY_THRESHOLD

        basket_limit = self.get_limit(basket)
        basket_pos = self.get_position(basket, state)
        basket_od = state.order_depths[basket]
        basket_orders = []
        max_qty = 3  # optimal with running mean

        if deviation > entry_thr:
            # Basket expensive -> sell basket aggressively
            for bid_price in sorted(basket_od.buy_orders.keys(), reverse=True):
                bid_vol = basket_od.buy_orders[bid_price]
                can_sell = basket_limit + basket_pos
                qty = min(bid_vol, can_sell, max_qty)
                if qty > 0:
                    basket_orders.append(Order(basket, bid_price, -qty))
                    basket_pos -= qty
                    max_qty -= qty
                if max_qty <= 0:
                    break

        elif deviation < -entry_thr:
            # Basket cheap -> buy basket aggressively
            for ask_price in sorted(basket_od.sell_orders.keys()):
                ask_vol = -basket_od.sell_orders[ask_price]
                can_buy = basket_limit - basket_pos
                qty = min(ask_vol, can_buy, max_qty)
                if qty > 0:
                    basket_orders.append(Order(basket, ask_price, qty))
                    basket_pos += qty
                    max_qty -= qty
                if max_qty <= 0:
                    break

        # Also place resting orders at entry threshold price (capture deviations)
        if True:
            rest_price_buy = int(round(comp_fair + mean_prem - entry_thr))
            rest_price_sell = int(round(comp_fair + mean_prem + entry_thr))
            can_buy = basket_limit - basket_pos
            can_sell = basket_limit + basket_pos
            if can_buy > 0 and rest_price_buy > 0:
                basket_orders.append(Order(basket, rest_price_buy, can_buy))
            if can_sell > 0 and rest_price_sell > 0:
                basket_orders.append(Order(basket, rest_price_sell, -can_sell))

        if basket_orders:
            all_orders[basket] = basket_orders

        return all_orders

    # ----------------------------------------------------------
    # Strategy: Options (Volatility Trading)
    # ----------------------------------------------------------
    def options_trade(self, product: str, state: TradingState, saved: dict) -> list:
        orders = []
        if product not in OPTIONS_CONFIG:
            return orders
        if product not in state.order_depths:
            return orders

        cfg = OPTIONS_CONFIG[product]
        underlying = cfg["underlying"]
        strike = cfg["strike"]

        if underlying not in state.order_depths:
            return orders

        S = get_mid(state.order_depths[underlying])
        if S <= 0:
            return orders

        option_mid = get_wmid(state.order_depths[product])
        if option_mid <= 0:
            return orders

        # Calculate time to expiry
        day_str = os.environ.get("PROSPERITY3BT_DAY", "")
        p2_day_str = os.environ.get("PROSPERITY2BT_DAY", "")

        if underlying == "COCONUT":
            # P2 long-dated options: T=245/365, sigma~0.194
            if p2_day_str and p2_day_str.isdigit():
                current_day = int(p2_day_str)
            else:
                current_day = 1
            T = 245.0 / 365.0  # fixed TTE for P2 coconut coupon
        else:
            # P3 volcanic rock options
            if day_str and day_str.isdigit():
                current_day = int(day_str)
            else:
                current_day = 3
            ts = state.timestamp
            time_in_day = ts / 1_000_000
            total_cal_days = 7 - current_day - time_in_day
            T = max(total_cal_days / 365.0, 1e-6)

        # Calculate implied vol / fair value
        if underlying == "COCONUT":
            # P2: use fixed sigma for stable pricing
            fixed_sigma = 0.194
            fair = bs_call_price(S, strike, T, fixed_sigma)
            edge_thr = 5.0  # optimal edge for P2 coconut coupon
        else:
            # P3: use fitted vol smile (FrankfurtHedgehogs approach)
            # coeffs from fitted volatility smile: IV = f(log(K/S)/sqrt(T))
            m_t_k = math.log(strike / S) / math.sqrt(T) if T > 1e-8 else 0
            vol_smile_iv = 0.17576677 + 0.01007566 * m_t_k + 0.18 * m_t_k * m_t_k
            vol_smile_iv = max(0.05, min(1.0, vol_smile_iv))
            fair = bs_call_price(S, strike, T, vol_smile_iv)
            # Edge threshold for P3 options
            edge_thr = 0.5

        if fair <= 0.5:
            return orders

        edge = option_mid - fair
        limit = self.get_limit(product)
        if underlying != "COCONUT":
            pass  # no cap needed with mean edge pricing

            # IV scalping: track running mean of edge deviation
            ekey = f"opt_edge_{product}"
            enkey = f"opt_edge_n_{product}"
            en = saved.get(enkey, 0) + 1
            saved[enkey] = en
            if en == 1:
                saved[ekey] = edge
            else:
                saved[ekey] = saved.get(ekey, edge) + (edge - saved.get(ekey, edge)) / en
            mean_edge = saved[ekey]
            # Adjust fair to include the mean edge (structural mispricing)
            fair = fair + mean_edge
            edge = option_mid - fair

        pos = self.get_position(product, state)
        od = state.order_depths[product]

        # Take mispriced orders aggressively
        max_take = 1 if underlying == "COCONUT" else limit  # P3: go big, unhedged
        if edge > edge_thr:
            # Option overpriced, sell
            for bid_price in sorted(od.buy_orders.keys(), reverse=True):
                if bid_price > fair:
                    bid_vol = od.buy_orders[bid_price]
                    can_sell = limit + pos
                    qty = min(bid_vol, can_sell, max_take)
                    if qty > 0:
                        orders.append(Order(product, bid_price, -qty))
                        pos -= qty
        elif edge < -edge_thr:
            # Option underpriced, buy
            for ask_price in sorted(od.sell_orders.keys()):
                if ask_price < fair:
                    ask_vol = -od.sell_orders[ask_price]
                    can_buy = limit - pos
                    qty = min(ask_vol, can_buy, max_take)
                    if qty > 0:
                        orders.append(Order(product, ask_price, qty))
                        pos += qty

        # Market making around fair value
        if underlying == "COCONUT":
            spread = max(3, int(fair * 0.01))
            max_mm_qty = 15
        else:
            # P3: strike-dependent spread — tighter for ATM, wider for OTM
            delta = bs_delta(S, strike, T, vol_smile_iv)
            liquidity = 4.0 * delta * (1.0 - delta)  # peaks at 1.0 for ATM, 0 for deep OTM
            base_spread = max(1, int(fair * 0.01))
            spread = max(1, int(base_spread * (1.5 - 0.5 * liquidity)))  # ATM: 1x, OTM: 1.5x
            max_mm_qty = 25
        # Position skew: shift MM prices to reduce inventory
        skew_factor = 0.9 if underlying != "COCONUT" else 0.5
        pos_skew = -pos / limit * spread * skew_factor if limit > 0 else 0
        buy_price = int(round(fair - spread + pos_skew))
        sell_price = int(round(fair + spread + pos_skew))
        if buy_price >= sell_price:
            buy_price = int(fair) - 1
            sell_price = int(fair) + 1
        buy_qty = min(limit - pos, max_mm_qty)
        sell_qty = min(limit + pos, max_mm_qty)
        if buy_qty > 0 and buy_price > 0:
            orders.append(Order(product, buy_price, buy_qty))
        if sell_qty > 0 and sell_price > 0:
            orders.append(Order(product, sell_price, -sell_qty))

        # Second level: wider spread to capture large moves (P3 only)
        if underlying != "COCONUT":
            wide_spread = max(2, int(fair * 0.02))
            wide_buy = int(round(fair - wide_spread + pos_skew))
            wide_sell = int(round(fair + wide_spread + pos_skew))
            wide_qty = min(limit - pos - buy_qty, max_mm_qty)
            wide_sell_qty = min(limit + pos - sell_qty, max_mm_qty)
            if wide_qty > 0 and wide_buy > 0 and wide_buy < buy_price:
                orders.append(Order(product, wide_buy, wide_qty))
            if wide_sell_qty > 0 and wide_sell > 0 and wide_sell > sell_price:
                orders.append(Order(product, wide_sell, -wide_sell_qty))

        return orders

    # ----------------------------------------------------------
    # Strategy: Conversion Arbitrage
    # ----------------------------------------------------------
    def conversion_arb(self, product: str, state: TradingState) -> tuple:
        orders = []
        conversions = 0

        if product not in state.order_depths:
            return orders, conversions

        obs = state.observations
        if obs is None:
            return orders, conversions
        if not hasattr(obs, 'conversionObservations') or obs.conversionObservations is None:
            return orders, conversions
        if product not in obs.conversionObservations:
            return orders, conversions

        conv = obs.conversionObservations[product]
        ext_bid = conv.bidPrice
        ext_ask = conv.askPrice
        transport = conv.transportFees
        export_tariff = conv.exportTariff
        import_tariff = conv.importTariff

        od = state.order_depths[product]
        limit = self.get_limit(product)
        pos = self.get_position(product, state)

        ext_buy_cost = ext_ask + transport + import_tariff
        ext_sell_rev = ext_bid - transport - export_tariff

        # Sell locally if price > external buy cost (import arb)
        for bid_price in sorted(od.buy_orders.keys(), reverse=True):
            if bid_price > ext_buy_cost + 1:
                bid_vol = od.buy_orders[bid_price]
                can_sell = limit + pos
                qty = min(bid_vol, can_sell)
                if qty > 0:
                    orders.append(Order(product, bid_price, -qty))
                    pos -= qty
            else:
                break

        # Buy locally if price < external sell revenue (export arb)
        for ask_price in sorted(od.sell_orders.keys()):
            if ask_price < ext_sell_rev - 1:
                ask_vol = -od.sell_orders[ask_price]
                can_buy = limit - pos
                qty = min(ask_vol, can_buy)
                if qty > 0:
                    orders.append(Order(product, ask_price, qty))
                    pos += qty
            else:
                break

        # Convert position back toward zero
        new_pos = pos
        for o in orders:
            new_pos += o.quantity

        if new_pos < 0:
            conversions = min(-new_pos, CONVERSION_MAX)
        elif new_pos > 0:
            conversions = -min(new_pos, CONVERSION_MAX)

        return orders, conversions

    # ----------------------------------------------------------
    # Insider Detection
    # ----------------------------------------------------------
    # Known insiders: map to products they're reliable on
    # P3: Olivia is reliable across products
    # P2: Don't fast-follow P2 insiders — their signals work differently
    KNOWN_INSIDERS = {"Olivia"}
    # Product-specific insiders (only follow on these specific products)
    PRODUCT_INSIDERS = {
        "ROSES": {"Rhianna", "Rihanna"},
    }

    def detect_insider(self, state: TradingState, saved: dict) -> dict:
        signals = {}

        # Fast path: check for known insider trades this tick
        if state.market_trades:
            for product, trades in state.market_trades.items():
                if product not in state.order_depths:
                    continue
                product_insiders = self.PRODUCT_INSIDERS.get(product, set())
                for trade in trades:
                    buyer = trade.buyer or ""
                    seller = trade.seller or ""
                    if buyer == "SUBMISSION" or seller == "SUBMISSION":
                        continue
                    # Known insiders: follow immediately
                    if buyer in self.KNOWN_INSIDERS or buyer in product_insiders:
                        if product not in signals or True:
                            signals[product] = (1, 0.9)  # high confidence buy
                    elif seller in self.KNOWN_INSIDERS or seller in product_insiders:
                        if product not in signals or True:
                            signals[product] = (-1, 0.9)  # high confidence sell
        insider_data = saved.get("insider", {})

        # Score previous predictions
        for product in state.order_depths:
            mid = get_mid(state.order_depths[product])
            if mid == 0:
                continue
            for tname, tdata in insider_data.items():
                if product in tdata:
                    pdata = tdata[product]
                    if "la" in pdata and "lp" in pdata:
                        last_p = pdata["lp"]
                        if pdata["la"] == "b" and mid > last_p:
                            pdata["c"] = pdata.get("c", 0) + 1
                        elif pdata["la"] == "s" and mid < last_p:
                            pdata["c"] = pdata.get("c", 0) + 1
                        pdata["t"] = pdata.get("t", 0) + 1
                        if pdata["t"] > INSIDER_WINDOW:
                            ratio = pdata["c"] / pdata["t"]
                            pdata["c"] = int(ratio * INSIDER_WINDOW)
                            pdata["t"] = INSIDER_WINDOW
                        pdata.pop("la", None)
                        pdata.pop("lp", None)

        # Record new trades
        if state.market_trades:
            for product, trades in state.market_trades.items():
                mid = get_mid(state.order_depths.get(product, OrderDepth()))
                if mid == 0:
                    continue
                for trade in trades:
                    buyer = trade.buyer if trade.buyer else ""
                    seller = trade.seller if trade.seller else ""
                    if buyer == "SUBMISSION" or seller == "SUBMISSION":
                        continue

                    if buyer:
                        if buyer not in insider_data:
                            insider_data[buyer] = {}
                        if product not in insider_data[buyer]:
                            insider_data[buyer][product] = {"c": 0, "t": 0}
                        insider_data[buyer][product]["la"] = "b"
                        insider_data[buyer][product]["lp"] = trade.price

                    if seller:
                        if seller not in insider_data:
                            insider_data[seller] = {}
                        if product not in insider_data[seller]:
                            insider_data[seller][product] = {"c": 0, "t": 0}
                        insider_data[seller][product]["la"] = "s"
                        insider_data[seller][product]["lp"] = trade.price

        # Generate signals
        for tname, tdata in insider_data.items():
            for product, pdata in tdata.items():
                total = pdata.get("t", 0)
                correct = pdata.get("c", 0)
                if total >= INSIDER_MIN_TRADES:
                    accuracy = correct / total
                    if accuracy >= INSIDER_THRESHOLD:
                        last = pdata.get("la")
                        if last:
                            if product not in signals or accuracy > signals[product][1]:
                                direction = 1 if last == "b" else -1
                                signals[product] = (direction, accuracy)

        # Limit size
        if len(insider_data) > 80:
            scored = []
            for tname, tdata in insider_data.items():
                max_acc = 0
                for pdata in tdata.values():
                    t = pdata.get("t", 0)
                    c = pdata.get("c", 0)
                    if t > 0:
                        max_acc = max(max_acc, c / t)
                scored.append((max_acc, tname))
            scored.sort(reverse=True)
            keep = set(name for _, name in scored[:40])
            insider_data = {k: v for k, v in insider_data.items() if k in keep}

        saved["insider"] = insider_data
        return signals

    def apply_insider(self, product: str, direction: int, confidence: float,
                      state: TradingState) -> list:
        orders = []
        if product not in state.order_depths:
            return orders

        od = state.order_depths[product]
        limit = self.get_limit(product)
        pos = self.get_position(product, state)

        # High confidence (known insiders): go to full limit
        if confidence >= 0.85:
            target_frac = 1.0
        else:
            target_frac = min(0.8, (confidence - INSIDER_THRESHOLD) / (1.0 - INSIDER_THRESHOLD) + 0.2)
        target_pos = int(direction * limit * target_frac)
        needed = target_pos - pos

        if needed > 0:
            # Take all available liquidity
            for ask_price in sorted(od.sell_orders.keys()):
                ask_vol = -od.sell_orders[ask_price]
                qty = min(ask_vol, needed, limit - pos)
                if qty > 0:
                    orders.append(Order(product, ask_price, qty))
                    pos += qty
                    needed -= qty
                if needed <= 0:
                    break
            # Place resting order for remainder
            if needed > 0:
                best_ask = min(od.sell_orders.keys()) if od.sell_orders else 0
                if best_ask > 0:
                    orders.append(Order(product, best_ask, min(needed, limit - pos)))
        elif needed < 0:
            for bid_price in sorted(od.buy_orders.keys(), reverse=True):
                bid_vol = od.buy_orders[bid_price]
                qty = min(bid_vol, -needed, limit + pos)
                if qty > 0:
                    orders.append(Order(product, bid_price, -qty))
                    pos -= qty
                    needed += qty
                if needed >= 0:
                    break
            # Place resting order for remainder
            if needed < 0:
                best_bid = max(od.buy_orders.keys()) if od.buy_orders else 0
                if best_bid > 0:
                    orders.append(Order(product, best_bid, max(needed, -(limit + pos))))

        return orders

    # ----------------------------------------------------------
    # Main run method
    # ----------------------------------------------------------
    def run(self, state: TradingState):
        saved = {}
        if state.traderData and state.traderData != "":
            try:
                saved = json.loads(state.traderData)
            except (json.JSONDecodeError, TypeError):
                saved = {}

        result = {}
        conversions = 0

        products = list(state.order_depths.keys())
        for p in products:
            self.classify_product(p)

        # Detect insider signals
        insider_signals = {}
        try:
            insider_signals = self.detect_insider(state, saved)
        except Exception:
            pass

        # Run strategies per product
        for product in products:
            archetype = self.classify_product(product)

            try:
                if archetype == "fixed":
                    result[product] = self.mm_fixed(product, state)

                elif archetype == "dynamic":
                    result[product] = self.mm_dynamic(product, state, saved)

                elif archetype == "basket":
                    basket_orders = self.basket_arb(product, state, saved)
                    for p, ords in basket_orders.items():
                        if p not in result:
                            result[p] = []
                        result[p].extend(ords)

                elif archetype == "option":
                    result[product] = self.options_trade(product, state, saved)

                elif archetype == "conversion":
                    conv_orders, conv_count = self.conversion_arb(product, state)
                    result[product] = conv_orders
                    conversions += conv_count

                # component, underlying, skip -> do nothing

            except Exception:
                if product not in result:
                    result[product] = []

        # Cross-option spread arbitrage (P3 volcanic rock vouchers only)
        # If bull call spread (C(K1) - C(K2)) deviates from BS theoretical, arb it
        try:
            vr_strikes = sorted([p for p in products if "VOLCANIC_ROCK_VOUCHER" in p],
                                key=lambda p: OPTIONS_CONFIG[p]["strike"])
            if len(vr_strikes) >= 2 and "VOLCANIC_ROCK" in state.order_depths:
                S = get_mid(state.order_depths["VOLCANIC_ROCK"])
                if S > 0:
                    day_str = os.environ.get("PROSPERITY3BT_DAY", "")
                    current_day = int(day_str) if day_str and day_str.isdigit() else 3
                    ts = state.timestamp
                    time_in_day = ts / 1_000_000
                    T = max((7 - current_day - time_in_day) / 365.0, 1e-6)

                    for i in range(len(vr_strikes) - 1):
                        lo_p = vr_strikes[i]
                        hi_p = vr_strikes[i + 1]
                        if lo_p not in state.order_depths or hi_p not in state.order_depths:
                            continue

                        K_lo = OPTIONS_CONFIG[lo_p]["strike"]
                        K_hi = OPTIONS_CONFIG[hi_p]["strike"]

                        # Get mean-edge-adjusted fairs
                        m_lo = math.log(K_lo / S) / math.sqrt(T) if T > 1e-8 else 0
                        m_hi = math.log(K_hi / S) / math.sqrt(T) if T > 1e-8 else 0
                        iv_lo = max(0.05, 0.17576677 + 0.01007566 * m_lo + 0.18 * m_lo * m_lo)
                        iv_hi = max(0.05, 0.17576677 + 0.01007566 * m_hi + 0.18 * m_hi * m_hi)
                        fair_lo = bs_call_price(S, K_lo, T, iv_lo)
                        fair_hi = bs_call_price(S, K_hi, T, iv_hi)

                        # Adjust with mean edges
                        me_lo = saved.get(f"opt_edge_{lo_p}", 0)
                        me_hi = saved.get(f"opt_edge_{hi_p}", 0)
                        fair_lo += me_lo
                        fair_hi += me_hi

                        theo_spread = fair_lo - fair_hi  # should be positive

                        # Market spread
                        lo_od = state.order_depths[lo_p]
                        hi_od = state.order_depths[hi_p]
                        lo_mid = get_wmid(lo_od)
                        hi_mid = get_wmid(hi_od)
                        if lo_mid <= 0 or hi_mid <= 0:
                            continue
                        mkt_spread = lo_mid - hi_mid

                        spread_dev = mkt_spread - theo_spread
                        spread_thr = 2.0  # min deviation to trade

                        if abs(spread_dev) > spread_thr:
                            lo_limit = self.get_limit(lo_p)
                            hi_limit = self.get_limit(hi_p)
                            lo_pos = self.get_position(lo_p, state)
                            hi_pos = self.get_position(hi_p, state)
                            max_spread_qty = 30

                            if spread_dev > spread_thr:
                                # Market spread too wide: sell lo (overpriced), buy hi (underpriced)
                                for bp in sorted(lo_od.buy_orders.keys(), reverse=True):
                                    if bp > fair_lo:
                                        bv = lo_od.buy_orders[bp]
                                        qty = min(bv, lo_limit + lo_pos, max_spread_qty)
                                        if qty > 0:
                                            if lo_p not in result: result[lo_p] = []
                                            result[lo_p].append(Order(lo_p, bp, -qty))
                                            max_spread_qty -= qty
                                    if max_spread_qty <= 0: break
                                max_spread_qty = 30
                                for ap in sorted(hi_od.sell_orders.keys()):
                                    if ap < fair_hi:
                                        av = -hi_od.sell_orders[ap]
                                        qty = min(av, hi_limit - hi_pos, max_spread_qty)
                                        if qty > 0:
                                            if hi_p not in result: result[hi_p] = []
                                            result[hi_p].append(Order(hi_p, ap, qty))
                                            max_spread_qty -= qty
                                    if max_spread_qty <= 0: break

                            elif spread_dev < -spread_thr:
                                # Market spread too narrow: buy lo (underpriced), sell hi (overpriced)
                                for ap in sorted(lo_od.sell_orders.keys()):
                                    if ap < fair_lo:
                                        av = -lo_od.sell_orders[ap]
                                        qty = min(av, lo_limit - lo_pos, max_spread_qty)
                                        if qty > 0:
                                            if lo_p not in result: result[lo_p] = []
                                            result[lo_p].append(Order(lo_p, ap, qty))
                                            max_spread_qty -= qty
                                    if max_spread_qty <= 0: break
                                max_spread_qty = 30
                                for bp in sorted(hi_od.buy_orders.keys(), reverse=True):
                                    if bp > fair_hi:
                                        bv = hi_od.buy_orders[bp]
                                        qty = min(bv, hi_limit + hi_pos, max_spread_qty)
                                        if qty > 0:
                                            if hi_p not in result: result[hi_p] = []
                                            result[hi_p].append(Order(hi_p, bp, -qty))
                                            max_spread_qty -= qty
                                    if max_spread_qty <= 0: break
        except Exception:
            pass

        # Apply insider signals to tradeable products
        for product, (direction, confidence) in insider_signals.items():
            if product in state.order_depths:
                archetype = self.classify_product(product)
                if archetype in ("dynamic", "component", "skip") and product not in INSIDER_EXCLUDE:
                    try:
                        insider_orders = self.apply_insider(product, direction, confidence, state)
                        if insider_orders:
                            if product not in result:
                                result[product] = []
                            result[product].extend(insider_orders)
                    except Exception:
                        pass

        # Validate position limits
        for product in list(result.keys()):
            if not result[product]:
                continue
            limit = self.get_limit(product)
            pos = self.get_position(product, state)
            valid_orders = []
            buy_total = 0
            sell_total = 0
            # Prioritize best-priced orders: buys at lowest price, sells at highest price
            buy_orders_sorted = sorted([o for o in result[product] if o.quantity > 0], key=lambda o: o.price)
            sell_orders_sorted = sorted([o for o in result[product] if o.quantity < 0], key=lambda o: -o.price)
            for order in buy_orders_sorted + sell_orders_sorted:
                if order.quantity > 0:
                    if pos + buy_total + order.quantity <= limit:
                        valid_orders.append(order)
                        buy_total += order.quantity
                    else:
                        remaining = limit - pos - buy_total
                        if remaining > 0:
                            valid_orders.append(Order(product, order.price, remaining))
                            buy_total += remaining
                elif order.quantity < 0:
                    if pos - sell_total + order.quantity >= -limit:
                        valid_orders.append(order)
                        sell_total -= order.quantity
                    else:
                        remaining = limit + pos - sell_total
                        if remaining > 0:
                            valid_orders.append(Order(product, order.price, -remaining))
                            sell_total += remaining
            result[product] = valid_orders

        # Ensure all products have entries
        for product in products:
            if product not in result:
                result[product] = []

        # Serialize state
        try:
            trader_data = json.dumps(saved)
        except (TypeError, ValueError):
            trader_data = "{}"

        if len(trader_data) > 10000:
            saved.pop("insider", None)
            try:
                trader_data = json.dumps(saved)
            except (TypeError, ValueError):
                trader_data = "{}"

        return result, conversions, trader_data
