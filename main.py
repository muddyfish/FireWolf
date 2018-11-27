import os
import config
import logger
import asyncio
from db.db import Database
import bot
import oauth2
from web.web_service import WebService

__version__ = "0.0.1"


class Main:
    def __init__(self):
        conf_file = os.getenv("FIREBOT_CONFIG", "config.yaml")
        self.config = config.Config.from_file(conf_file)

        self.log = logger.initialise(self.config.logging_level)
        self.log.info(f"Starting FireBot v{__version__}")

        self.log.debug("Initialising asyncio")
        tasks = (self.startup(), )
        self.init_asyncio(tasks)

    def init_asyncio(self, tasks):
        loop = asyncio.get_event_loop()
        for task in tasks:
            asyncio.async(task)
        loop.run_forever()
        loop.close()

    async def startup(self):
        self.log.debug("Starting DB")
        self.db = await Database.create(self.config.db)
        self.log.debug("Starting Discord Bot")
        self.bot = await bot.initialise(self.config.discord, self.config.steam_api_key, self.db)
        self.log.debug("Starting Oauth service")
        self.oauth = oauth2.Oauth2(self.bot, self.config.discord)
        self.log.debug("Starting Discord Bot")
        self.app = WebService(self.bot, self.oauth, self.config.web)


if __name__ == "__main__":
    Main()
