import os
import config
import logger

__version__ = "0.0.1"


class Main:
    def __init__(self):
        conf_file = os.getenv("COGS_CONFIG", "config.yaml")
        self.config = config.Config.from_file(conf_file)
        print(self.config)

        log = logger.initialise(self.config.logging_level)
        log.info(f"Starting CoGS v{__version__}")


if __name__ == "__main__":
    Main()
