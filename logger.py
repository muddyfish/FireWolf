import atexit
import logging
import sys
from traceback import print_tb

_LOGGER_NAME = "FireWolf"


class LogWriter:
    _logger = logging.getLogger(_LOGGER_NAME)

    def log(self, level:int, message:str) -> None:
        self._logger.log(level, message)


def _exception_handler(logger):
    def _log_uncaught_exception(exc_type, exc_val, traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_val, traceback)
        else:
            logger.critical(str(exc_val) or exc_type.__name__)
            if __debug__:
                print_tb(traceback)

            sys.exit(1)

    return _log_uncaught_exception


def initialise(level):
    formatter = logging.Formatter(
        fmt="%(asctime)s\t%(levelname)s\t%(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ%z"
    )

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level)

    stream_handler = logging.StreamHandler()
    file_handler = logging.FileHandler("fire_bot.log")

    for handler in (stream_handler, file_handler):
        atexit.register(handler.close)
        handler.setLevel(level)
        handler.setFormatter(formatter)

        logger.addHandler(handler)

    sys.excepthook = _exception_handler(logger)

    return logger
