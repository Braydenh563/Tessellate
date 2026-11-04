"""The suite keeps only failing tests' temp folders (pytest.ini).

Before this, a full run left about 7GB of per-test data folders and filled the
CI runner's disk, so the last thousand tests failed with `disk I/O error`.
"""
import configparser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_passing_tests_do_not_keep_their_temp_folders():
    cfg = configparser.ConfigParser()
    cfg.read(ROOT / "pytest.ini")
    assert cfg["pytest"].get("tmp_path_retention_policy") == "failed"


def test_a_tmp_path_is_usable_inside_its_test(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    assert (tmp_path / "a.txt").read_text() == "x"
