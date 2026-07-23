import logging

from app.system.logging_config import configure_logging


def test_logging_config_writes_diagnostic_file(tmp_path):
    root = logging.getLogger()
    previous_level = root.level
    try:
        log_path = configure_logging(tmp_path)
        logger = logging.getLogger("app.cloud.diagnostic_test")
        logger.info("cloud.sync.test organization_id=1")
        for handler in root.handlers:
            if getattr(handler, "name", None) == "smartfile-file":
                handler.flush()

        content = log_path.read_text(encoding="utf-8")
        assert "cloud.sync.test organization_id=1" in content
    finally:
        for handler in root.handlers[:]:
            if getattr(handler, "name", None) == "smartfile-file":
                root.removeHandler(handler)
                handler.close()
        root.setLevel(previous_level)
