from sqlalchemy.ext.declarative import declarative_base, DeferredReflection
from sqlalchemy import Integer, Text, MetaData, Column, Table, Date, ForeignKey, Boolean


def _base_repr(self):
    """
    Monkeypatch the Base object so it's eval-able
    :param self:
    :return str:
    """
    params = ", ".join("{}={}".format(column.key, repr(getattr(self, column.key)))
                       for column in self.__table__.columns)

    return f"{self.__class__.__name__}({params})"


Base = declarative_base()
Base.__repr__ = _base_repr
metadata = MetaData()


class UserConnections(Base):
    __tablename__ = "user_connections"
    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer)
    discord_user_id = Column(Integer)
    connection_user_id = Column(Text)
    connection_type = Column(Text)


class GuildData(Base):
    __tablename__ = "guild_data"
    id = Column(Integer, primary_key=True)
    guild_id = Column(Integer)
    log_id = Column(Integer)
    role_id = Column(Integer)
    add_on_authenticate = Column(Boolean)
    require_steam = Column(Boolean)
