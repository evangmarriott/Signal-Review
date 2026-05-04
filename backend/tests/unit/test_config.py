from pathlib import Path

from src.config import Settings


def test_settings_parses_comma_separated_cors_origins_from_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "CORS_ORIGINS=http://localhost:5173,https://signalreview.example\n",
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.get_cors_origins() == [
        "http://localhost:5173",
        "https://signalreview.example",
    ]
