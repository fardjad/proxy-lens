from __future__ import annotations

from pathlib import Path

import pytest

from proxylens_server import cli


def test_parse_bind_returns_host_and_port() -> None:
    assert cli._parse_bind("0.0.0.0:9000") == ("0.0.0.0", 9000)


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("localhost", "bind address"),
        ("localhost:not-a-port", "port must be an integer"),
        ("localhost:70000", "between 0 and 65535"),
    ],
)
def test_parse_bind_rejects_invalid_values(value: str, message: str) -> None:
    with pytest.raises(Exception) as exc_info:
        cli._parse_bind(value)

    assert message in str(exc_info.value)


def test_main_uses_bind_and_runtime_options(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}

    def fake_run(app: object, **kwargs: object) -> None:
        captured["app"] = app
        captured["kwargs"] = kwargs

    monkeypatch.setattr(cli.uvicorn, "run", fake_run)
    monkeypatch.delenv(cli.DATA_DIR_ENV_VAR, raising=False)
    monkeypatch.delenv(cli.FILTER_SCRIPT_ENV_VAR, raising=False)

    exit_code = cli.main(
        [
            "--bind",
            "0.0.0.0:9000",
            "--log-level",
            "debug",
            "--workers",
            "3",
            "--data-dir",
            str(tmp_path / "data"),
            "--filter-script",
            str(tmp_path / "filter.py"),
            "--no-access-log",
        ]
    )

    assert exit_code == 0
    kwargs = captured["kwargs"]
    assert kwargs == {
        "host": "0.0.0.0",
        "port": 9000,
        "log_level": "debug",
        "reload": False,
        "workers": 3,
        "access_log": False,
        "factory": True,
    }
    assert captured["app"] == "proxylens_server.cli:create_app_from_cli"
    assert cli.os.environ[cli.DATA_DIR_ENV_VAR] == str((tmp_path / "data").resolve())
    assert cli.os.environ[cli.FILTER_SCRIPT_ENV_VAR] == str(
        (tmp_path / "filter.py").resolve()
    )


def test_main_uses_default_host_and_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(app: object, **kwargs: object) -> None:
        captured["app"] = app
        captured["kwargs"] = kwargs

    monkeypatch.setattr(cli.uvicorn, "run", fake_run)
    monkeypatch.delenv(cli.DATA_DIR_ENV_VAR, raising=False)
    monkeypatch.delenv(cli.FILTER_SCRIPT_ENV_VAR, raising=False)

    exit_code = cli.main([])

    assert exit_code == 0
    assert captured["app"] == "proxylens_server.cli:create_app_from_cli"
    assert captured["kwargs"] == {
        "host": cli.DEFAULT_HOST,
        "port": cli.DEFAULT_PORT,
        "log_level": "info",
        "reload": False,
        "workers": 1,
        "access_log": True,
        "factory": True,
    }


def test_create_app_from_cli_reads_config_from_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}

    def fake_create_app(config: object) -> str:
        captured["config"] = config
        return "app"

    monkeypatch.setenv(cli.DATA_DIR_ENV_VAR, str(tmp_path / "data"))
    monkeypatch.setenv(cli.FILTER_SCRIPT_ENV_VAR, str(tmp_path / "filter.py"))
    monkeypatch.setattr(cli, "create_app", fake_create_app)

    app = cli.create_app_from_cli()

    assert app == "app"
    config = captured["config"]
    assert config.data_dir == (tmp_path / "data").resolve()
    assert config.filter_script == (tmp_path / "filter.py").resolve()


def test_main_rejects_non_positive_workers() -> None:
    with pytest.raises(SystemExit, match="2"):
        cli.main(["--workers", "0"])


def test_main_rejects_reload_with_multiple_workers() -> None:
    with pytest.raises(SystemExit, match="2"):
        cli.main(["--reload", "--workers", "2"])
