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
INSIDER_THRESHOLD = 0.55     # accuracy threshold to follow an insider
INSIDER_MIN_TRADES = 5       # min trades before trusting insider score
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
        fair = FIXED_FAIR_VALUES.get(product, 10000)
        limit = self.get_limit(product)
        pos = self.get_position(product, state)

        # Take mispriced orders: buy below fair, sell above fair
        for ask_price in sorted(od.sell_orders.keys()):
            if ask_price <= fair:
                ask_vol = -od.sell_orders[ask_price]
                can_buy = limit - pos
                qty = min(ask_vol, can_buy)
                if qty > 0:
                    orders.append(Order(product, ask_price, qty))
                    pos += qty

        for bid_price in sorted(od.buy_orders.keys(), reverse=True):
            if bid_price >= fair:
                bid_vol = od.buy_orders[bid_price]
                can_sell = limit + pos
                qty = min(bid_vol, can_sell)
                if qty > 0:
                    orders.append(Order(product, bid_price, -qty))
                    pos -= qty

        # Resting orders with inventory skew
        buy_price = fair - MM_FIXED_SPREAD
        sell_price = fair + MM_FIXED_SPREAD

        buy_qty = limit - pos
        sell_qty = limit + pos

        if buy_qty > 0:
            orders.append(Order(product, int(buy_price), buy_qty))
        if sell_qty > 0:
            orders.append(Order(product, int(sell_price), -sell_qty))

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

        # Update EMA
        alpha = MM_DYNAMIC_EMA_ALPHA
        key = f"ema_{product}"
        prev_ema = saved.get(key, mid)
        ema = alpha * mid + (1 - alpha) * prev_ema
        saved[key] = ema
        self.ema[product] = ema

        fair = ema
        limit = self.get_limit(product)
        pos = self.get_position(product, state)
        spread = 1 if product == "KELP" else MM_DYNAMIC_SPREAD

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
            c_mid = get_mid(state.order_depths[c])
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
        entry_thr = BASKET_ENTRY_THRESHOLD

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

        option_mid = get_mid(state.order_depths[product])
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
            edge_thr = 2.0  # edge for P2 coconut coupon
        else:
            # P3: use fitted vol smile (FrankfurtHedgehogs approach)
            # coeffs from fitted volatility smile: IV = f(log(K/S)/sqrt(T))
            m_t_k = math.log(strike / S) / math.sqrt(T) if T > 1e-8 else 0
            vol_smile_iv = 0.16476677 + 0.01007566 * m_t_k + 0.27362531 * m_t_k * m_t_k
            vol_smile_iv = max(0.05, min(1.0, vol_smile_iv))
            fair = bs_call_price(S, strike, T, vol_smile_iv)
            # Dynamic edge threshold: widen for low-vega options (Frankfurt approach)
            vega = bs_vega(S, strike, T, vol_smile_iv)
            edge_thr = 0.3 if vega > 1.0 else 0.8

        if fair <= 0.5:
            return orders

        edge = option_mid - fair
        limit = self.get_limit(product)

        # IV scalping: track running mean of edge deviation (works for both P2 and P3)
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

        if underlying != "COCONUT":
            limit = min(limit, 75)  # cap P3 options position

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

        # Market making around fair value (only for COCONUT with wide spread)
        if underlying == "COCONUT":
            spread = max(3, int(fair * 0.01))
            max_mm_qty = 15
            buy_price = int(round(fair - spread))
            sell_price = int(round(fair + spread))
            buy_qty = min(limit - pos, max_mm_qty)
            sell_qty = min(limit + pos, max_mm_qty)
            if buy_qty > 0 and buy_price > 0:
                orders.append(Order(product, buy_price, buy_qty))
            if sell_qty > 0 and sell_price > 0:
                orders.append(Order(product, sell_price, -sell_qty))
        # P3 options: no MM resting orders, only take mispriced

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

    def detect_insider(self, state: TradingState, saved: dict) -> dict:
        signals = {}

        # Fast path: check for known insider trades this tick
        if state.market_trades:
            for product, trades in state.market_trades.items():
                if product not in state.order_depths:
                    continue
                for trade in trades:
                    buyer = trade.buyer or ""
                    seller = trade.seller or ""
                    if buyer == "SUBMISSION" or seller == "SUBMISSION":
                        continue
                    # Known insiders: follow immediately
                    if buyer in self.KNOWN_INSIDERS:
                        if product not in signals or True:
                            signals[product] = (1, 0.9)  # high confidence buy
                    elif seller in self.KNOWN_INSIDERS:
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
            for order in result[product]:
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
