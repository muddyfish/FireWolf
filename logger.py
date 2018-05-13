import atexit
import logging
import sys
from traceback import print_tb



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
    exceptions = create_logger("fire_bot", formatter, level, True, True)
    sys.excepthook = _exception_handler(exceptions)
    create_logger("discord", formatter, level, True, True)
    create_logger("aiohttp.server", formatter, level, True, True)
    return exceptions


def create_logger(name, formatter, level, stream=False, file=False):
    logger = logging.getLogger(name)
    logger.setLevel(level)

    handlers = []
    if stream:
        handlers.append(logging.StreamHandler())
    if file:
        handlers.append(logging.FileHandler(f"{name}.log"))

    for handler in handlers:
        atexit.register(handler.close)
        handler.setLevel(level)
        handler.setFormatter(formatter)

        logger.addHandler(handler)

    return logger
