import pytest

from cli import build_parser
from importer.config import load_settings


def test_config_loads():
    s = load_settings()
    assert s.config["limits"]["max_upload_mb"] == 200
    assert "백업" in s.config["selection"]["exclude_folders"]


def test_apply_defaults_to_dry_run():
    args = build_parser().parse_args(["apply", "--project", "X"])
    assert args.yes is False


def test_apply_requires_project():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["apply"])
