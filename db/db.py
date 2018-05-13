from sqlalchemy_aio import ASYNCIO_STRATEGY
from sqlalchemy import create_engine
from sqlalchemy.schema import CreateTable
from sqlalchemy.exc import OperationalError
from db.models import user_connections


class Database:
    def __init__(self, engine):
        self.engine = engine

    @classmethod
    async def create(cls, conf):
        engine = create_engine(conf["url"], strategy=ASYNCIO_STRATEGY)
        db = cls(engine)
        await db.setup()
        return db

    async def setup(self):
        try:
            await self.engine.execute(CreateTable(user_connections))
        except OperationalError as e:
            pass
