from flask import Blueprint, render_template, request, jsonify, send_file, session, redirect, url_for
from database import get_db_connection, connection, close
from utils.currency import get_cotacao, get_variacao_cotacao, moeda
from werkzeug.security import generate_password_hash, check_password_hash
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta, date

load_dotenv()
routes = Blueprint("routes", __name__)

@routes.before_request
def require_login():
    public_routes = {"routes.login", "routes.cadastro", "static", "routes.cadastrar"}
    if request.endpoint in public_routes:
        return None

    if "usuario_id" not in session:
        return redirect(url_for("routes.login"))

# criar funções uteis pra evitar ficar reescrevendo codigo

def getPaises():
    conn, cursor = connection()
    cursor.execute("SELECT id_pais, pais FROM paises ORDER BY pais")
    paises = cursor.fetchall()
    close(conn, cursor)
    return paises

def getDash(id):
    conn, cursor = connection()
    user = session["usuario_id"]

    cursor.execute("""SELECT v.id_viagem, p.pais, v.id_destino
    FROM viagem as v
    inner join paises as p
    on v.id_destino = p.id_pais
    WHERE id_user = %s;""",(user,))
    viagens =cursor.fetchall()
    
    cursor.execute("""SELECT DATEDIFF(data_viagem, CURDATE()) AS dias_restantes
    FROM viagem
    WHERE id_viagem = %s;""",(id,))
    dias_restantes =cursor.fetchone()[0]

    cursor.execute("select anotacao as nota from anotacoes where id_viagem = %s  ORDER BY id_nota DESC;", (id,))
    notas = cursor.fetchall()  

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

    cursor.execute("""
    SELECT COALESCE(
        SUM(
            CASE
                WHEN tipo = 'deposito' THEN valor
                WHEN tipo = 'retirada' THEN -valor
            END 
        ), 0
    ) AS total
    FROM movimentacoes
    WHERE id_viagem = %s
""", (id,))
    guardado = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COALESCE(
        SUM(
            CASE
                WHEN tipo = 'deposito' THEN valor
                WHEN tipo = 'retirada' THEN -valor
                ELSE 0
            END
        ), 0
    ) AS qtd
    FROM movimentacoes
    WHERE data_move >= DATE_SUB(CURDATE(), INTERVAL 1 MONTH)
      AND id_viagem = %s
""", (id,))
    ultimo_mes = cursor.fetchone()[0]

    cursor.execute("""
    SELECT DATEDIFF(data_volta, data_viagem), data_viagem, data_volta
    FROM viagem where id_viagem = %s;
""", (id,))

    datas=cursor.fetchone()

    cursor.execute("select * from usuarios where id_user = %s", (user,))
    nome = cursor.fetchone()[1]

    close(conn, cursor)
    return {
        "custo": custo,
        "origem": "Brasil",
        "destino": destino[0],
        "guardado": guardado,
        "imagem": imagem,
        "sigla": sigla,
        "nome": nome,
        "cotacao": destino[1],
        "simbolo" : destino[2],
        "dias": datas[0],
        "ida": datas[1],
        "volta": datas[2],
        "ultimo_mes": ultimo_mes,
        "dias_restantes": dias_restantes,
        "notas": notas,
        "viagens": viagens
    }

# ====================== rotas de exibição ======================

# Mostra a página inicial
@routes.route("/")
def index():
    if "usuario_id" not in session:
        return redirect(url_for("routes.login"))

    conn, cursor = connection()
    cursor.execute("SELECT v.id_viagem, p.pais FROM viagem v INNER JOIN paises p ON v.id_destino = p.id_pais WHERE v.id_user = %s ORDER BY v.id_viagem ASC", (session["usuario_id"],))
    viagens = cursor.fetchall()
    cursor.execute("SELECT nome FROM usuarios WHERE id_user = %s", (session["usuario_id"],))
    nome_usuario = cursor.fetchone()
    close(conn, cursor)

    if not viagens:
        return render_template(
            'index.html',
            dash={"nome": nome_usuario[0] if nome_usuario else "Usuário", "viagens": []},
            paises=getPaises(),
            has_viagens=False,
            no_trip=True,
            id_viagem=None
        )

    id_viagem = request.args.get("viagem", type=int)
    if id_viagem is None or id_viagem not in [v[0] for v in viagens]:
        return redirect(url_for("routes.index", viagem=viagens[0][0]))

    dash = getDash(id_viagem)
    meta = dash['custo'] * dash['dias']
    percent = round((dash['guardado'] / meta) * 100, 1) if meta else 0
    cotacao = get_cotacao("brl", dash['cotacao'])
    variacao = get_variacao_cotacao("brl", dash['cotacao'])

    if dash['guardado'] < meta:
        target = f"Faltam R${moeda(meta - dash['guardado'])} para sua meta"
    else:
        target = "Sua meta foi alcançada!"

    return render_template('index.html', dash=dash, cotacao=cotacao, variacao=variacao, target=target, meta=meta, id_viagem=id_viagem, percent=percent, paises=getPaises(), has_viagens=True, no_trip=False)

@routes.route("/login", methods=['GET', 'POST'])
def login():
    if "usuario_id" in session:
        return redirect(url_for("routes.index"))

    erro = None

    if request.method == 'POST':
        usuario = (request.form.get('usuario') or '').strip()
        senha = request.form.get('senha') or ''

        if not usuario or not senha:
            erro = 'Preencha usuário e senha.'
        else:
            conn, cursor = connection()
            cursor.execute("SELECT * FROM usuarios WHERE email = %s OR nome = %s LIMIT 1", (usuario, usuario))
            usuario_db = cursor.fetchone()
            close(conn, cursor)

            if usuario_db:
                senha_hash = usuario_db[3]
                senha_valida = False

                if senha_hash.startswith('pbkdf2:') or senha_hash.startswith('scrypt:') or senha_hash.startswith('argon2:') or senha_hash.startswith('bcrypt:'):
                    senha_valida = check_password_hash(senha_hash, senha)
                else:
                    senha_valida = (senha_hash == senha)

                if senha_valida:
                    if not (senha_hash.startswith('pbkdf2:') or senha_hash.startswith('scrypt:') or senha_hash.startswith('argon2:') or senha_hash.startswith('bcrypt:')):
                        conn, cursor = connection()
                        cursor.execute("UPDATE usuarios SET senha = %s WHERE id_user = %s", (generate_password_hash(senha), usuario_db[0]))
                        conn.commit()
                        close(conn, cursor)

                    session['usuario_id'] = usuario_db[0]
                    session['usuario_nome'] = usuario_db[1]
                    return redirect(url_for('routes.index'))

            erro = 'Usuário ou senha inválidos.'

    return render_template('login.html', erro=erro)

@routes.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("routes.login"))

@routes.route("/cadastro")
def cadastro():
    return render_template('cadastro.html')


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

@routes.route("/api/movimentacao", methods=['POST'])
def movimentacao():
    conn, cursor= connection()
    dados = request.form.to_dict()

    cursor.execute("""
        INSERT INTO movimentacoes (id_viagem, valor, tipo) VALUES (%s, %s, %s)
""", (dados['id_viagem'], dados['valor'], dados['tipo'],))

    conn.commit()

    close(conn, cursor)

    return redirect(url_for("routes.index", viagem=dados['id_viagem']))

@routes.route("/api/anotacao", methods=['POST'])
def anotacao():
    conn, cursor= connection()
    dados = request.get_json()

    cursor.execute("""
        INSERT INTO anotacoes (id_viagem, anotacao) VALUES (%s, %s)
""", (dados['id_viagem'], dados['anotacao'],))

    conn.commit()

    close(conn, cursor)

    return {"sucesso": True}

@routes.route("/api/viagem", methods=['POST'])
def criar_viagem():
    if "usuario_id" not in session:
        return redirect(url_for("routes.login"))

    dados = request.form.to_dict()
    titulo = (dados.get('titulo') or '').strip()
    destino = dados.get('destino')
    data_viagem = dados.get('data_viagem')
    data_volta = dados.get('data_volta')
    meta = dados.get('meta') or 0

    if not titulo or not destino or not data_viagem or not data_volta:
        return redirect(url_for("routes.index"))

    conn, cursor = connection()
    cursor.execute("""
        INSERT INTO viagem (id_user, id_origem, id_destino, titulo, data_viagem, data_volta, meta)
        VALUES (%s, 1, %s, %s, %s, %s, %s)
    """, (session['usuario_id'], destino, titulo, data_viagem, data_volta, meta))
    conn.commit()
    nova_viagem_id = cursor.lastrowid
    close(conn, cursor)

    return redirect(url_for("routes.index", viagem=nova_viagem_id))

@routes.route("/cadastrar-user", methods=['POST'])
def cadastrar():
    dados = request.form.to_dict()
    nome = (dados.get('nome') or '').strip()
    email = (dados.get('email') or '').strip()
    senha = dados.get('senha') or ''
    aceita_termos = request.form.get('aceita_termos') == 'on'

    if not nome or not email or not senha:
        return render_template('cadastro.html', erro='Preencha nome, e-mail e senha.')

    if not aceita_termos:
        return render_template('cadastro.html', erro='Você precisa aceitar os termos de uso e LGPD para continuar.')

    conn, cursor = connection()
    cursor.execute("SELECT id_user FROM usuarios WHERE email = %s OR nome = %s LIMIT 1", (email, nome))
    usuario_existente = cursor.fetchone()

    if usuario_existente:
        close(conn, cursor)
        return render_template('cadastro.html', erro='Usuário ou e-mail já cadastrado.')

    senha_hash = generate_password_hash(senha)
    cursor.execute("""
        INSERT INTO usuarios (nome, email, senha) VALUES (%s, %s, %s)
""", (nome, email, senha_hash,))

    conn.commit()
    close(conn, cursor)

    return redirect(url_for("routes.login"))

# ====================== ROTAS DE PUT ======================



# ====================== ROTAS DE DELETE ======================

