from sqlalchemy import Column, Integer, String, Text, JSON, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Ad(Base):
    __tablename__ = 'ads'
    id = Column(Integer, primary_key=True, autoincrement=True)
    text = Column(Text)
    photos = Column(JSON)
    referrer = Column(Text)
    referrer_comment = Column(Text)
    date_added = Column(DateTime, default=datetime.now())
    admin_added = Column(Integer)

class LastAds(Base):
    __tablename__ = 'last_ads'
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer)
    messages = Column(JSON)

class Settings(Base):
    __tablename__ = 'settings'
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(Text, nullable=False)
    value = Column(JSON, nullable=False)