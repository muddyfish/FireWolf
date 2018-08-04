from sqlalchemy_aio import ASYNCIO_STRATEGY
from sqlalchemy import create_engine
from sqlalchemy.sql import text
from db.models import UserConnections

class Null:
    def __repr__(self):
        return "NULL"


class Database:
    def __init__(self, engine):
        self.engine = engine

    @classmethod
    async def create(cls, conf):
        engine = create_engine(conf["url"], strategy=ASYNCIO_STRATEGY)
        db = cls(engine)
        return db

    async def insert(self, model):
        stmt = f"INSERT INTO {model.__tablename__} VALUES {tuple(getattr(model, name) if getattr(model, name) is not None else Null() for name in model.__table__.columns.keys())};"
        await self.engine.execute(stmt)

    async def get_guild_settings(self, guild_id):
        stmt = text("SELECT role_id, add_on_authenticate, require_steam FROM guild_data where guild_id=:guild_id;")
        res = await self.engine.execute(stmt, guild_id=guild_id)
        res = await res.fetchone()
        if res is None:
            return None, None, None
        role_id, add_on_authenticate, require_steam = res
        return role_id, add_on_authenticate, require_steam

    async def set_guild_settings(self, guild_id, role_id, add_on_authenticate, require_steam):
        stmt = text("UPDATE guild_data SET role_id=:role_id, add_on_authenticate=:add_on_authenticate, require_steam=:require_steam WHERE guild_id=:guild_id")
        await self.engine.execute(stmt,
                                  guild_id=guild_id,
                                  role_id=role_id,
                                  add_on_authenticate=add_on_authenticate,
                                  require_steam=require_steam)

    async def get_log_channel(self, guild_id):
        stmt = text("SELECT log_id FROM guild_data where guild_id=:guild_id;")
        res = await self.engine.execute(stmt, guild_id=guild_id)
        res = await res.fetchone()
        return res[0]

    async def add_connections(self, member, connections):
        for connection in connections:
            db_row = UserConnections(guild_id=member.guild.id,
                                     discord_user_id=member.id,
                                     connection_type=connection["type"],
                                     connection_user_id=connection["id"])
            await self.insert(db_row)

    async def get_connections(self, guild_id):
        stmt = text("SELECT connection_type, connection_user_id FROM user_connections where guild_id=:guild_id;")
        res = await self.engine.execute(stmt, guild_id=guild_id)
        return await res.fetchall()