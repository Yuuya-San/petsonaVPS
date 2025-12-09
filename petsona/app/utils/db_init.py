import pymysql
from flask import current_app
from sqlalchemy import create_engine

def ensure_database_exists():
    """
    Ensures the MySQL database exists before the app starts.
    Creates the database if missing.
    """

    db_user = current_app.config["DB_USERNAME"]
    db_pass = current_app.config["DB_PASSWORD"]
    db_host = current_app.config["DB_HOST"]
    db_name = current_app.config["DB_NAME"]

    # Connect to MySQL server (NOT to a database)
    connection = pymysql.connect(
        host=db_host,
        user=db_user,
        password=db_pass,
        autocommit=True
    )

    cursor = connection.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`;")
    cursor.close()
    connection.close()


def create_tables(db):
    """
    Ensures all SQLAlchemy models create their tables automatically.
    """

    engine = create_engine(current_app.config["SQLALCHEMY_DATABASE_URI"])

    # Connect and create tables if not exist
    db.metadata.create_all(engine)
