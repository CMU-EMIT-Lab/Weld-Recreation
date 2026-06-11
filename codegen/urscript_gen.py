"""
urscript_gen.py
---------------
Converts parsed WeldWaypoints into URScript programs for the UR10e.

Two deployment backends are supported:

  ScriptFileBackend  — writes a self-contained .script file.
                       Deploy via SSH (see deploy/ssh_deploy.py) or
                       load directly onto the pendant via USB/network share.
                       The robot executes it as a single atomic program.
                       ✓ Recommended for production runs.
                       ✓ Inspectable / version-controllable.
                       ✗ No live feedback; errors only visible on pendant.

  SocketBackend      — opens a TCP connection to port 30002 and streams the
                       full program as one payload. The robot executes it
                       immediately. Useful for rapid iteration / debugging
                       when you are co-located with the robot.
                       ✓ Instant execution, no file transfer step.
                       ✗ Non-blocking: you must manage timing yourself.
                       ✗ Sending commands while a program is running stops it.

Choose via the `backend` parameter in `generate()`.

URScript references used:
  - movel(pose, a, v, t, r)  — linear TCP motion [m, m/s, m/s², m, rad]
  - movej(pose, a, v, t, r)  — joint-space motion for approach/retract
  - set_digital_out(n, val)  — torch relay control
  - sleep(t)                 — dwell / arc start delay
  - Port 30002 (Secondary Interface) for socket streaming

Safety notes baked in:
  - Acceleration capped at 0.5 m/s² (weld) / 1.2 m/s² (rapid)
  - All moves wrapped in a def/end block so the robot doesn't execute
    partial programs if the connection drops mid-send
  - Approach uses movej to avoid Cartesian singularities near start point
"""

import socket
import time
import logging
import math
from pathlib import Path
from typing import Literal

from gcode_parser import WeldWaypoint

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# UR10e Motion Parameters
# Tune these for your fixture, material, and wire-feed setup.
# ──────────────────────────────────────────────────────────────────────────────

# Linear (Cartesian) accelerations — m/s²
WELD_ACCEL = 0.3      # conservative for weld segments
RAPID_ACCEL = 1.0     # approach / retract moves

# Torch digital output number on the UR10e tool I/O
# Check your wiring: typically digital output 0 or 1 on the tool connector
TORCH_DIGITAL_OUT = 0

# Arc start delay (seconds) — time between torch-on and motion start
ARC_START_DELAY = 0.5

# Arc end dwell (seconds) — crater fill time at end of weld
ARC_END_DWELL = 0.2

# TCP socket timeout when connecting to robot
SOCKET_CONNECT_TIMEOUT = 5.0   # seconds
SOCKET_SEND_TIMEOUT = 10.0     # seconds

# UR10e network interface
DEFAULT_ROBOT_IP = "192.168.1.1"
URSCRIPT_PORT = 30002   # Secondary interface — accepts full URScript programs

# Default Payload and TCP configurations
DEFAULT_PAYLOAD_MASS = 3.58               # kg
DEFAULT_PAYLOAD_COG = [0.036, -0.080, 0.060]    # [CoGx, CoGy, CoGz] in meters offset from tool mount
DEFAULT_TCP_POSE = [0.00225, 0.00271, 0.45227, 0.8534, 0.5181, 1.1027]  # 0 equivalent tool center point


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _fmt_pose(pose: list[float]) -> str:
    """Format a 6-element pose as a URScript p[] literal."""
    if len(pose) != 6:
        raise ValueError(f"Pose must have 6 elements, got {len(pose)}: {pose}")
    return "p[{:.6f}, {:.6f}, {:.6f}, {:.6f}, {:.6f}, {:.6f}]".format(*pose)


def _movel(pose: list[float], speed: float, accel: float, blend: float) -> str:
    """Return a movel() URScript line (linear tool-space move)."""
    return (
        f"  movel({_fmt_pose(pose)}, "
        f"a={accel:.4f}, v={speed:.4f}, r={blend:.4f})"
    )


def _movej_from_pose(pose: list[float], speed: float = 0.5, accel: float = 1.0, blend: float = 0.0) -> str:
    """
    Return a movej() line using a Cartesian pose (UR does IK internally).
    Safer than movel for approach moves far from the weld start.
    """
    return (
        f"  movej({_fmt_pose(pose)}, "
        f"a={accel:.4f}, v={speed:.4f}, r={blend:.4f})"
    )


def _torch_on() -> list[str]:
    return [
        f"  set_digital_out({TORCH_DIGITAL_OUT}, True)   # torch ON",
        f"  sleep({ARC_START_DELAY})                     # arc start delay",
    ]


def _torch_off() -> list[str]:
    return [
        f"  sleep({ARC_END_DWELL})                       # crater fill dwell",
        f"  set_digital_out({TORCH_DIGITAL_OUT}, False)  # torch OFF",
    ]


# ──────────────────────────────────────────────────────────────────────────────
# Script builder
# ──────────────────────────────────────────────────────────────────────────────

def build_urscript(
    waypoints: list[WeldWaypoint],
    program_name: str = "weld_program",
) -> str:
    """
    Convert a list of WeldWaypoints into a complete URScript program string.

    The program structure:
      def <program_name>():
        # safety: torch off at start
        movej → approach point (first rapid waypoint)
        [ for each waypoint:
            movel (rapid) → torch_on → movel (weld) → torch_off ]
        movej → retract
      end

    Parameters
    ----------
    waypoints    : parsed from gcode_parser.parse_gcode()
    program_name : name of the URScript def block

    Returns
    -------
    Complete URScript as a string, ready to write to file or send via socket.
    """
    if not waypoints:
        raise ValueError("Cannot build URScript: waypoint list is empty.")

    lines: list[str] = []

    # Header
    cog_str = ", ".join(f"{x:.4f}" for x in DEFAULT_PAYLOAD_COG)
    tcp_str = ", ".join(f"{x:.4f}" for x in DEFAULT_TCP_POSE)
    lines += [
        f"def {program_name}():",
        f"  # Auto-generated by cobot_welding/codegen/urscript_gen.py",
        f"  # Waypoints: {len(waypoints)}",
        f"  # DO NOT EDIT — regenerate from G-code instead.",
        f"",
        f"  # ── Safety init ──────────────────────────────────────────",
        f"  set_digital_out({TORCH_DIGITAL_OUT}, False)  # ensure torch off",
        f"  set_target_payload({DEFAULT_PAYLOAD_MASS:.1f}, [{cog_str}])",
        f"  set_tcp(p[{tcp_str}])",
        f"  sleep(0.1)",
        f"",
    ]

    # Approach: movej to first waypoint using joint-space for safety
    first = waypoints[0]
    lines += [
        "  # ── Approach (joint-space to avoid singularities) ─────────",
        _movej_from_pose(first.pose, speed=0.3, accel=0.8, blend=0.0),
        "",
    ]

    # Main motion loop
    in_weld = False
    lines.append("  # ── Weld path ──────────────────────────────────────────")

    for i, wp in enumerate(waypoints):
        # Transition: rapid → weld (torch on)
        if wp.is_weld and not in_weld:
            lines.append(f"  # weld segment start — {wp.label}")
            lines += _torch_on()
            in_weld = True

        # Transition: weld → rapid (torch off)
        elif not wp.is_weld and in_weld:
            lines += _torch_off()
            lines.append(f"  # rapid move — {wp.label}")
            in_weld = False

        accel = WELD_ACCEL if wp.is_weld else RAPID_ACCEL
        lines.append(_movel(wp.pose, wp.speed, accel, wp.blend_radius))

    # Ensure torch is off at end
    if in_weld:
        lines += _torch_off()

    # Retract: lift Z by 80 mm from last position, joint-space
    last = waypoints[-1]
    retract_pose = list(last.pose)
    retract_pose[2] += 0.080  # +80 mm in Z
    lines += [
        "",
        "  # ── Retract ─────────────────────────────────────────────",
        _movej_from_pose(retract_pose, speed=0.5, accel=1.0, blend=0.0),
        "",
    ]

    lines.append("end")
    lines.append(f'{program_name}()')

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Backend: Script File
# ──────────────────────────────────────────────────────────────────────────────

class ScriptFileBackend:
    """
    Writes the generated URScript to a .script file on disk.

    The file can be:
      - Transferred to the robot via SSH (see deploy/ssh_deploy.py)
      - Placed on a USB stick and loaded via the teach pendant
      - Fetched by the robot over a network share

    The .script file must wrap all motion in def/end — which build_urscript()
    handles automatically. Port 30001/30002 can execute it by reading the file
    as bytes and sending the full buffer.
    """

    def __init__(self, output_path: str | Path):
        self.output_path = Path(output_path)

    def deploy(self, script: str) -> Path:
        """Write script to disk. Returns the output path."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(script, encoding="utf-8")
        logger.info("URScript written to %s (%d bytes)", self.output_path, len(script))
        return self.output_path


# ──────────────────────────────────────────────────────────────────────────────
# Backend: Live Socket
# ──────────────────────────────────────────────────────────────────────────────

class SocketBackend:
    """
    Sends the generated URScript directly to the robot via TCP socket on port 30002.

    The UR Secondary Interface (port 30002) accepts a complete URScript program
    as a raw byte stream. The robot executes it immediately on receipt.

    Important limitations (from URScript docs):
      - Sending a new script while a program is running STOPS the running program.
      - The interface is non-blocking — you must manage execution timing externally.
      - For sequential multi-move programs, the entire def/end block must be sent
        as a single payload (not line by line). build_urscript() produces this.
      - Port 30002 is the Secondary Interface. Port 30001 is Primary (same behavior).
        Port 30003 (Realtime) has a 125 Hz cycle and different constraints.

    When to use socket vs file:
      Use socket  → rapid iteration, debugging, testing individual segments
      Use file    → production, SSH-deployed runs, repeatable batch welds
    """

    def __init__(self, robot_ip: str = DEFAULT_ROBOT_IP, port: int = URSCRIPT_PORT):
        self.robot_ip = robot_ip
        self.port = port

    def deploy(self, script: str) -> None:
        """
        Send script to robot over TCP. Blocks until send is complete.
        Does NOT block until robot execution is complete — that is a robot-side
        concern. Use robot state monitoring (RTDE / port 30003 feedback) for that.
        """
        payload = (script + "\n").encode("utf-8")
        logger.info(
            "Connecting to UR10e at %s:%d ...", self.robot_ip, self.port
        )

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(SOCKET_CONNECT_TIMEOUT)
            try:
                s.connect((self.robot_ip, self.port))
            except (socket.timeout, ConnectionRefusedError) as e:
                raise ConnectionError(
                    f"Could not connect to UR10e at {self.robot_ip}:{self.port}. "
                    f"Check IP, robot power, and network. Original error: {e}"
                ) from e

            s.settimeout(SOCKET_SEND_TIMEOUT)
            logger.info("Connected. Sending %d bytes ...", len(payload))

            # Send in chunks in case payload is large
            total_sent = 0
            while total_sent < len(payload):
                sent = s.send(payload[total_sent:])
                if sent == 0:
                    raise RuntimeError("Socket connection broken during send.")
                total_sent += sent

            # Brief pause: UR controller needs ~50ms to process the received script
            time.sleep(0.1)

        logger.info(
            "Script sent successfully (%d bytes). Robot is now executing.", total_sent
        )


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def generate(
    waypoints: list[WeldWaypoint],
    backend: Literal["file", "socket"] = "file",
    output_path: str | Path | None = None,
    robot_ip: str = DEFAULT_ROBOT_IP,
    program_name: str = "weld_program",
) -> str:
    """
    Generate URScript from waypoints and deploy via the chosen backend.

    Parameters
    ----------
    waypoints    : output of gcode_parser.parse_gcode()
    backend      : "file"   → write .script to output_path (default)
                   "socket" → stream directly to robot at robot_ip:30002
    output_path  : required for "file" backend; path to write .script file
    robot_ip     : required for "socket" backend; robot network IP
    program_name : name of the URScript def block

    Returns
    -------
    The generated URScript as a string (regardless of backend).
    """
    script = build_urscript(waypoints, program_name=program_name)

    if backend == "file":
        if output_path is None:
            raise ValueError("output_path must be specified for file backend.")
        deployer = ScriptFileBackend(output_path)
        deployer.deploy(script)

    elif backend == "socket":
        deployer = SocketBackend(robot_ip=robot_ip)
        deployer.deploy(script)

    else:
        raise ValueError(f"Unknown backend: '{backend}'. Choose 'file' or 'socket'.")

    return script