"""Headless self-check for Savage Dungeon.

Covers the pygame-free core only: Savage Worlds dice maths, player
wounds/armour/serialisation, chunked map generation + save/restore, and the
combat resolution helpers. main.py / systems/ (pygame) are never imported.

Usage: python selfcheck.py
"""

import os
import random
import sys
import tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class Checker:
    """Collects failures so every check runs before exiting."""

    def __init__(self) -> None:
        self.failures: list[str] = []
        self.passed: list[str] = []

    def check(self, label: str, ok: bool, detail: str = "") -> None:
        if ok:
            self.passed.append(label)
            print(f"  ok   {label}")
        else:
            message = f"{label}: {detail}" if detail else label
            self.failures.append(message)
            print(f"  FAIL {message}")

    def section(self, title: str) -> None:
        print(f"[{title}]")


def check_dice(c: Checker) -> None:
    """Savage Worlds rolls must satisfy wild-die and raise invariants."""
    c.section("savage dice")
    from core.savage_dice import SavageDice

    random.seed(20261026)
    rolls = [SavageDice.roll() for _ in range(400)]
    c.check(
        "roll total is the higher of trait/wild dice",
        all(r.total == max(r.trait_roll, r.wild_roll) for r in rolls),
        "total != max(trait, wild)",
    )
    c.check(
        "dice stay inside d8 / d6 ranges",
        all(1 <= r.trait_roll <= 8 and 1 <= r.wild_roll <= 6 for r in rolls),
        "out-of-range die",
    )
    c.check(
        "crit fail only when both dice show 1",
        all(r.is_critical_fail == (r.trait_roll == 1 and r.wild_roll == 1) for r in rolls),
        "mismatched crit-fail flag",
    )

    targeted = [SavageDice.roll_with_target(6) for _ in range(400)]
    c.check(
        "raise flag and raise count follow the target number",
        all(
            r.is_raise == (r.total >= 10)
            and r.raises == ((r.total - 6) // 4 if r.total >= 6 else 0)
            for r in targeted
        ),
        "raise maths off",
    )

    damage = [SavageDice.damage_roll("2d6+3") for _ in range(100)]
    c.check(
        "2d6+3 damage stays in 5..15",
        all(5 <= d <= 15 for d in damage),
        f"min={min(damage)} max={max(damage)}",
    )
    c.check("unparseable damage notation yields 0", SavageDice.damage_roll("nope") == 0)
    c.check(
        "bennie and initiative dice are in range",
        all(1 <= SavageDice.spend_bennie() <= 8 for _ in range(50))
        and all(1 <= a <= 8 and 1 <= b <= 6 for a, b in
                (SavageDice.roll_initiative() for _ in range(50))),
        "out-of-range bennie/initiative",
    )


def check_player(c: Checker) -> None:
    """Wounds, armour and save-field round trip must behave as documented."""
    c.section("player state")
    from core.player import Bennies, PlayerState, create_default_player

    player = create_default_player()
    c.check(
        "default player has torso armour 1 and 3 bennies",
        player.armor["torso"] == 1 and player.bennies.current == 3 and player.max_wounds == 3,
        f"armor={player.armor['torso']} bennies={player.bennies.current}",
    )

    dead, msg = player.take_damage(3, "torso")   # 3 - 1 armour = 2 dmg -> 1 wound
    c.check(
        "armour reduces damage and 1 wound is taken",
        dead is False and player.wounds == 1 and player.is_shaken,
        f"wounds={player.wounds} shaken={player.is_shaken} msg={msg}",
    )

    dead, _ = player.take_damage(9, "head")      # 9 dmg -> 3 more wounds = 4 > max 3
    c.check(
        "exceeding max wounds kills the character",
        dead is True and player.wounds == 4 and player.is_alive is False,
        f"wounds={player.wounds} alive={player.is_alive}",
    )

    p2 = create_default_player()
    p2.wounds = 2
    p2.is_shaken = True
    p2.bennies.current = 1
    p2.position = (5, 7)
    p2.facing = 2
    p2.armor["torso"] = 2
    data = p2.to_dict()
    restored = PlayerState.from_dict(data)
    c.check(
        "to_dict/from_dict round trip keeps stats, skills and position",
        restored.wounds == 2 and restored.is_shaken is True
        and restored.bennies.current == 1 and restored.position == (5, 7)
        and restored.facing == 2 and restored.armor["torso"] == 2
        and restored.attributes == p2.attributes
        and sorted(restored.skills) == sorted(p2.skills)
        and restored.skills["fighting"].rank == p2.skills["fighting"].rank
        and restored.inventory == p2.inventory,
        f"got wounds={restored.wounds} pos={restored.position}",
    )

    b = Bennies(max_bennies=2, current=1)
    spent = b.use()
    empty = b.use()
    b.restore(5)
    c.check(
        "bennies spend down and never exceed the cap",
        spent is True and empty is False and b.current == 2,
        f"current={b.current}",
    )
    c.check(
        "skill die uses the better of attribute and rank",
        create_default_player().get_skill_die("fighting") == 6
        and create_default_player().get_skill_die("missing") is None,
        "skill-die lookup wrong",
    )


def check_map(c: Checker) -> None:
    """Chunks must generate deterministically, save/restore and unload."""
    c.section("map system")
    from core.map_system import MapSystem, TileType

    a = MapSystem(seed=12345)
    b = MapSystem(seed=12345)
    a.move_player(8, 8)
    b.move_player(8, 8)
    chunk_a = a.chunks["chunk_0_0"]
    chunk_b = b.chunks["chunk_0_0"]
    c.check(
        "a fixed seed reproduces the same 16x16 chunk",
        len(chunk_a.tiles) == 256 and len(chunk_b.tiles) == 256
        and all(chunk_a.tiles[k].type is chunk_b.tiles[k].type for k in chunk_a.tiles),
        f"tiles={len(chunk_a.tiles)} vs {len(chunk_b.tiles)}",
    )
    c.check(
        "chunk borders are solid walls",
        all(
            chunk_a.get_tile(x, y).type is TileType.WALL
            for x in range(0, 16, 15)
            for y in range(0, 16, 15)
        )
        and chunk_a.get_tile(0, 8).type is TileType.WALL,
        "edge tile is not a wall",
    )

    visible = a.get_visible_tiles(8, 8)
    c.check(
        "FOV returns the 9x9 neighbourhood around the player",
        len(visible) == 81
        and all(abs(t.x - 8) + abs(t.y - 8) <= 8 for t in visible),
        f"visible={len(visible)}",
    )

    tile = a.reveal_tile(8, 8)
    c.check(
        "revealing a tile marks it revealed exactly once",
        tile is not None and tile.revealed and (8, 8) in a.revealed_tiles
        and tile.reveal() is False,
        "reveal bookkeeping wrong",
    )
    c.check(
        "flagging a tile toggles the flag back and forth",
        a.flag_tile(9, 8) is True and a.flag_tile(9, 8) is False,
        "flag toggle wrong",
    )

    states = a.get_tile_states()
    fresh = MapSystem(seed=12345)
    fresh.restore_tile_states(states)
    restored = fresh.get_tile(8, 8)
    c.check(
        "tile revealed/flagged states survive export + restore",
        any(s["x"] == 8 and s["y"] == 8 and s["revealed"] for s in states)
        and restored is not None and restored.revealed,
        f"states={states[:2]}",
    )

    with tempfile.TemporaryDirectory(prefix="dungeon-selfcheck-") as tmpdir:
        path = os.path.join(tmpdir, "chunks.json")
        a.chunks["chunk_0_0"].visited = True
        expected = {k: t.type.value for k, t in a.chunks["chunk_0_0"].tiles.items()}
        a.save_chunks(path)
        loaded = MapSystem(seed=999)
        loaded.load_chunks(path)
        got = {k: t.type.value for k, t in loaded.chunks["chunk_0_0"].tiles.items()}
        c.check(
            "visited chunks survive a JSON save/load round trip",
            loaded.seed == 12345 and got == expected,
            f"seed={loaded.seed} tiles={len(got)} expected={len(expected)}",
        )

    far = MapSystem(seed=12345)
    far.move_player(8, 8)
    unloaded = far.move_player(400, 400)
    c.check(
        "moving far away unloads the distant chunks",
        len(unloaded) > 0
        and "chunk_0_0" not in far.chunks
        and all(
            abs(ch.world_x - 400) + abs(ch.world_y - 400) <= far.UNLOAD_DIST
            for ch in far.chunks.values()
        ),
        f"unloaded={unloaded[:3]} left={sorted(far.chunks)}",
    )


def check_combat(c: Checker) -> None:
    """Combat helpers must resolve safe tiles and consumables deterministically."""
    c.section("combat")
    from core.combat import CombatSystem, EncounterResult
    from core.map_system import Tile, TileType
    from core.player import create_default_player

    player = create_default_player()
    safe = Tile(3, 3, TileType.FLOOR, threat=0)
    log = CombatSystem.resolve_exploration(player, safe)
    c.check(
        "a threat-0 tile resolves safely without damage",
        log.result is EncounterResult.SUCCESS and log.damage == 0
        and player.wounds == 0,
        f"result={log.result} damage={log.damage}",
    )

    c.check(
        "pretest on a safe tile reports DC 0",
        CombatSystem.pretest_exploration(player, safe) == (True, "安全", 0),
        "pretest mismatch",
    )

    hurt = create_default_player()
    hurt.wounds = 1
    message = CombatSystem.use_consumable(
        hurt, {"name": "potion", "effect": "heal_1_wound"}
    )
    c.check(
        "a healing potion removes exactly one wound",
        hurt.wounds == 0 and "potion" in message,
        f"wounds={hurt.wounds} msg={message}",
    )
    empty_message = CombatSystem.use_consumable(
        hurt, {"name": "potion", "effect": "heal_1_wound"}
    )
    c.check(
        "healing with no wounds is a no-op",
        hurt.wounds == 0 and bool(empty_message),
        f"wounds={hurt.wounds}",
    )

    dead, _ = CombatSystem.check_death(hurt)
    alive, _ = CombatSystem.check_death(player)
    c.check(
        "check_death only fires for a dead character",
        dead is False and alive is False and player.is_alive,
        f"dead_flag={dead}",
    )
    hurt.is_alive = False
    dead, _ = CombatSystem.check_death(hurt)
    c.check("check_death detects a killed character", dead is True)


def main() -> int:
    c = Checker()
    try:
        check_dice(c)
        check_player(c)
        check_map(c)
        check_combat(c)
    except Exception as exc:  # noqa: BLE001 - report any crash as a failure
        print(f"FAIL unexpected {type(exc).__name__}: {exc}")
        return 1

    if c.failures:
        print(f"FAIL {len(c.failures)} check(s) failed: {c.failures[0]}")
        return 1

    print(
        f"selfcheck ok: {len(c.passed)} checks - Savage Worlds dice/raise invariants, "
        "player wounds-armour-bennies + save-field round trip, seeded chunk generation "
        "+ chunk save/load and unloading, combat/consumable resolution"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
