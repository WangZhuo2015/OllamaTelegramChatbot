from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

from utils.config import ADMIN_IDS

engine = create_engine('sqlite:///bot.db')
Session = sessionmaker(bind=engine)
db_session = Session()

Base = declarative_base()


def add_admins_to_db():
    for admin_id in ADMIN_IDS:
        user = db_session.query(User).filter_by(platform_user_id=str(admin_id)).first()
        if not user:
            new_admin = User(
                platform="Telegram",
                platform_user_id=str(admin_id),
                is_admin=True,
                is_authorized=True
            )
            db_session.add(new_admin)
    db_session.commit()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    platform = Column(String, nullable=False)
    platform_user_id = Column(String, nullable=False, unique=True)
    username = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)
    is_authorized = Column(Boolean, default=False)
    email = Column(String, nullable=True)
    joined_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_active = Column(DateTime, default=datetime.datetime.utcnow)
    active_session_id = Column(Integer, nullable=True)


class Platform(Base):
    __tablename__ = 'platforms'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)


class Context(Base):
    __tablename__ = 'contexts'

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, nullable=False)
    entry_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)
    context_data = Column(String, nullable=False)  # in json format
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


def init_db():
    db_engine = create_engine('sqlite:///bot.db')
    Base.metadata.create_all(db_engine)
    return sessionmaker(bind=db_engine)()


Base.metadata.create_all(engine)

session = init_db()
