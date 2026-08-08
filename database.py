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