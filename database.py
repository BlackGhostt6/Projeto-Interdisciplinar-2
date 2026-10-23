import mysql.connector
import os
from flask import g, has_app_context
from dotenv import load_dotenv
from threading import Lock

# carregar variáveis de ambiente
load_dotenv()

# configurações de conexão com o banco de dados
db_config = {
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'port': int(os.getenv('DB_PORT', 3306))
}

def get_db_connection():
    return mysql.connector.connect(**db_config)


def connection():
    if has_app_context():
        conn = getattr(g, "_database_connection", None)
        if conn is None or not conn.is_connected():
            if conn is not None:
                conn.close()
            conn = get_db_connection()
            g._database_connection = conn
    else:
        conn = get_db_connection()
    cursor = conn.cursor(buffered=True)
    return conn, cursor


def close(conn, cursor):
    try:
        if cursor:
            cursor.close()
    finally:
        if conn and not has_app_context():
            conn.close()


def close_request_connection(exception=None):
    release_request_connection()


def release_request_connection():
    conn = g.pop("_database_connection", None)
    if conn is not None:
        conn.close()


_auth_schema_lock = Lock()
_auth_schema_initialized = False


def ensure_auth_tables():
    global _auth_schema_initialized

    if _auth_schema_initialized:
        return

    with _auth_schema_lock:
        if _auth_schema_initialized:
            return

        conn, cursor = connection()
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS verification_challenges (
                    email VARCHAR(254) NOT NULL,
                    purpose VARCHAR(20) NOT NULL,
                    code_hash CHAR(64) NOT NULL,
                    payload_json LONGTEXT NULL,
                    expires_at DATETIME NOT NULL,
                    attempts TINYINT UNSIGNED NOT NULL DEFAULT 0,
                    PRIMARY KEY (email, purpose),
                    KEY idx_verification_challenges_expiry (expires_at)
                ) ENGINE=InnoDB
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS verification_rate_limits (
                    email VARCHAR(254) NOT NULL,
                    rate_day DATE NOT NULL,
                    send_count TINYINT UNSIGNED NOT NULL DEFAULT 0,
                    PRIMARY KEY (email)
                ) ENGINE=InnoDB
            """)
            conn.commit()
            _auth_schema_initialized = True
        except Exception:
            conn.rollback()
            raise
        finally:
            close(conn, cursor)