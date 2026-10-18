"""Guard the backtester test tree layout."""

import unittest
from pathlib import Path

BACKTESTER_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = BACKTESTER_ROOT / "src"
TEST_ROOT = BACKTESTER_ROOT / "tests"

ROOT_LAYOUT_TESTS = {
    "test_layout.py",
    "test_skeleton_imports.py",
}


def _source_area_names() -> set[str]:
    return {
        path.relative_to(SOURCE_ROOT).parts[0]
        for path in SOURCE_ROOT.rglob("*.py")
        if "__pycache__" not in path.parts and path.name != "__init__.py"
    }


def _root_module_test_names() -> set[str]:
    return {
        f"test_{path.stem}.py" for path in BACKTESTER_ROOT.glob("*.py") if path.stem != "__init__"
    }


class TestBacktesterTestLayout(unittest.TestCase):
    def test_source_area_test_directories_exist(self) -> None:
        missing = sorted(area for area in _source_area_names() if not (TEST_ROOT / area).is_dir())

        self.assertEqual(
            [],
            missing,
            "Create backtester/tests/<area>/ for each backtester/src/<area>/ package.",
        )

    def test_source_area_tests_are_not_flattened_at_root(self) -> None:
        allowed_root_tests = _root_module_test_names() | ROOT_LAYOUT_TESTS
        flattened_source_tests = sorted(
            path.name for path in TEST_ROOT.glob("test_*.py") if path.name not in allowed_root_tests
        )

        self.assertEqual(
            [],
            flattened_source_tests,
            "Move source-area tests under backtester/tests/<area>/test_*.py.",
        )

    def test_nested_tests_start_with_source_area(self) -> None:
        source_areas = _source_area_names()
        misplaced_tests = []

        for path in TEST_ROOT.rglob("test_*.py"):
            relative_path = path.relative_to(TEST_ROOT)
            if len(relative_path.parts) == 1:
                continue

            if relative_path.parts[0] not in source_areas:
                misplaced_tests.append(str(relative_path))

        self.assertEqual(
            [],
            sorted(misplaced_tests),
            "Nested backtester tests must mirror a first-level backtester/src/ folder.",
        )
