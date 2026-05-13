from __future__ import annotations

import logging
from pathlib import Path

import uvicorn


def configure_file_logging() -> Path:
    log_dir = Path(__file__).resolve().parent / "_work"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "debugger-runtime.log"

    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)

    # Mirror uvicorn loggers into the same file.
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

    return log_file


def main() -> None:
    log_file = configure_file_logging()
    print(f"Logging backend runtime to: {log_file}")
    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        log_level="debug",
    )


if __name__ == "__main__":
    main()
