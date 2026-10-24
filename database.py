import mysql.connector
import os
import time
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

DB_CONNECT_RETRY_DELAYS = (0.5, 1.0)
TRANSIENT_DB_ERROR_CODES = {
    mysql.connector.errorcode.CR_CONNECTION_ERROR,
    mysql.connector.errorcode.CR_CONN_HOST_ERROR,
    mysql.connector.errorcode.CR_UNKNOWN_HOST,
    mysql.connector.errorcode.CR_SERVER_GONE_ERROR,
    mysql.connector.errorcode.CR_SERVER_LOST,
    mysql.connector.errorcode.CR_SERVER_LOST_EXTENDED,
}


def is_transient_connection_error(error):
    return getattr(error, "errno", None) in TRANSIENT_DB_ERROR_CODES


def get_db_connection():
    for tentativa in range(len(DB_CONNECT_RETRY_DELAYS) + 1):
        try:
            return mysql.connector.connect(**db_config, connection_timeout=5)
        except mysql.connector.Error as error:
            if not is_transient_connection_error(error):
                raise
            if tentativa == len(DB_CONNECT_RETRY_DELAYS):
                raise
            time.sleep(DB_CONNECT_RETRY_DELAYS[tentativa])


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