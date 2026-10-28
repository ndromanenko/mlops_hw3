import sys
from pathlib import Path
from typing import Any

from loguru import logger

LOG_DIR = Path(__file__).parent / "logs"

CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)
FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
    "{name}:{function}:{line} - {message}"
)


def setup_logger(
    level: str = "INFO",
    serialize: bool = False,
    diagnose: bool = False,
) -> None:
    """Configure loguru logger with console and rotating file sinks."""
    logger.remove()

    logger.add(
        sys.stderr,
        level=level,
        format=CONSOLE_FORMAT,
        colorize=True,
        serialize=serialize,
        backtrace=True,
        diagnose=diagnose,
        enqueue=True,
    )

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.add(
        LOG_DIR / "service_{time:YYYY-MM-DD}.log",
        level=level,
        format=FILE_FORMAT,
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        serialize=serialize,
        backtrace=True,
        diagnose=diagnose,
        enqueue=True,
    )


def get_logger(name: str | None = None) -> Any:
    """Get a logger instance with optional context binding."""
    if name:
        return logger.bind(name=name)
    return logger
