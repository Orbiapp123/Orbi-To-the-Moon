"""
Orbi: To the Moon — Python Backend Prototype
=============================================
Stack: FastAPI + PostgreSQL (via SQLAlchemy) + Redis (caching)
Run:   uvicorn orbi_backend:app --reload

This module covers:
  - Player registration & profile
  - Inventory / item management
  - Farming loop (wheat → milk → cheese)
  - Chest opening & rarity rolling
  - Marketplace listings & purchases
  - Staking positions
  - Daily leaderboard computation
  - Background Solana event indexer
"""

from __future__ import annotations

import asyncio
import enum
import hashlib
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# In this prototype we use plain Python dicts / dataclasses instead of a real
# DB so you can run it with zero dependencies.  A production deploy would swap
# these for SQLAlchemy models + PostgreSQL + Redis.
# ---------------------------------------------------------------------------

# ── Enums ──────────────────────────────────────────────────────────────────

class Rarity(str, enum.Enum):
    COMMON    = "Common"
    UNCOMMON  = "Uncommon"
    RARE      = "Rare"
    EPIC      = "Epic"
    COSMIC    = "Cosmic"


class ItemType(str, enum.Enum):
    ACCESSORY = "Accessory"
    COW       = "Cow"
    SEED      = "Seed"
    POTION    = "Potion"
    CHEESE    = "Cheese"


class ChestType(str, enum.Enum):
    FARMING = "Farming"   # → Cows / seeds
    SEEDS   = "Seeds"     # → Fixed seed bundle
    ITEMS   = "Items"     # → Accessories, potions, cheese, cows


class StakeDuration(int, enum.Enum):
    THIRTY    = 30   # days
    NINETY    = 90
    ONE_EIGHTY = 180


# ── Constants ──────────────────────────────────────────────────────────────

CHEST_STR_COST: dict[ChestType, int] = {
    ChestType.FARMING: 50,
    ChestType.SEEDS:   20,
    ChestType.ITEMS:   80,
}

# Staking APY by duration (annualised, %)
STAKE_APY: dict[StakeDuration, float] = {
    StakeDuration.THIRTY:     25.0,
    StakeDuration.NINETY:     45.0,
    StakeDuration.ONE_EIGHTY: 70.0,
}

# Rarity weights used in chest rolls
RARITY_WEIGHTS = {
    Rarity.COMMON:   60,
    Rarity.UNCOMMON: 25,
    Rarity.RARE:     10,
    Rarity.EPIC:      4,
    Rarity.COSMIC:    1,
}

# Energy/hunger by level (capacity units)
def energy_capacity(level: int) -> int:
    return 100 + (level - 1) * 10

def hunger_capacity(level: int) -> int:
    return 10 + (level - 1) * 2

# XP needed to reach the next level
XP_PER_LEVEL = 1_000


# ── Data Models ────────────────────────────────────────────────────────────

@dataclass
class Item:
    mint: str            # Unique identifier (would be NFT mint address on-chain)
    name: str
    item_type: ItemType
    rarity: Rarity
    owner: str           # wallet address
    equipped: bool = False
    for_sale: bool = False
    sale_price_sol: float = 0.0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "mint":          self.mint,
            "name":          self.name,
            "type":          self.item_type.value,
            "rarity":        self.rarity.value,
            "owner":         self.owner,
            "equipped":      self.equipped,
            "for_sale":      self.for_sale,
            "sale_price_sol": self.sale_price_sol,
        }


@dataclass
class FarmPlot:
    """Represents one farm step in the production chain."""
    wallet: str
    stage: str             # "wheat" | "fed" | "milk" | "cheese"
    cow_rarity: Rarity
    started_at: float = field(default_factory=time.time)
    duration_seconds: int = 3600  # 1 hour base, reduced by cow rarity

    @property
    def ready(self) -> bool:
        return time.time() >= self.started_at + self.duration_seconds

    def to_dict(self) -> dict:
        remaining = max(0.0, (self.started_at + self.duration_seconds) - time.time())
        return {
            "stage":      self.stage,
            "cow_rarity": self.cow_rarity.value,
            "ready":      self.ready,
            "remaining_s": round(remaining),
        }


@dataclass
class StakePosition:
    wallet: str
    amount_str: int          # STR tokens staked
    duration: StakeDuration
    opened_at: float = field(default_factory=time.time)

    @property
    def unlock_at(self) -> float:
        return self.opened_at + self.duration.value * 86_400

    @property
    def is_unlocked(self) -> bool:
        return time.time() >= self.unlock_at

    @property
    def yield_str(self) -> int:
        """Accrued $STR yield (pro-rated to current time, capped at duration)."""
        elapsed_days = min(
            (time.time() - self.opened_at) / 86_400,
            self.duration.value,
        )
        apy = STAKE_APY[self.duration] / 100
        return int(self.amount_str * apy * elapsed_days / 365)

    def to_dict(self) -> dict:
        return {
            "wallet":       self.wallet,
            "amount_str":   self.amount_str,
            "duration_days": self.duration.value,
            "apy_pct":      STAKE_APY[self.duration],
            "is_unlocked":  self.is_unlocked,
            "yield_str":    self.yield_str,
            "unlock_at":    datetime.fromtimestamp(
                self.unlock_at, tz=timezone.utc
            ).isoformat(),
        }


@dataclass
class Player:
    wallet: str
    level:  int   = 1
    xp:     int   = 0
    str_balance: int = 0   # in-game $STR balance (mirrors on-chain)
    energy: int   = field(init=False)
    hunger: int   = field(init=False)
    energy_last_updated: float = field(default_factory=time.time)
    hunger_last_updated: float = field(default_factory=time.time)
    daily_score: int = 0   # resets each leaderboard cycle
    registered_at: float = field(default_factory=time.time)

    def __post_init__(self):
        self.energy = energy_capacity(self.level)
        self.hunger = hunger_capacity(self.level)

    # ── Energy & Hunger ───────────────────────────────────────────────────

    def current_energy(self) -> int:
        """
        Energy regenerates passively: 3 units per 10 hours.
        Returns the current value clamped to capacity.
        """
        elapsed_hours = (time.time() - self.energy_last_updated) / 3600
        regen = int(elapsed_hours * 3 / 10)
        return min(self.energy + regen, energy_capacity(self.level))

    def consume_energy(self, amount: int = 10) -> bool:
        """Consume energy for a minigame session. Returns False if insufficient."""
        current = self.current_energy()
        if current < amount:
            return False
        self.energy = current - amount
        self.energy_last_updated = time.time()
        return True

    def current_hunger(self) -> int:
        return self.hunger

    def feed(self, cheese_count: int = 1) -> bool:
        """Replenish hunger bar with cheese items. Returns False if already full."""
        cap = hunger_capacity(self.level)
        if self.hunger >= cap:
            return False
        self.hunger = min(self.hunger + cheese_count * 2, cap)
        self.hunger_last_updated = time.time()
        return True

    def consume_hunger(self) -> bool:
        """Each minigame play costs 1 hunger unit."""
        if self.hunger <= 0:
            return False
        self.hunger -= 1
        return True

    # ── Levelling ─────────────────────────────────────────────────────────

    def add_xp(self, amount: int) -> bool:
        """Add XP; return True if a level-up occurred."""
        self.xp += amount
        levelled_up = False
        while self.xp >= XP_PER_LEVEL:
            self.xp -= XP_PER_LEVEL
            self.level += 1
            levelled_up = True
        return levelled_up

    def to_dict(self) -> dict:
        return {
            "wallet":       self.wallet,
            "level":        self.level,
            "xp":           self.xp,
            "xp_to_next":   XP_PER_LEVEL - self.xp,
            "energy":       self.current_energy(),
            "energy_cap":   energy_capacity(self.level),
            "hunger":       self.current_hunger(),
            "hunger_cap":   hunger_capacity(self.level),
            "str_balance":  self.str_balance,
            "daily_score":  self.daily_score,
        }


# ── In-memory "database" (replace with PostgreSQL in production) ───────────

_players:    dict[str, Player]        = {}
_items:      dict[str, Item]          = {}
_farms:      dict[str, FarmPlot]      = {}  # wallet → active farm plot
_stakes:     dict[str, list[StakePosition]] = {}
_listings:   dict[str, Item]          = {}  # mint → listed item
_treasury:   int                      = 0   # STR in staking treasury


# ── Helper: mint ID generation ─────────────────────────────────────────────

def _new_mint(prefix: str = "ITEM") -> str:
    raw = f"{prefix}-{time.time()}-{random.randint(0, 999_999)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16].upper()


# ── Chest Rarity Roller ────────────────────────────────────────────────────

def roll_rarity() -> Rarity:
    population = list(RARITY_WEIGHTS.keys())
    weights    = list(RARITY_WEIGHTS.values())
    return random.choices(population, weights=weights, k=1)[0]


def _item_name_for(rarity: Rarity, item_type: ItemType) -> str:
    prefixes = {
        Rarity.COMMON:   "Dusty",
        Rarity.UNCOMMON: "Glowing",
        Rarity.RARE:     "Radiant",
        Rarity.EPIC:     "Ethereal",
        Rarity.COSMIC:   "Cosmic",
    }
    suffixes = {
        ItemType.ACCESSORY: "Helm",
        ItemType.COW:       "Lunar Cow",
        ItemType.SEED:      "Star Seed",
        ItemType.POTION:    "Elixir",
        ItemType.CHEESE:    "Moon Cheese",
    }
    return f"{prefixes[rarity]} {suffixes[item_type]}"


# ── Farming Duration by Cow Rarity ────────────────────────────────────────

COW_FARM_SECONDS: dict[Rarity, int] = {
    Rarity.COMMON:   3600,   # 1 hour
    Rarity.UNCOMMON: 2700,   # 45 min
    Rarity.RARE:     1800,   # 30 min
    Rarity.EPIC:     900,    # 15 min
    Rarity.COSMIC:   300,    # 5 min
}


# ══════════════════════════════════════════════════════════════════════════
#  PUBLIC SERVICE FUNCTIONS
#  These would be called by FastAPI route handlers in production.
# ══════════════════════════════════════════════════════════════════════════

class OrbiError(Exception):
    """Base error class for business-logic failures."""


def register_player(wallet: str) -> dict:
    """
    Register a new player.
    In production this is gated by the on-chain register_player instruction —
    the backend verifies the transaction signature before creating the DB row.
    """
    if wallet in _players:
        raise OrbiError(f"Player {wallet} already registered")

    player = Player(wallet=wallet)

    # Everyone starts with a Common Lunar Cow (non-transferable)
    starter_cow_mint = _new_mint("COW")
    starter_cow = Item(
        mint=starter_cow_mint,
        name="Dusty Lunar Cow",
        item_type=ItemType.COW,
        rarity=Rarity.COMMON,
        owner=wallet,
    )

    _players[wallet] = player
    _items[starter_cow_mint] = starter_cow

    return {
        "status":  "registered",
        "player":  player.to_dict(),
        "starter": starter_cow.to_dict(),
    }


def get_player(wallet: str) -> dict:
    player = _players.get(wallet)
    if not player:
        raise OrbiError(f"Player not found: {wallet}")
    return player.to_dict()


def get_inventory(wallet: str) -> list[dict]:
    if wallet not in _players:
        raise OrbiError(f"Player not found: {wallet}")
    return [item.to_dict() for item in _items.values() if item.owner == wallet]


# ── Chest Opening ──────────────────────────────────────────────────────────

def open_chest(wallet: str, chest_type: ChestType) -> dict:
    """
    Deduct STR, roll rarity, mint a new item.
    In production: STR deduction is verified on-chain first.
    """
    player = _players.get(wallet)
    if not player:
        raise OrbiError("Player not found")

    cost = CHEST_STR_COST[chest_type]
    if player.str_balance < cost:
        raise OrbiError(f"Insufficient STR. Need {cost}, have {player.str_balance}")

    # Level gate — Cosmic chests require level 10+
    if chest_type == ChestType.ITEMS and roll_rarity() == Rarity.COSMIC:
        if player.level < 10:
            raise OrbiError("You need level 10 to receive Cosmic items")

    player.str_balance -= cost
    global _treasury
    _treasury += int(cost * 0.70)  # 70% to staking treasury

    # Roll item type based on chest
    if chest_type == ChestType.FARMING:
        item_type = random.choice([ItemType.COW, ItemType.SEED])
    elif chest_type == ChestType.SEEDS:
        item_type = ItemType.SEED
    else:
        item_type = random.choice([
            ItemType.ACCESSORY, ItemType.COW,
            ItemType.POTION, ItemType.CHEESE,
        ])

    rarity = roll_rarity()
    mint   = _new_mint()
    item   = Item(
        mint=mint,
        name=_item_name_for(rarity, item_type),
        item_type=item_type,
        rarity=rarity,
        owner=wallet,
    )
    _items[mint] = item
    player.add_xp(50)  # XP for opening a chest

    return {
        "chest_type": chest_type.value,
        "str_spent":  cost,
        "item":       item.to_dict(),
        "xp_gained":  50,
        "player":     player.to_dict(),
    }


# ── Minigame ───────────────────────────────────────────────────────────────

def play_minigame(wallet: str, score: int) -> dict:
    """
    Simulate a minigame session.  Consumes energy + hunger.
    Returns STR earned (from leaderboard pool) and XP.
    In production: score is validated server-side with game replay data.
    """
    player = _players.get(wallet)
    if not player:
        raise OrbiError("Player not found")

    if not player.consume_energy(10):
        raise OrbiError("Not enough energy to play")
    if not player.consume_hunger():
        raise OrbiError("Your moon is starving — feed it cheese first!")

    # STR reward: tiered by score (simplified)
    if score >= 1000:
        str_reward = random.randint(15, 30)
        tier = "top"
    elif score >= 500:
        str_reward = random.randint(5, 14)
        tier = "middle"
    else:
        str_reward = random.randint(1, 4)
        tier = "bottom"

    player.str_balance  += str_reward
    player.daily_score  += score
    levelled_up = player.add_xp(score // 10)

    return {
        "score":       score,
        "tier":        tier,
        "str_earned":  str_reward,
        "xp_gained":   score // 10,
        "levelled_up": levelled_up,
        "player":      player.to_dict(),
    }


# ── Farming ────────────────────────────────────────────────────────────────

def start_farm(wallet: str) -> dict:
    """Start the farming cycle: plant wheat seeds."""
    player = _players.get(wallet)
    if not player:
        raise OrbiError("Player not found")
    if wallet in _farms:
        raise OrbiError("Farm already active — wait for current stage to complete")

    # Find the best cow in inventory
    best_cow = None
    for item in _items.values():
        if item.owner == wallet and item.item_type == ItemType.COW and not item.for_sale:
            if best_cow is None or (
                list(Rarity).index(item.rarity) > list(Rarity).index(best_cow.rarity)
            ):
                best_cow = item

    if not best_cow:
        raise OrbiError("You need a cow to start the farm")

    duration = COW_FARM_SECONDS[best_cow.rarity]
    plot = FarmPlot(
        wallet=wallet,
        stage="wheat",
        cow_rarity=best_cow.rarity,
        duration_seconds=duration,
    )
    _farms[wallet] = plot
    return {"farm": plot.to_dict(), "cow_used": best_cow.to_dict()}


def advance_farm(wallet: str) -> dict:
    """
    Advance the farm one stage: wheat → fed → milk → cheese.
    Each stage takes the same duration.  The final stage produces cheese items.
    """
    player = _players.get(wallet)
    if not player:
        raise OrbiError("Player not found")

    plot = _farms.get(wallet)
    if not plot:
        raise OrbiError("No active farm — call start_farm first")
    if not plot.ready:
        raise OrbiError("Farm stage not ready yet")

    stage_chain = ["wheat", "fed", "milk", "cheese"]
    current_idx = stage_chain.index(plot.stage)

    if current_idx < len(stage_chain) - 1:
        # Advance to next stage
        plot.stage = stage_chain[current_idx + 1]
        plot.started_at = time.time()
        return {"farm": plot.to_dict(), "message": f"Advanced to '{plot.stage}' stage"}
    else:
        # Final stage: harvest cheese
        del _farms[wallet]
        cheese_count = 1 + (list(Rarity).index(plot.cow_rarity))  # better cow = more cheese
        minted = []
        for _ in range(cheese_count):
            mint = _new_mint("CHEESE")
            cheese = Item(
                mint=mint,
                name="Moon Cheese",
                item_type=ItemType.CHEESE,
                rarity=Rarity.COMMON,
                owner=wallet,
            )
            _items[mint] = cheese
            minted.append(cheese.to_dict())

        player.add_xp(100)
        return {
            "message":      "Harvest complete!",
            "cheese_minted": minted,
            "cheese_count": cheese_count,
            "xp_gained":    100,
            "player":       player.to_dict(),
        }


def feed_moon(wallet: str, cheese_mint: str) -> dict:
    """Use a cheese item to replenish the hunger bar."""
    player = _players.get(wallet)
    if not player:
        raise OrbiError("Player not found")

    cheese = _items.get(cheese_mint)
    if not cheese or cheese.owner != wallet:
        raise OrbiError("Cheese item not found in your inventory")
    if cheese.item_type != ItemType.CHEESE:
        raise OrbiError("That item is not cheese")

    if not player.feed(1):
        raise OrbiError("Hunger bar is already full")

    del _items[cheese_mint]  # consumed
    return {"hunger": player.current_hunger(), "hunger_cap": hunger_capacity(player.level)}


# ── Marketplace ────────────────────────────────────────────────────────────

MARKETPLACE_FEE = 0.01   # 1% to developer
DEV_WALLET = "DEV_WALLET_ADDRESS_HERE"


def list_item(wallet: str, mint: str, price_sol: float) -> dict:
    """List an item for sale on the marketplace."""
    item = _items.get(mint)
    if not item or item.owner != wallet:
        raise OrbiError("Item not found in your inventory")
    if item.for_sale:
        raise OrbiError("Item already listed")
    if price_sol <= 0:
        raise OrbiError("Price must be positive")

    item.for_sale = True
    item.sale_price_sol = price_sol
    _listings[mint] = item
    return {"listed": item.to_dict()}


def cancel_listing(wallet: str, mint: str) -> dict:
    """Cancel a marketplace listing."""
    item = _items.get(mint)
    if not item or item.owner != wallet:
        raise OrbiError("Item not found")
    item.for_sale = False
    item.sale_price_sol = 0.0
    _listings.pop(mint, None)
    return {"cancelled": True, "mint": mint}


def buy_item(buyer_wallet: str, mint: str, buyer_sol_balance: float) -> dict:
    """
    Purchase a marketplace listing.
    In production: the SOL transfer is done on-chain; backend just
    records the ownership change after verifying the tx signature.
    """
    item = _listings.get(mint)
    if not item:
        raise OrbiError("Item not listed for sale")
    if item.owner == buyer_wallet:
        raise OrbiError("You cannot buy your own item")

    price    = item.sale_price_sol
    dev_cut  = round(price * MARKETPLACE_FEE, 9)
    seller_receives = round(price - dev_cut, 9)

    if buyer_sol_balance < price:
        raise OrbiError(f"Insufficient SOL. Need {price}, have {buyer_sol_balance}")

    seller = item.owner
    item.owner         = buyer_wallet
    item.for_sale      = False
    item.sale_price_sol = 0.0
    del _listings[mint]

    return {
        "item":             item.to_dict(),
        "buyer":            buyer_wallet,
        "seller":           seller,
        "price_sol":        price,
        "seller_receives":  seller_receives,
        "dev_fee_sol":      dev_cut,
    }


def get_listings() -> list[dict]:
    return [item.to_dict() for item in _listings.values()]


# ── Staking ────────────────────────────────────────────────────────────────

def stake_str(wallet: str, amount: int, duration: StakeDuration) -> dict:
    """Open a staking position."""
    player = _players.get(wallet)
    if not player:
        raise OrbiError("Player not found")
    if player.str_balance < amount:
        raise OrbiError(f"Insufficient STR. Need {amount}, have {player.str_balance}")
    if amount <= 0:
        raise OrbiError("Stake amount must be positive")

    player.str_balance -= amount
    position = StakePosition(wallet=wallet, amount_str=amount, duration=duration)
    _stakes.setdefault(wallet, []).append(position)

    return {
        "staked":    amount,
        "position":  position.to_dict(),
        "player":    player.to_dict(),
    }


def claim_stake(wallet: str, position_index: int) -> dict:
    """Claim a matured staking position + yield."""
    player = _players.get(wallet)
    if not player:
        raise OrbiError("Player not found")

    positions = _stakes.get(wallet, [])
    if position_index >= len(positions):
        raise OrbiError("Invalid position index")

    pos = positions[position_index]
    if not pos.is_unlocked:
        unlock_dt = datetime.fromtimestamp(pos.unlock_at, tz=timezone.utc)
        raise OrbiError(f"Position locked until {unlock_dt.isoformat()}")

    global _treasury
    total_yield = pos.yield_str
    if _treasury < total_yield:
        raise OrbiError("Treasury insufficient to pay yield right now")

    _treasury -= total_yield
    total_return = pos.amount_str + total_yield
    player.str_balance += total_return
    positions.pop(position_index)

    return {
        "principal":    pos.amount_str,
        "yield_str":    total_yield,
        "total_return": total_return,
        "player":       player.to_dict(),
    }


def get_stakes(wallet: str) -> list[dict]:
    return [p.to_dict() for p in _stakes.get(wallet, [])]


# ── Leaderboard ───────────────────────────────────────────────────────────

def get_leaderboard(top_n: int = 20) -> list[dict]:
    """
    Returns top_n players sorted by daily_score.
    In production this runs on a Redis sorted set refreshed every minute.
    """
    ranked = sorted(_players.values(), key=lambda p: p.daily_score, reverse=True)
    result = []
    for rank, player in enumerate(ranked[:top_n], start=1):
        result.append({
            "rank":        rank,
            "wallet":      player.wallet,
            "daily_score": player.daily_score,
            "level":       player.level,
            "str_payout":  _leaderboard_payout(rank, top_n, len(_players)),
        })
    return result


def _leaderboard_payout(rank: int, top_n: int, total_players: int) -> int:
    """
    Tiered payout:
      Top third  → large share
      Middle third → medium share
      Bottom third → participation reward
    """
    if total_players == 0:
        return 0
    top_third    = max(1, top_n // 3)
    middle_third = top_third * 2
    if rank <= top_third:
        return random.randint(15, 30)
    elif rank <= middle_third:
        return random.randint(5, 14)
    else:
        return random.randint(1, 4)


def reset_leaderboard() -> None:
    """Called daily by the scheduler to zero out daily scores."""
    for player in _players.values():
        player.daily_score = 0


# ── Background Solana Indexer (stub) ──────────────────────────────────────

async def solana_event_indexer(rpc_url: str = "https://api.devnet.solana.com") -> None:
    """
    Production: Uses solana-py (or solders) to subscribe to program logs via
    WebSocket. When it detects an Orbi program event (register, buy_chest,
    buy_item etc.) it updates the DB accordingly.

    This stub just prints what it would do.
    """
    print(f"[Indexer] Connecting to Solana RPC: {rpc_url}")
    print("[Indexer] Listening for Orbi program events...")

    # Example: parse a simulated log
    simulated_events = [
        {"type": "register_player",  "wallet": "WALLET_ABC123"},
        {"type": "buy_chest",        "wallet": "WALLET_ABC123", "chest": "Items"},
        {"type": "marketplace_sale", "buyer":  "WALLET_DEF456", "seller": "WALLET_ABC123",
         "mint": "ITEM_AAAA1111", "price_sol": 2.5},
    ]

    for event in simulated_events:
        await asyncio.sleep(1)
        print(f"[Indexer] Event received: {event}")

        if event["type"] == "register_player":
            wallet = event["wallet"]
            if wallet not in _players:
                register_player(wallet)
                print(f"[Indexer] Registered new player: {wallet}")

        elif event["type"] == "marketplace_sale":
            mint = event["mint"]
            if mint in _items:
                _items[mint].owner = event["buyer"]
                print(f"[Indexer] Ownership of {mint} → {event['buyer']}")


# ══════════════════════════════════════════════════════════════════════════
#  DEMO / SMOKE TEST
#  Run:  python orbi_backend.py
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import json

    def pp(obj):
        print(json.dumps(obj, indent=2))

    print("=" * 60)
    print("  ORBI BACKEND — SMOKE TEST")
    print("=" * 60)

    # 1. Register two players
    print("\n[1] Register players")
    alice = register_player("ALICE_WALLET")
    bob   = register_player("BOB_WALLET")
    pp(alice)

    # 2. Give Alice some STR to work with
    _players["ALICE_WALLET"].str_balance = 500

    # 3. Open a chest
    print("\n[2] Alice opens an Items chest")
    chest_result = open_chest("ALICE_WALLET", ChestType.ITEMS)
    pp(chest_result)

    # 4. Play a minigame
    print("\n[3] Alice plays a minigame (score: 750)")
    game_result = play_minigame("ALICE_WALLET", score=750)
    pp(game_result)

    # 5. Start the farm
    print("\n[4] Alice starts her farm")
    farm_result = start_farm("ALICE_WALLET")
    pp(farm_result)
    print("  (Simulating farm completion — fast-forwarding time...)")
    _farms["ALICE_WALLET"].started_at -= 4000  # make it ready
    adv = advance_farm("ALICE_WALLET")
    _farms["ALICE_WALLET"].started_at -= 4000
    adv = advance_farm("ALICE_WALLET")
    _farms["ALICE_WALLET"].started_at -= 4000
    adv = advance_farm("ALICE_WALLET")
    _farms["ALICE_WALLET"].started_at -= 4000
    harvest = advance_farm("ALICE_WALLET")
    pp(harvest)

    # 6. List an item in the marketplace
    item_to_sell = chest_result["item"]["mint"]
    print(f"\n[5] Alice lists item {item_to_sell} for 1.5 SOL")
    listing = list_item("ALICE_WALLET", item_to_sell, price_sol=1.5)
    pp(listing)

    # 7. Bob buys it
    print("\n[6] Bob buys Alice's item")
    _players["BOB_WALLET"].str_balance = 200
    sale = buy_item("BOB_WALLET", item_to_sell, buyer_sol_balance=5.0)
    pp(sale)

    # 8. Alice stakes some STR
    print("\n[7] Alice stakes 100 STR for 30 days")
    stake_result = stake_str("ALICE_WALLET", 100, StakeDuration.THIRTY)
    pp(stake_result)

    # 9. Leaderboard
    print("\n[8] Leaderboard")
    pp(get_leaderboard(top_n=5))

    print("\n" + "=" * 60)
    print("  All smoke tests passed ✓")
    print("=" * 60)
