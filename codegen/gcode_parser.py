"""
gcode_parser.py
---------------
Parses G-code output from the vision stack into a structured list of
WeldWaypoint objects for downstream URScript generation.

G-code conventions assumed from vision stack:
  G0  - Rapid move (approach / retract, no welding)
  G1  - Linear weld move (torch on)
  G28 - Home / safe retract
  F   - Feed rate in mm/min  -> converted to m/s for URScript
  X, Y, Z - Cartesian position in mm -> converted to meters
  A, B, C - Tool orientation as Euler angles (deg) -> converted to axis-angle (rad)
            If absent, a default torch-down orientation is used.
  ; or (  - Comment characters, ignored

Example G-code from vision stack:
  G0 X100.0 Y50.0 Z80.0          ; rapid approach
  G1 X100.0 Y50.0 Z10.0 F300     ; plunge to weld start
  G1 X200.0 Y50.0 Z10.0 F150     ; weld pass
  G1 X200.0 Y100.0 Z10.0 F150    ; corner
  G0 X200.0 Y100.0 Z80.0         ; retract
"""

import re
import math
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Default torch orientation (pointing straight down in robot base frame)
# Axis-angle: [Rx, Ry, Rz] in radians
# Adjust to match your TCP / fixture setup.
# ──────────────────────────────────────────────
DEFAULT_ORIENTATION_RAD = [-math.pi, -math.pi, 0.0]  # torch pointing -Z (down)

MM_TO_M = 1e-3
MM_PER_MIN_TO_M_PER_S = 1.0 / 60000.0  # mm/min → m/s

# Weld feed rate bounds (m/s) — clamp vision-stack values into safe range
MIN_WELD_SPEED = 0.002   # 2 mm/s
MAX_WELD_SPEED = 0.020   # 20 mm/s
DEFAULT_WELD_SPEED = 0.005  # 5 mm/s

RAPID_SPEED = 0.3        # m/s for G0 rapid traversals


@dataclass
class WeldWaypoint:
    """
    A single robot TCP waypoint derived from a G-code line.

    pose : [x, y, z, Rx, Ry, Rz]  (meters, axis-angle radians)
    speed: TCP speed in m/s
    is_weld: True if torch should be active (G1), False for rapid (G0)
    blend_radius: meters — 0.0 means stop-and-go (exact point)
    label: optional human-readable tag for debugging
    """
    pose: list[float]           # [x, y, z, Rx, Ry, Rz]
    speed: float                # m/s
    is_weld: bool               # G1 → True, G0 → False
    blend_radius: float = 0.0   # m — non-zero enables blending
    label: str = ""


def _euler_deg_to_axis_angle(rx_deg: float, ry_deg: float, rz_deg: float) -> list[float]:
    """
    Convert ZYX Euler angles (degrees) to axis-angle representation (radians).
    URScript poses use axis-angle: the vector direction is the rotation axis,
    its magnitude is the rotation angle in radians.

    This is a simple ZYX → rotation matrix → axis-angle path.
    For small orientations (mostly torch-down), this is sufficient.
    """
    rx = math.radians(rx_deg)
    ry = math.radians(ry_deg)
    rz = math.radians(rz_deg)

    # Build ZYX rotation matrix
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(sy) if False else (math.cos(ry), math.sin(ry))
    cz, sz = math.cos(rz), math.sin(rz)

    r11 = cz * cy
    r12 = cz * sy * sx - sz * cx
    r13 = cz * sy * cx + sz * sx
    r21 = sz * cy
    r22 = sz * sy * sx + cz * cx
    r23 = sz * sy * cx - cz * sx
    r31 = -sy
    r32 = cy * sx
    r33 = cy * cx

    # Rotation matrix → axis-angle
    angle = math.acos(max(-1.0, min(1.0, (r11 + r22 + r33 - 1.0) / 2.0)))

    if abs(angle) < 1e-6:
        return [0.0, 0.0, 0.0]

    ax = (r32 - r23) / (2.0 * math.sin(angle))
    ay = (r13 - r31) / (2.0 * math.sin(angle))
    az = (r21 - r12) / (2.0 * math.sin(angle))

    return [ax * angle, ay * angle, az * angle]


def _clamp_speed(speed_m_s: float, is_weld: bool) -> float:
    if not is_weld:
        return RAPID_SPEED
    return max(MIN_WELD_SPEED, min(MAX_WELD_SPEED, speed_m_s))


def parse_gcode(gcode_path: str | Path) -> list[WeldWaypoint]:
    """
    Parse a G-code file and return a list of WeldWaypoints.

    Parameters
    ----------
    gcode_path : path to the .gcode file output by the vision stack

    Returns
    -------
    List of WeldWaypoint in execution order.
    Raises ValueError on malformed input.
    """
    path = Path(gcode_path)
    if not path.exists():
        raise FileNotFoundError(f"G-code file not found: {path}")

    waypoints: list[WeldWaypoint] = []

    # State carried between lines
    current_x = current_y = current_z = 0.0
    current_rx = current_ry = current_rz = None  # None → use default
    current_feed_mm_min: Optional[float] = None
    current_gmode: Optional[int] = None  # last seen G-code type

    with path.open("r") as f:
        for lineno, raw_line in enumerate(f, start=1):
            # Strip comments: semicolons and parenthetical blocks
            line = re.sub(r";.*$", "", raw_line)
            line = re.sub(r"\(.*?\)", "", line).strip().upper()
            if not line:
                continue

            # ── Extract G-command ──────────────────────────────────────────
            g_match = re.search(r"G(\d+)", line)
            g_cmd: Optional[int] = int(g_match.group(1)) if g_match else None

            if g_cmd is not None:
                current_gmode = g_cmd

            if current_gmode is None:
                logger.debug("Line %d: no G-mode active, skipping: %s", lineno, raw_line.strip())
                continue

            # ── Skip non-motion G-codes ────────────────────────────────────
            if current_gmode == 28:
                # G28 home — append a safe retract waypoint if we have a position
                wp = WeldWaypoint(
                    pose=[current_x, current_y, current_z + 0.08, *DEFAULT_ORIENTATION_RAD],
                    speed=RAPID_SPEED,
                    is_weld=False,
                    blend_radius=0.0,
                    label=f"G28_home_L{lineno}",
                )
                waypoints.append(wp)
                continue

            if current_gmode not in (0, 1):
                logger.debug("Line %d: G%d not handled, skipping", lineno, current_gmode)
                continue

            # ── Extract XYZ ────────────────────────────────────────────────
            def _get(axis: str, default: float) -> float:
                m = re.search(rf"{axis}([+-]?\d+\.?\d*)", line)
                return float(m.group(1)) if m else default

            x_m = _get("X", current_x * 1000) * MM_TO_M
            y_m = _get("Y", current_y * 1000) * MM_TO_M
            z_m = _get("Z", current_z * 1000) * MM_TO_M

            current_x, current_y, current_z = x_m, y_m, z_m

            # ── Extract optional orientation ───────────────────────────────
            a_deg = _get("A", math.degrees(current_rx) if current_rx else 180.0)
            b_deg = _get("B", math.degrees(current_ry) if current_ry else 0.0)
            c_deg = _get("C", math.degrees(current_rz) if current_rz else 0.0)

            has_orientation = bool(
                re.search(r"[ABC][+-]?\d", line)
            )

            if has_orientation:
                orientation = _euler_deg_to_axis_angle(a_deg, b_deg, c_deg)
                current_rx, current_ry, current_rz = orientation
            else:
                orientation = (
                    [current_rx, current_ry, current_rz]
                    if current_rx is not None
                    else DEFAULT_ORIENTATION_RAD
                )

            # ── Extract feed rate ──────────────────────────────────────────
            f_match = re.search(r"F([+-]?\d+\.?\d*)", line)
            if f_match:
                current_feed_mm_min = float(f_match.group(1))

            speed_m_s = (
                current_feed_mm_min * MM_PER_MIN_TO_M_PER_S
                if current_feed_mm_min
                else DEFAULT_WELD_SPEED
            )

            is_weld = current_gmode == 1
            speed_m_s = _clamp_speed(speed_m_s, is_weld)

            # ── Blend radius: 0 for last weld point and all rapids ─────────
            # Will be refined in post-processing below
            blend = 0.002 if is_weld else 0.005  # 2 mm weld blend, 5 mm rapid blend

            wp = WeldWaypoint(
                pose=[x_m, y_m, z_m, *orientation],
                speed=speed_m_s,
                is_weld=is_weld,
                blend_radius=blend,
                label=f"G{current_gmode}_L{lineno}",
            )
            waypoints.append(wp)

    if not waypoints:
        raise ValueError(f"No valid waypoints parsed from {path}. Check G-code format.")

    # ── Post-processing: zero blend on final weld point ────────────────────
    # The last waypoint in any weld segment must be exact (no blend)
    for i in range(len(waypoints) - 1):
        if waypoints[i].is_weld and not waypoints[i + 1].is_weld:
            waypoints[i].blend_radius = 0.0  # stop exactly at weld end

    # Always zero blend on final waypoint
    waypoints[-1].blend_radius = 0.0

    logger.info("Parsed %d waypoints from %s", len(waypoints), path.name)
    return waypoints


def summarize_waypoints(waypoints: list[WeldWaypoint]) -> str:
    """Return a human-readable summary of parsed waypoints for debugging."""
    lines = [f"{'#':<4} {'Label':<20} {'Type':<6} {'X':>8} {'Y':>8} {'Z':>8} {'Speed':>8}"]
    lines.append("-" * 70)
    for i, wp in enumerate(waypoints):
        x, y, z = wp.pose[0], wp.pose[1], wp.pose[2]
        wtype = "WELD" if wp.is_weld else "RAPID"
        lines.append(
            f"{i:<4} {wp.label:<20} {wtype:<6} {x*1000:>7.2f}mm {y*1000:>7.2f}mm "
            f"{z*1000:>7.2f}mm {wp.speed*1000:>6.2f}mm/s"
        )
    return "\n".join(lines)