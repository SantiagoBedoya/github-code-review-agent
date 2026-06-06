from __future__ import annotations


_LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "logging.Formatter",
            "fmt": "%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
            "datefmt": "%H:%M:%S",
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
    },
    "root": {"handlers": ["default"], "level": "INFO"},
    "loggers": {
        "github_code_review": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "github_code_review.agents": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "github_code_review.github": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["default"], "level": "INFO", "propagate": False},
    },
}


def main() -> None:
    import uvicorn

    uvicorn.run(
        "github_code_review.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_config=_LOG_CONFIG,
    )


if __name__ == "__main__":
    main()
