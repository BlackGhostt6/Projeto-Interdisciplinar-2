from flask import Blueprint, render_template, request, jsonify, send_file, session, redirect, url_for
from database import get_db_connection, connection, close
from utils.currency import get_cotacao, get_variacao_cotacao
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta, date

load_dotenv()
routes = Blueprint("routes", __name__)

# criar funções uteis pra evitar ficar reescrevendo codigo

def getDash(id):
    conn, cursor = connection()
    user = 1

    cursor.execute("select v.id_destino, p.pais from viagem as v inner join paises as p on v.id_destino = p.id_pais  where id_viagem = %s ", (id,))
    pais = cursor.fetchone()[1]

    cursor.execute("select v.id_destino, p.sigla from viagem v inner join paises p on v.id_destino = p.id_pais where pais = %s", (pais,))
    sigla=cursor.fetchone()[1]

    cursor.execute("select v.id_destino, p.imagem from viagem as v inner join paises as p on v.id_destino = p.id_pais  where id_viagem = %s ", (id,))
    imagem = cursor.fetchone()[1]

    cursor.execute("""
    select cust_med from paises where pais = %s
""", (pais,))
    custo = cursor.fetchone()[0]

    cursor.execute("""
    select pais, cod_moeda, simbolo
        from paises
        where pais = %s
""", (pais,))
    destino = cursor.fetchone() 

    cursor.execute("select sum(valor) as total from movimentacoes where id_viagem = %s;", (id,))
    guardado = cursor.fetchone()[0]

    cursor.execute("select sum(valor) as qtd from movimentacoes where data_move >= DATE_SUB(CURDATE(), INTERVAL 1 MONTH) AND id_viagem = %s;", (id,))
    ultimo_mes = cursor.fetchone()[0]

    cursor.execute("""
    SELECT DATEDIFF(data_volta, data_viagem), data_viagem, data_volta
    FROM viagem where id_viagem = %s;
""", (id,))

    datas=cursor.fetchone()

    user = 1
    cursor.execute("select * from usuarios where id_user = %s", (user,))
    nome = cursor.fetchone()[1]

    if guardado < custo:
        target= f'Faltam R${custo-guardado} para sua meta'
    else:
        target= "Sua meta foi alcançada!"

    close(conn, cursor)
    return {
        "custo": custo,
        "origem": "Brasil",
        "destino": destino[0],
        "guardado": guardado,
        "target": target, 
        "imagem": imagem,
        "sigla": sigla,
        "nome": nome,
        "cotacao": destino[1],
        "simbolo" : destino[2],
        "dias": datas[0],
        "ida": datas[1],
        "volta": datas[2],
        "ultimo_mes": ultimo_mes
    }

# ====================== rotas de exibição ======================

# Mostra a página inicial
@routes.route("/")
def index():
    id_viagem = request.args.get("viagem", 1, type=int)
    dash = getDash(id_viagem)
    percent = round((dash['guardado']/dash['custo'])*100, 1)
    cotacao = get_cotacao("brl", dash['cotacao'])
    variacao=get_variacao_cotacao("brl", dash['cotacao'])
    return render_template('index.html', dash = dash, cotacao = cotacao, variacao =variacao, id_viagem=id_viagem, percent = percent)

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

@routes.route("/api/depositos/<int:id_viagem>")
def api_depositos(id_viagem):

    conn, cursor = connection()

    cursor.execute("""
    SELECT
        DATE_FORMAT(data_move, '%Y-%m') AS mes,
        SUM(CASE
            WHEN tipo = 'deposito' THEN valor
            WHEN tipo = 'retirada' THEN -valor
            ELSE 0
        END) AS total
    FROM movimentacoes
    WHERE id_viagem = %s
    GROUP BY DATE_FORMAT(data_move, '%Y-%m')
    ORDER BY mes
""", (id_viagem,))

    resultado = cursor.fetchall()

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

