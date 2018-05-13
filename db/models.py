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


Base = declarative_base(cls=DeferredReflection)
Base.__repr__ = _base_repr
metadata = MetaData()


user_connections = Table("user_connections",
                         metadata,
                         Column("id", Integer, primary_key=True),

                         Column("discord_user_id", Integer),
                         Column("connection_user_id", Text),
                         Column("connection_type", Text)
                         )
