"""aim.py — pure manual-aim math (no Kivy import, unit-testable).

Manual aim couples the squad's firing direction to steering motion: a
trailing "aim lead" point eases toward the player's steering target; the
horizontal gap between them (how far the player is currently reaching)
maps to a firing angle off vertical. Hold still and the lead catches up,
so the aim self-centers to straight-up.

All inputs are in already-scaled world px; callers wrap raw constants in
graphics.ws() before calling. Angles are radians measured off straight-up,
positive to the right.
"""

import math


def update_aim_lead(lead_x: float, target_x: float, dt: float,
                    ease: float) -> float:
    """Ease the trailing aim-lead point toward the steering target.

    `ease` is a per-second rate; the step is clamped to [0, 1] so a large
    `dt` (or a stall) can't overshoot the target.
    """
    k = ease * dt
    if k > 1.0:
        k = 1.0
    elif k < 0.0:
        k = 0.0
    return lead_x + (target_x - lead_x) * k


def aim_angle(offset_px: float, full_px: float, max_rad: float) -> float:
    """Map a horizontal lead offset (px) to a firing angle off vertical.

    Linear until |offset| reaches `full_px`, then saturates at ±`max_rad`.
    """
    if full_px <= 0.0:
        return 0.0
    t = offset_px / full_px
    if t > 1.0:
        t = 1.0
    elif t < -1.0:
        t = -1.0
    return t * max_rad


def reticle_point(hero_x: float, muzzle_y: float, angle_rad: float,
                  lead_dist: float):
    """The convergence point the guns aim at: `lead_dist` ahead of the
    muzzle along `angle_rad` (measured off straight-up, +right)."""
    rx = hero_x + math.sin(angle_rad) * lead_dist
    ry = muzzle_y + math.cos(angle_rad) * lead_dist
    return rx, ry
