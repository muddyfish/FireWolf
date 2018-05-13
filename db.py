from sqlalchemy_aio import ASYNCIO_STRATEGY
from sqlalchemy import Column, Integer, MetaData, Table, Text, create_engine, select
from sqlalchemy.schema import CreateTable, DropTable


class Database:
    def __init__(self, engine):
        self.engine = engine

    @classmethod
    async def create(cls, conf):
        engine = create_engine(conf["url"], strategy=ASYNCIO_STRATEGY)
        db = cls()
        return db
