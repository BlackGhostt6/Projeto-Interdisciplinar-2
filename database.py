import mysql.connector
import os
from dotenv import load_dotenv

# carregar variáveis de ambiente
load_dotenv()

# configurações de conexão com o banco de dados
db_config = {
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD')
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

def connection():
    conn = get_db_connection()
    cursor = conn.cursor()
    return conn, cursor

def close(cursor, conn):
    if cursor:
            cursor.close()
    if conn:
        conn.close()