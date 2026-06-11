"""
main.py
-------
End-to-end pipeline: G-code file → URScript → deploy (file or socket).

Usage
-----
# Write a .script file (for SSH deploy):
python main.py --input path/to/weld.gcode --output output/weld_program.script

# Stream directly to robot over socket:
python main.py --input path/to/weld.gcode --backend socket --robot-ip 192.168.1.1

# Dry run (generate script, print to stdout, no deploy):
python main.py --input path/to/weld.gcode --dry-run

# Override program name:
python main.py --input path/to/weld.gcode --output output/run_1.script --name run_1
"""

import argparse
import logging
import sys
from pathlib import Path

from gcode_parser import parse_gcode, summarize_waypoints
from urscript_gen import generate, DEFAULT_ROBOT_IP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("cobot_welding")


def main():
    parser = argparse.ArgumentParser(
        description="Cobot Welding Pipeline: G-code → URScript → UR10e",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input", "-i", required=True,
        help="Path to G-code file from vision stack",
    )
    parser.add_argument(
        "--backend", "-b", choices=["file", "socket"], default="file",
        help=(
            "Deployment backend. "
            "'file' writes a .script file (default). "
            "'socket' streams directly to the robot."
        ),
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="Output .script file path (required for --backend file)",
    )
    parser.add_argument(
        "--robot-ip", default=DEFAULT_ROBOT_IP,
        help=f"UR10e IP address for socket backend (default: {DEFAULT_ROBOT_IP})",
    )
    parser.add_argument(
        "--name", "-n", default="weld_program",
        help="URScript program name (def block name)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Parse and generate script but do not deploy. Prints script to stdout.",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show parsed waypoint summary before generating",
    )

    args = parser.parse_args()

    # ── Validate args ──────────────────────────────────────────────────────
    if args.backend == "file" and not args.output and not args.dry_run:
        parser.error("--output is required when using --backend file")

    # ── Parse G-code ───────────────────────────────────────────────────────
    logger.info("Parsing G-code: %s", args.input)
    try:
        waypoints = parse_gcode(args.input)
    except (FileNotFoundError, ValueError) as e:
        logger.error("G-code parsing failed: %s", e)
        sys.exit(1)

    logger.info("Parsed %d waypoints.", len(waypoints))

    if args.verbose:
        print("\n" + summarize_waypoints(waypoints) + "\n")

    # ── Generate & deploy ──────────────────────────────────────────────────
    if args.dry_run:
        from urscript_gen import build_urscript
        script = build_urscript(waypoints, program_name=args.name)
        print("\n" + "─" * 60)
        print("DRY RUN — URScript output (not deployed):")
        print("─" * 60)
        print(script)
        print("─" * 60 + "\n")
        logger.info("Dry run complete. %d lines generated.", script.count('\n') + 1)
        return

    try:
        script = generate(
            waypoints,
            backend=args.backend,
            output_path=args.output,
            robot_ip=args.robot_ip,
            program_name=args.name,
        )
    except (ConnectionError, RuntimeError, ValueError) as e:
        logger.error("Deploy failed: %s", e)
        sys.exit(1)

    logger.info(
        "Pipeline complete. %d waypoints → %d script lines.",
        len(waypoints),
        script.count('\n') + 1,
    )

    if args.backend == "file":
        logger.info("Script written to: %s", args.output)
        logger.info("Deploy with:  python deploy/ssh_deploy.py --script %s --robot-ip %s",
                    args.output, args.robot_ip)
    else:
        logger.info("Script sent to robot at %s. Robot is now executing.", args.robot_ip)


if __name__ == "__main__":
    main()