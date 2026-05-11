import pymysql # pyright: ignore[reportMissingModuleSource]
from flask import current_app # pyright: ignore[reportMissingImports]
from sqlalchemy import create_engine # pyright: ignore[reportMissingImports]

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
