import os

class Config:
    SECRET_KEY = "Task-Hive_secret_key"

    SQLALCHEMY_DATABASE_URI = "sqlite:///Task-Hive.db"

    SQLALCHEMY_TRACK_MODIFICATIONS = False
