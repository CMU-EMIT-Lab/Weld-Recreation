"""
test_codegen.py
---------------
Tests for gcode_parser and urscript_gen.
Run with:  python -m pytest codegen/tests/test_codegen.py -v
"""

import math
import tempfile
from pathlib import Path
import pytest
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from gcode_parser import parse_gcode, WeldWaypoint, MM_TO_M
from urscript_gen import build_urscript, _fmt_pose, _movel


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

SIMPLE_GCODE = """\
; Simple two-pass weld
G0 X100.0 Y50.0 Z80.0        ; rapid approach
G1 X100.0 Y50.0 Z5.0 F200    ; plunge
G1 X200.0 Y50.0 Z5.0 F150    ; weld pass
G0 X200.0 Y50.0 Z80.0        ; retract
"""

GCODE_WITH_ORIENTATION = """\
G0 X0.0 Y0.0 Z50.0
G1 X0.0 Y0.0 Z2.0 F180 A180.0 B0.0 C0.0
G1 X100.0 Y0.0 Z2.0 F150 A180.0 B0.0 C0.0
G0 X100.0 Y0.0 Z50.0
"""

GCODE_MULTI_SEGMENT = """\
; Two separate weld segments
G0 X0.0 Y0.0 Z50.0
G1 X0.0 Y0.0 Z5.0 F200
G1 X50.0 Y0.0 Z5.0 F150
G0 X50.0 Y0.0 Z50.0
G0 X100.0 Y0.0 Z50.0
G1 X100.0 Y0.0 Z5.0 F200
G1 X150.0 Y0.0 Z5.0 F150
G0 X150.0 Y0.0 Z50.0
"""


def write_temp_gcode(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".gcode", delete=False, encoding="utf-8"
    )
    f.write(content)
    f.close()
    return Path(f.name)


# ──────────────────────────────────────────────────────────────────────────────
# Parser tests
# ──────────────────────────────────────────────────────────────────────────────

class TestGcodeParser:

    def test_basic_parse_returns_waypoints(self):
        path = write_temp_gcode(SIMPLE_GCODE)
        wps = parse_gcode(path)
        assert len(wps) == 4

    def test_gcode_types_correct(self):
        path = write_temp_gcode(SIMPLE_GCODE)
        wps = parse_gcode(path)
        assert wps[0].is_weld is False   # G0
        assert wps[1].is_weld is True    # G1 plunge
        assert wps[2].is_weld is True    # G1 weld
        assert wps[3].is_weld is False   # G0 retract

    def test_position_mm_to_meters(self):
        path = write_temp_gcode(SIMPLE_GCODE)
        wps = parse_gcode(path)
        # First waypoint: X100, Y50, Z80 in mm → 0.1, 0.05, 0.08 in m
        assert abs(wps[0].pose[0] - 0.1) < 1e-6
        assert abs(wps[0].pose[1] - 0.05) < 1e-6
        assert abs(wps[0].pose[2] - 0.08) < 1e-6

    def test_feed_rate_converted_to_m_per_s(self):
        path = write_temp_gcode(SIMPLE_GCODE)
        wps = parse_gcode(path)
        # G1 at F150 mm/min = 150/60000 m/s = 0.0025 m/s
        expected = 150 / 60000
        assert abs(wps[2].speed - expected) < 1e-6

    def test_last_weld_point_zero_blend(self):
        path = write_temp_gcode(SIMPLE_GCODE)
        wps = parse_gcode(path)
        # wps[2] is last weld before retract — blend must be 0
        assert wps[2].blend_radius == 0.0

    def test_final_waypoint_zero_blend(self):
        path = write_temp_gcode(SIMPLE_GCODE)
        wps = parse_gcode(path)
        assert wps[-1].blend_radius == 0.0

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            parse_gcode("/nonexistent/path/weld.gcode")

    def test_empty_gcode_raises(self):
        path = write_temp_gcode("; only comments\n\n")
        with pytest.raises(ValueError, match="No valid waypoints"):
            parse_gcode(path)

    def test_comments_stripped(self):
        gcode = "G0 X10.0 Y20.0 Z30.0 ; this is a comment\n"
        path = write_temp_gcode(gcode)
        wps = parse_gcode(path)
        assert len(wps) == 1
        assert abs(wps[0].pose[0] - 0.01) < 1e-6

    def test_multi_segment_weld(self):
        path = write_temp_gcode(GCODE_MULTI_SEGMENT)
        wps = parse_gcode(path)
        weld_points = [w for w in wps if w.is_weld]
        rapid_points = [w for w in wps if not w.is_weld]
        assert len(weld_points) == 4
        assert len(rapid_points) == 4

    def test_speed_clamped_to_max(self):
        # F=99999 mm/min is way over max weld speed
        gcode = "G1 X100.0 Y0.0 Z5.0 F99999\n"
        path = write_temp_gcode(gcode)
        wps = parse_gcode(path)
        from gcode_parser import MAX_WELD_SPEED
        assert wps[0].speed <= MAX_WELD_SPEED

    def test_speed_clamped_to_min(self):
        gcode = "G1 X100.0 Y0.0 Z5.0 F0.001\n"
        path = write_temp_gcode(gcode)
        wps = parse_gcode(path)
        from gcode_parser import MIN_WELD_SPEED
        assert wps[0].speed >= MIN_WELD_SPEED

    def test_rapid_speed_overrides_feed(self):
        from gcode_parser import RAPID_SPEED
        gcode = "G0 X100.0 Y0.0 Z50.0 F9999\n"
        path = write_temp_gcode(gcode)
        wps = parse_gcode(path)
        assert wps[0].speed == RAPID_SPEED


# ──────────────────────────────────────────────────────────────────────────────
# URScript generator tests
# ──────────────────────────────────────────────────────────────────────────────

class TestUrscriptGen:

    def _simple_waypoints(self) -> list[WeldWaypoint]:
        return [
            WeldWaypoint(pose=[0.1, 0.05, 0.08, math.pi, 0, 0], speed=0.3,
                         is_weld=False, blend_radius=0.005, label="approach"),
            WeldWaypoint(pose=[0.1, 0.05, 0.005, math.pi, 0, 0], speed=0.005,
                         is_weld=True, blend_radius=0.002, label="plunge"),
            WeldWaypoint(pose=[0.2, 0.05, 0.005, math.pi, 0, 0], speed=0.004,
                         is_weld=True, blend_radius=0.0, label="weld_end"),
            WeldWaypoint(pose=[0.2, 0.05, 0.08, math.pi, 0, 0], speed=0.3,
                         is_weld=False, blend_radius=0.0, label="retract"),
        ]

    def test_script_is_string(self):
        script = build_urscript(self._simple_waypoints())
        assert isinstance(script, str)
        assert len(script) > 0

    def test_script_has_def_end(self):
        script = build_urscript(self._simple_waypoints())
        assert "def weld_program():" in script
        assert script.strip().endswith("end")

    def test_custom_program_name(self):
        script = build_urscript(self._simple_waypoints(), program_name="test_run_1")
        assert "def test_run_1():" in script

    def test_torch_on_present_for_weld(self):
        script = build_urscript(self._simple_waypoints())
        from urscript_gen import TORCH_DIGITAL_OUT
        assert f"set_digital_out({TORCH_DIGITAL_OUT}, True)" in script

    def test_torch_off_present(self):
        script = build_urscript(self._simple_waypoints())
        from urscript_gen import TORCH_DIGITAL_OUT
        assert f"set_digital_out({TORCH_DIGITAL_OUT}, False)" in script

    def test_movel_in_script(self):
        script = build_urscript(self._simple_waypoints())
        assert "movel(" in script

    def test_movej_for_approach(self):
        script = build_urscript(self._simple_waypoints())
        assert "movej(" in script

    def test_pose_format(self):
        pose = [0.1, 0.05, 0.005, math.pi, 0.0, 0.0]
        formatted = _fmt_pose(pose)
        assert formatted.startswith("p[")
        assert formatted.endswith("]")
        assert formatted.count(",") == 5

    def test_pose_wrong_length_raises(self):
        with pytest.raises(ValueError):
            _fmt_pose([0.1, 0.2, 0.3])

    def test_empty_waypoints_raises(self):
        with pytest.raises(ValueError, match="empty"):
            build_urscript([])

    def test_retract_in_script(self):
        script = build_urscript(self._simple_waypoints())
        assert "Retract" in script or "retract" in script.lower()

    def test_safety_init_torch_off(self):
        script = build_urscript(self._simple_waypoints())
        from urscript_gen import TORCH_DIGITAL_OUT
        # First occurrence of digital_out should be False (safety init)
        first_digital = script.find(f"set_digital_out({TORCH_DIGITAL_OUT}")
        snippet = script[first_digital:first_digital + 60]
        assert "False" in snippet

    def test_script_no_weld_segments(self):
        """All-rapid path should still produce valid script with no torch fire."""
        wps = [
            WeldWaypoint(pose=[0.1, 0.0, 0.1, math.pi, 0, 0], speed=0.3,
                         is_weld=False, blend_radius=0.0, label="r1"),
            WeldWaypoint(pose=[0.2, 0.0, 0.1, math.pi, 0, 0], speed=0.3,
                         is_weld=False, blend_radius=0.0, label="r2"),
        ]
        script = build_urscript(wps)
        from urscript_gen import TORCH_DIGITAL_OUT
        assert f"set_digital_out({TORCH_DIGITAL_OUT}, True)" not in script


# ──────────────────────────────────────────────────────────────────────────────
# Integration: parse → generate
# ──────────────────────────────────────────────────────────────────────────────

class TestIntegration:

    def test_parse_then_generate_produces_valid_script(self):
        path = write_temp_gcode(SIMPLE_GCODE)
        wps = parse_gcode(path)
        script = build_urscript(wps)
        assert "def weld_program():" in script
        assert "movel(" in script
        assert script.strip().endswith("end")

    def test_file_backend_writes_file(self):
        from urscript_gen import generate
        path = write_temp_gcode(SIMPLE_GCODE)
        wps = parse_gcode(path)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "test.script"
            generate(wps, backend="file", output_path=out)
            assert out.exists()
            content = out.read_text()
            assert "def weld_program():" in content

    def test_full_pipeline_waypoint_count_preserved(self):
        path = write_temp_gcode(GCODE_MULTI_SEGMENT)
        wps = parse_gcode(path)
        script = build_urscript(wps)
        # All 8 waypoints should produce 8 movel calls
        assert script.count("movel(") == 8
        