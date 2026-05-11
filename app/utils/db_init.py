import os
import pymysql # pyright: ignore[reportMissingModuleSource]
from flask import current_app # pyright: ignore[reportMissingImports]
from sqlalchemy import create_engine # pyright: ignore[reportMissingImports]
from sqlalchemy.engine.url import make_url # pyright: ignore[reportMissingImports]


def _parse_database_url():
    """Parse SQLALCHEMY_DATABASE_URI or DB_* config values."""
    db_uri = current_app.config.get("SQLALCHEMY_DATABASE_URI")
    if db_uri:
        try:
            parsed = make_url(db_uri)
            return {
                "drivername": parsed.drivername,
                "username": parsed.username,
                "password": parsed.password,
                "host": parsed.host or "localhost",
                "port": parsed.port or 3306,
                "database": parsed.database,
            }
        except Exception:
            pass

    return {
        "drivername": "mysql",
        "username": current_app.config.get("DB_USERNAME") or os.getenv("DB_USERNAME"),
        "password": current_app.config.get("DB_PASSWORD") or os.getenv("DB_PASSWORD"),
        "host": current_app.config.get("DB_HOST") or os.getenv("DB_HOST", "localhost"),
        "port": int(current_app.config.get("DB_PORT") or os.getenv("DB_PORT", 3306)),
        "database": current_app.config.get("DB_NAME") or os.getenv("DB_NAME"),
    }


def ensure_database_exists():
    """
    Ensures the MySQL database exists before the app starts.
    Creates the database if missing.
    """

    parsed = _parse_database_url()
    db_user = parsed["username"]
    db_pass = parsed["password"]
    db_host = parsed["host"]
    db_port = parsed["port"]
    db_name = parsed["database"]

    if not all([db_user, db_pass, db_host, db_name]):
        raise RuntimeError(
            "Database credentials are not fully configured. "
            "Set SQLALCHEMY_DATABASE_URI or DB_USERNAME, DB_PASSWORD, DB_HOST, DB_NAME."
        )

    # Connect to MySQL server (NOT to a database)
    connection = pymysql.connect(
        host=db_host,
        port=db_port,
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
    
    # Add any missing columns to existing tables
    add_missing_columns(engine)


def add_missing_columns(engine):
    """
    Adds missing columns to existing tables
    """
    from sqlalchemy import text # pyright: ignore[reportMissingImports]
    
    with engine.begin() as connection:
        # Add is_open column to merchants table if it doesn't exist
        try:
            connection.execute(text("""
                ALTER TABLE merchants 
                ADD COLUMN is_open BOOLEAN DEFAULT 1 
                AFTER is_verified
            """))
            print("✅ Added is_open column to merchants table")
        except Exception as e:
            if "Duplicate column" not in str(e) and "already exists" not in str(e):
                print(f"⚠️ Error adding is_open column: {e}")
            # else: column already exists, continue
        
        # Add is_24h column to merchants table if it doesn't exist
        try:
            connection.execute(text("""
                ALTER TABLE merchants 
                ADD COLUMN is_24h BOOLEAN DEFAULT 0 
                AFTER closing_time
            """))
            print("✅ Added is_24h column to merchants table")
        except Exception as e:
            if "Duplicate column" not in str(e) and "already exists" not in str(e):
                print(f"⚠️ Error adding is_24h column: {e}")
            # else: column already exists, continue
            else:
                print("is_open column already exists in merchants table")
