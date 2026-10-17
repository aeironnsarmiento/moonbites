import logging


APP_LOGGER_NAME = __name__.rsplit(".", 2)[0]  # "app", or "backend.app" when packaged


def configure_logging() -> None:
    """Let the app's own INFO records (such as the blog fallback log) reach stdout.

    Only the app's package logger is touched; third-party libraries keep their
    defaults. A handler is added only when nothing upstream would print the
    records, so a host that configures the root logger is not duplicated.
    """
    app_logger = logging.getLogger(APP_LOGGER_NAME)
    if app_logger.level == logging.NOTSET:
        app_logger.setLevel(logging.INFO)
    if not app_logger.handlers and not logging.getLogger().handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        app_logger.addHandler(handler)
