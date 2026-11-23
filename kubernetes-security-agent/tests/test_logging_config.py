import logging
from pathlib import Path

from agent.logging_config import configure_logging


def test_file_logging_rotates_and_stays_bounded(monkeypatch, tmp_path: Path) -> None:
    log_file = tmp_path / "agent.log"
    monkeypatch.setenv("AGENT_LOG_FILE", str(log_file))
    monkeypatch.setenv("AGENT_LOG_MAX_BYTES", "300")
    monkeypatch.setenv("AGENT_LOG_BACKUP_COUNT", "2")
    configure_logging()

    logger = logging.getLogger("rotation-test")
    for index in range(20):
        logger.info("bounded log message", extra={"index": index, "padding": "x" * 80})

    files = sorted(tmp_path.glob("agent.log*"))
    assert log_file in files
    assert any(path.name == "agent.log.1" for path in files)
    assert len(files) <= 3
