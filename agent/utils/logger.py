"""Logging setup — stdout output is captured by Docker logs."""

import logging
import sys


def setup_logger(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("social-agent")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(handler)

    return logger
