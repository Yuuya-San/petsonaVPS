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

        # Add healthcare_info column to breed table if it doesn't exist
        try:
            connection.execute(text("""
                ALTER TABLE breed 
                ADD COLUMN healthcare_info TEXT NULL 
                COMMENT 'Detailed healthcare information including vaccination frequency, vet visits, parasite control, dental care, and other medical requirements'
            """))
            print("✅ Added healthcare_info column to breed table")
        except Exception as e:
            if "Duplicate column" not in str(e) and "already exists" not in str(e):
                print(f"⚠️ Error adding healthcare_info column: {e}")
            # else: column already exists, continue

        # Add pet_category column to species table if it doesn't exist
        try:
            connection.execute(text("""
                ALTER TABLE species 
                ADD COLUMN pet_category VARCHAR(100) NOT NULL DEFAULT 'Uncategorized' 
                COMMENT 'Pet category (e.g., Cat, Dog, Bird)'
            """))
            print("✅ Added pet_category column to species table")
        except Exception as e:
            if "Duplicate column" not in str(e) and "already exists" not in str(e):
                print(f"⚠️ Error adding pet_category column: {e}")
            # else: column already exists, continue

        # Add subscription columns to users table if they don't exist
        try:
            connection.execute(text("""
                ALTER TABLE users
                ADD COLUMN subscription_plan VARCHAR(32) NOT NULL DEFAULT 'basic' AFTER `role`
            """))
            print("✅ Added subscription_plan column to users table")
        except Exception as e:
            if "Duplicate column" not in str(e) and "already exists" not in str(e):
                print(f"⚠️ Error adding subscription_plan column: {e}")
        try:
            connection.execute(text("""
                ALTER TABLE users
                ADD COLUMN subscription_status VARCHAR(32) NOT NULL DEFAULT 'active' AFTER subscription_plan
            """))
            print("✅ Added subscription_status column to users table")
        except Exception as e:
            if "Duplicate column" not in str(e) and "already exists" not in str(e):
                print(f"⚠️ Error adding subscription_status column: {e}")
        try:
            connection.execute(text("""
                ALTER TABLE users
                ADD COLUMN subscription_renewal_date DATETIME NULL AFTER subscription_status
            """))
            print("✅ Added subscription_renewal_date column to users table")
        except Exception as e:
            if "Duplicate column" not in str(e) and "already exists" not in str(e):
                print(f"⚠️ Error adding subscription_renewal_date column: {e}")
        try:
            connection.execute(text("""
                ALTER TABLE users
                ADD COLUMN pending_subscription_plan VARCHAR(32) NULL AFTER subscription_renewal_date
            """))
            print("✅ Added pending_subscription_plan column to users table")
        except Exception as e:
            if "Duplicate column" not in str(e) and "already exists" not in str(e):
                print(f"⚠️ Error adding pending_subscription_plan column: {e}")
        try:
            connection.execute(text("""
                ALTER TABLE users
                ADD COLUMN subscription_payment_due DATETIME NULL AFTER pending_subscription_plan
            """))
            print("✅ Added subscription_payment_due column to users table")
        except Exception as e:
            if "Duplicate column" not in str(e) and "already exists" not in str(e):
                print(f"⚠️ Error adding subscription_payment_due column: {e}")
        try:
            connection.execute(text("""
                ALTER TABLE users
                ADD COLUMN quiz_access_count INT NOT NULL DEFAULT 0 AFTER subscription_payment_due
            """))
            print("✅ Added quiz_access_count column to users table")
        except Exception as e:
            if "Duplicate column" not in str(e) and "already exists" not in str(e):
                print(f"⚠️ Error adding quiz_access_count column: {e}")

        # Add PayMongo payment tracking columns to users table
        try:
            connection.execute(text("""
                ALTER TABLE users
                ADD COLUMN paymongo_payment_id VARCHAR(255) UNIQUE NULL AFTER quiz_access_count
            """))
            print("✅ Added paymongo_payment_id column to users table")
        except Exception as e:
            if "Duplicate column" not in str(e) and "already exists" not in str(e):
                print(f"⚠️ Error adding paymongo_payment_id column: {e}")
        
        try:
            connection.execute(text("""
                ALTER TABLE users
                ADD COLUMN paymongo_intent_id VARCHAR(255) UNIQUE NULL AFTER paymongo_payment_id
            """))
            print("✅ Added paymongo_intent_id column to users table")
        except Exception as e:
            if "Duplicate column" not in str(e) and "already exists" not in str(e):
                print(f"⚠️ Error adding paymongo_intent_id column: {e}")
        
        try:
            connection.execute(text("""
                ALTER TABLE users
                ADD COLUMN paymongo_payment_status VARCHAR(32) NULL AFTER paymongo_intent_id
            """))
            print("✅ Added paymongo_payment_status column to users table")
        except Exception as e:
            if "Duplicate column" not in str(e) and "already exists" not in str(e):
                print(f"⚠️ Error adding paymongo_payment_status column: {e}")
        
        try:
            connection.execute(text("""
                ALTER TABLE users
                ADD COLUMN paymongo_last_payment_update DATETIME NULL AFTER paymongo_payment_status
            """))
            print("✅ Added paymongo_last_payment_update column to users table")
        except Exception as e:
            if "Duplicate column" not in str(e) and "already exists" not in str(e):
                print(f"⚠️ Error adding paymongo_last_payment_update column: {e}")
        
        try:
            connection.execute(text("""
                ALTER TABLE users
                ADD COLUMN paymongo_payment_method VARCHAR(50) NULL AFTER paymongo_last_payment_update
            """))
            print("✅ Added paymongo_payment_method column to users table")
        except Exception as e:
            if "Duplicate column" not in str(e) and "already exists" not in str(e):
                print(f"⚠️ Error adding paymongo_payment_method column: {e}")

        # Drop icon column from species table if it exists
        try:
            connection.execute(text("""
                ALTER TABLE species 
                DROP COLUMN icon
            """))
            print("✅ Removed icon column from species table")
        except Exception as e:
            if "Unknown column" not in str(e) and "doesn't exist" not in str(e):
                print(f"⚠️ Error removing icon column: {e}")
            # else: column doesn't exist, continue
