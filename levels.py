# GateRunner level data.
#
# M1 stub: declares the six worlds (name + theme colors used by ui.WorldMap
# and ui.LevelSelect) and the level-count constants the screens need. The
# real build_levels() generator with per-level enemy / gate / boss knobs
# lands in M9, modelled on CoinTex's levels.py.

NUM_WORLDS = 6
LEVELS_PER_WORLD = 10

# Each world is rendered with a gradient background drawn by graphics.Background.
# Colors are (r, g, b) in 0..1; "accent" is used for buttons and HUD trims.
WORLDS = [
    # 1. Meadow — gentle pace, the basics
    {"id": 1, "name": "Meadow",   "top": (0.32, 0.62, 0.36), "bottom": (0.16, 0.34, 0.20), "accent": (0.95, 0.85, 0.30)},
    # 2. Desert — faster enemies, dusty palette
    {"id": 2, "name": "Desert",   "top": (0.92, 0.72, 0.40), "bottom": (0.60, 0.40, 0.20), "accent": (0.95, 0.65, 0.25)},
    # 3. Industrial — denser spawns, cool tones
    {"id": 3, "name": "Industrial", "top": (0.40, 0.45, 0.55), "bottom": (0.16, 0.20, 0.28), "accent": (0.30, 0.75, 0.90)},
    # 4. Snowfield — slippery feel, weapon-swap gates appear
    {"id": 4, "name": "Snowfield","top": (0.78, 0.86, 0.92), "bottom": (0.44, 0.56, 0.66), "accent": (0.55, 0.85, 1.00)},
    # 5. Volcano — boss-spawn density, hot palette
    {"id": 5, "name": "Volcano",  "top": (0.86, 0.32, 0.22), "bottom": (0.30, 0.08, 0.06), "accent": (1.00, 0.60, 0.15)},
    # 6. Cosmos — everything at its hardest
    {"id": 6, "name": "Cosmos",   "top": (0.20, 0.16, 0.36), "bottom": (0.05, 0.04, 0.12), "accent": (0.70, 0.45, 1.00)},
]


def get_world(world):
    # 1-indexed lookup; clamps to last world so M1 screens always render even
    # when a save references a higher world than exists yet.
    idx = max(1, min(NUM_WORLDS, int(world))) - 1
    return WORLDS[idx]


def levels_in_world(world):
    # Returns the 10 level descriptors the LevelSelectScreen renders. M1 keeps
    # this minimal — each is just an index + the human label. M9 replaces with
    # the real per-level knobs (enemy waves, gate scripts, boss config).
    base = (world - 1) * LEVELS_PER_WORLD + 1
    return [
        {"index": base + i, "world": world, "world_index": i + 1}
        for i in range(LEVELS_PER_WORLD)
    ]


# Static seeded arena used by the 2-player versus mode. The host generates a
# random seed and the client builds the same arena from it — see net.py and
# the M13 multiplayer milestone for how this is wired up.
MP_LEVEL = "mp"
