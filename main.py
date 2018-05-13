import os
import config
import logger
import asyncio
from db.db import Database

__version__ = "0.0.1"


class Main:
    def __init__(self):
        conf_file = os.getenv("FIREBOT_CONFIG", "config.yaml")
        self.config = config.Config.from_file(conf_file)

        self.log = logger.initialise(self.config.logging_level)
        self.log.info(f"Starting FireBot v{__version__}")

        self.log.debug("Initialising asyncio")
        tasks = (self.start_db(), self.start_bot())
        self.init_asyncio(tasks)

    def init_asyncio(self, tasks):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.wait([loop.create_task(i) for i in tasks]))
        loop.close()

    async def start_db(self):
        self.log.debug("Starting DB")
        self.db = await Database.create(self.config.db)

    async def start_bot(self):
        self.log.debug("Starting Discord Bot")


if __name__ == "__main__":
    Main()
