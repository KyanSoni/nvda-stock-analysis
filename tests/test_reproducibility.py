"""Reproducibility from saved raw data, with no network access at all."""
import pytest

import fetch_sec
import run_m1
from common import sha256_file
from conftest import SYNTHETIC_SNAPSHOT
from run_m1 import OUTPUT_FILES


@pytest.fixture
def no_network():
    """Make any HTTP call fail loudly, so a test cannot pass by quietly reaching SEC."""
    original = fetch_sec.requests.get

    def blocked(*args, **kwargs):
        raise AssertionError("network access attempted in an offline test")

    fetch_sec.requests.get = blocked
    try:
        yield
    finally:
        fetch_sec.requests.get = original


def test_same_snapshot_gives_byte_identical_outputs(tmp_path, no_network):
    out_a, out_b = tmp_path / "a", tmp_path / "b"
    assert run_m1.main(["--source", "snapshot", "--snapshot", str(SYNTHETIC_SNAPSHOT), "--out", str(out_a)]) == 0
    assert run_m1.main(["--source", "snapshot", "--snapshot", str(SYNTHETIC_SNAPSHOT), "--out", str(out_b)]) == 0
    for name in OUTPUT_FILES.values():
        assert sha256_file(out_a / name) == sha256_file(out_b / name), f"{name} differs between runs"


def test_raw_snapshot_is_never_modified(tmp_path, no_network):
    before = sha256_file(SYNTHETIC_SNAPSHOT)
    run_m1.main(["--source", "snapshot", "--snapshot", str(SYNTHETIC_SNAPSHOT), "--out", str(tmp_path)])
    assert sha256_file(SYNTHETIC_SNAPSHOT) == before


def test_run_manifest_records_snapshot_hash(tmp_path, no_network):
    import json
    run_m1.main(["--source", "snapshot", "--snapshot", str(SYNTHETIC_SNAPSHOT), "--out", str(tmp_path)])
    manifest = json.loads((tmp_path / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["snapshot_sha256"] == sha256_file(SYNTHETIC_SNAPSHOT)
    assert manifest["source_mode"] == "snapshot" and manifest["checks_passed"] is True
    assert set(manifest["output_sha256"]) == set(OUTPUT_FILES)
