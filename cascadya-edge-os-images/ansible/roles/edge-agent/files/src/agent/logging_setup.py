import logging
from logging.handlers import RotatingFileHandler


def setup_logging(level: str) -> None:
    logger = logging.getLogger()
    logger.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        "agent.log", maxBytes=5_000_000, backupCount=3
    )
    file_handler.setFormatter(formatter)

    logger.handlers.clear()
    logger.addHandler(console)
    logger.addHandler(file_handler)
