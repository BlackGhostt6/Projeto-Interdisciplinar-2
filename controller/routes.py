from flask import Blueprint, render_template, request, jsonify, send_file, session, redirect, url_for
from database import get_db_connection, connection, close
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta, date

load_dotenv()
routes = Blueprint("routes", __name__)

# criar funções uteis pra evitar ficar reescrevendo codigo

def getResume():
    conn, cursor = connection()
    pais = "japao"

    cursor.execute("""
    select cust_med from paises where pais = %s
""", (pais,))
    custo = cursor.fetchone()[0]

    cursor.execute("""
    select pais
        from paises
        where pais = %s
""", (pais,))
    destino = cursor.fetchone()[0]

    close(conn, cursor)
    return {
        "custo": custo,
        "origem": "Brasil",
        "destino": destino
    }
    

# ====================== rotas de exibição ======================

# Mostra a página inicial
@routes.route("/")
def index():
    resume = getResume()
    return render_template('index.html', resume = resume)

# ====================== ROTAS DE GET ======================

# Busca por um ou mais países e retorna um json
@routes.route("/api/get-country", methods=['GET'])
def getCountry():
    conn, cursor = connection()
    pais = request.args.get('pais')
    
    if pais:
        cursor.execute("""
            SELECT * 
            FROM paises 
            WHERE pais = %s
        """,(pais,))
        resultado=cursor.fetchone()
    else:
        cursor.execute("select * from paises")
        resultado=cursor.fetchall()
    
    close(conn, cursor)
    
    return jsonify(resultado)

# Busca por uma ou mais anotações e retorna um json
@routes.route("/api/get-note", methods=['GET'])
def getNote():
    conn, cursor = connection()
    nota = request.args.get('id_nota')
    
    if nota:
        cursor.execute("""
            SELECT * 
            FROM anotacoes 
            WHERE id_nota = %s
        """,(nota,))
        resultado=cursor.fetchone()
    else:
        cursor.execute("select * from anotacoes")
        resultado=cursor.fetchall()
    
    close(conn, cursor)
    
    return jsonify(resultado)

# Busca por um ou mais usuários e retorna um json
@routes.route("/api/get-user", methods=['GET'])
def getUser():
    conn, cursor = connection()
    usuario = request.args.get('id_user')

    if usuario:
        cursor.execute("""
            SELECT * 
            FROM usuarios 
            WHERE id_user = %s
        """,(usuario,))
        resultado=cursor.fetchone()
    else:
        cursor.execute("select * from usuarios")
        resultado=cursor.fetchall()

    close(conn, cursor)

    return jsonify(resultado)


# Busca por uma ou mais viagens e retorna um json
@routes.route("/api/get-trip", methods=['GET'])
def getTrip():
    conn, cursor = connection()
    viagem = request.args.get('id_viagem')

    if viagem:
        cursor.execute("""
            SELECT * 
            FROM viagem 
            WHERE id_viagem = %s
        """,(viagem,))
        resultado=cursor.fetchone()
    else:
        cursor.execute("select * from viagem")
        resultado=cursor.fetchall()

    close(conn, cursor)

    return jsonify(resultado)


# Busca por uma ou mais movimentações e retorna um json
@routes.route("/api/get-movement", methods=['GET'])
def getMovement():
    conn, cursor = connection()
    movimentacao = request.args.get('id_move')

    if movimentacao:
        cursor.execute("""
            SELECT * 
            FROM movimentacoes 
            WHERE id_move = %s
        """,(movimentacao,))
        resultado=cursor.fetchone()
    else:
        cursor.execute("select * from movimentacoes")
        resultado=cursor.fetchall()

    close(conn, cursor)

    return jsonify(resultado)

# ====================== ROTAS DE POST ===========''===========



# ====================== ROTAS DE PUT ======================



# ====================== ROTAS DE DELETE ======================

