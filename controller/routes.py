from flask import Blueprint, render_template, request, jsonify, send_file, session, redirect, url_for
from database import get_db_connection, connection, close
from utils.currency import get_cotacao, get_variacao_cotacao, moeda
from werkzeug.security import generate_password_hash, check_password_hash
from decimal import Decimal
import json
import os
import random
import smtplib
import re
from pathlib import Path
from email.mime.text import MIMEText
from dotenv import load_dotenv
from datetime import datetime, timedelta, date

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
routes = Blueprint("routes", __name__)

PENDING_USERS = []
EMAIL_CODES_PER_DAY = {}


def normalize_email(email):
    return (email or '').strip().lower()


def get_daily_code_counter(email):
    email_key = normalize_email(email)
    today = date.today().isoformat()
    record = EMAIL_CODES_PER_DAY.get(email_key)

    if not record or record.get('day') != today:
        EMAIL_CODES_PER_DAY[email_key] = {'day': today, 'count': 0}
        return EMAIL_CODES_PER_DAY[email_key]

    return record


def can_send_new_code(email):
    record = get_daily_code_counter(email)
    return record['count'] < 5


def send_verification_email(email, code):
    smtp_host = os.getenv('SMTP_HOST')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_user = os.getenv('SMTP_USERNAME') or os.getenv('SMTP_USER')
    smtp_password = os.getenv('SMTP_PASSWORD')
    use_tls = os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
    use_ssl = os.getenv('SMTP_USE_SSL', 'false').lower() == 'true'
    smtp_mock = os.getenv('SMTP_MOCK', 'false').lower() == 'true'

    if not smtp_host:
        if smtp_mock:
            print(f"[SMTP MOCK] Código para {email}: {code}")
            return True
        raise ValueError('SMTP não configurado. Defina SMTP_HOST, SMTP_PORT, SMTP_USERNAME e SMTP_PASSWORD no arquivo .env.')

    message = MIMEText(
        f"Seu código de verificação do TripPlan é: {code}\n\nEste código expira em 5 minutos.",
        'plain',
        'utf-8'
    )
    message['Subject'] = 'Código de verificação - TripPlan'
    message['From'] = smtp_user or 'contato.gabriel276@gmail.com'
    message['To'] = email

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)
                server.sendmail(message['From'], [email], message.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if use_tls:
                    server.starttls()
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)
                server.sendmail(message['From'], [email], message.as_string())
        return True
    except Exception as exc:
        if smtp_mock:
            print(f"[SMTP MOCK] Código para {email}: {code}")
            return True
        raise ValueError(f'Falha no envio do e-mail via SMTP: {exc}') from exc


def create_verification_code(email, payload):
    global PENDING_USERS

    normalized_email = normalize_email(email)

    if not can_send_new_code(normalized_email):
        raise ValueError('Você atingiu o limite de 5 códigos para este e-mail hoje. Tente novamente amanhã.')

    for item in list(PENDING_USERS):
        if item['email'] == normalized_email:
            PENDING_USERS.remove(item)

    code = f'{random.randint(100000, 999999):06d}'
    created_at = datetime.now()

    pending_data = {
        'email': normalized_email,
        'nome': payload.get('nome', ''),
        'username': payload.get('username', ''),
        'senha': payload.get('senha', ''),
        'aceita_termos': payload.get('aceita_termos', True),
        'tipo': payload.get('tipo', 'cadastro'),
        'codigo': code,
        'criado_em': created_at,
        'expira_em': created_at + timedelta(minutes=5),
    }

    PENDING_USERS.append(pending_data)

    record = get_daily_code_counter(normalized_email)
    record['count'] += 1

    try:
        send_verification_email(normalized_email, code)
    except Exception as exc:
        PENDING_USERS = [
            item for item in PENDING_USERS
            if item['email'] != normalized_email
        ]
        raise ValueError(
            f'Não foi possível enviar o e-mail de verificação: {exc}'
        )

    return pending_data


def clear_expired_pending_users():
    now = datetime.now()
    for item in list(PENDING_USERS):
        if item['expira_em'] <= now:
            PENDING_USERS.remove(item)


@routes.before_request
def require_login():
    public_routes = {
        "routes.login",
        "routes.cadastro",
        "routes.verificar_email",
        "routes.reenviar_codigo",
        "routes.cadastrar",
        "routes.api_enviar_codigo",
        "routes.api_verificar_codigo",
        "routes.esqueci_senha",
        "routes.redefinir_senha",
        "routes.trocar_senha",
        "static"
    }
    public_paths = {
        "/login",
        "/cadastro",
        "/verificar-email",
        "/esqueci-senha",
        "/redefinir-senha",
        "/politica-de-privacidade",
        "/logout"
    }

    if request.endpoint in public_routes or request.path in public_paths:
        return None

    if "usuario_id" not in session:
        return redirect(url_for("routes.login"))

# criar funções uteis pra evitar ficar reescrevendo codigo

def getPaises():
    conn, cursor = connection()
    excluded = "brasil"
    cursor.execute("SELECT id_pais, pais FROM paises where not pais = %s ORDER BY pais",(excluded,))
    paises = cursor.fetchall()
    close(conn, cursor)
    return paises

def getDash(id):
    conn, cursor = connection()
    user = session["usuario_id"]

    cursor.execute("""
        SELECT
            v.id_viagem,
            p.pais,
            v.titulo,
            v.data_viagem,
            v.data_volta,
            v.id_destino,
            p.sigla,
            p.imagem,
            p.cust_med,
            p.cod_moeda,
            p.simbolo,
            u.nome,
            DATEDIFF(v.data_viagem, CURDATE()) AS dias_restantes,
            (
                SELECT COALESCE(SUM(
                    CASE
                        WHEN tipo = 'deposito' THEN valor
                        WHEN tipo = 'retirada' THEN -valor
                    END
                ), 0)
                FROM movimentacoes
                WHERE id_viagem = v.id_viagem
            ) AS guardado,
            (
                SELECT COALESCE(SUM(
                    CASE
                        WHEN tipo = 'deposito' THEN valor
                        WHEN tipo = 'retirada' THEN -valor
                    END
                ), 0)
                FROM movimentacoes
                WHERE data_move >= DATE_SUB(CURDATE(), INTERVAL 1 MONTH)
                  AND id_viagem = v.id_viagem
            ) AS ultimo_mes,
            DATEDIFF(v.data_volta, v.data_viagem) AS dias,
            v.data_viagem AS ida,
            v.data_volta AS volta
        FROM viagem AS v
        INNER JOIN paises AS p ON v.id_destino = p.id_pais
        INNER JOIN usuarios AS u ON u.id_user = v.id_user
        WHERE v.id_viagem = %s AND v.id_user = %s
    """, (id, user))
    viagem = cursor.fetchone()

    cursor.execute("""
        SELECT id_nota, anotacao
        FROM anotacoes
        WHERE id_viagem = %s
        ORDER BY id_nota DESC
    """, (id,))
    notas = cursor.fetchall()

    cursor.execute("""
        SELECT v.id_viagem, p.pais, v.titulo, v.data_viagem, v.data_volta, v.id_destino
        FROM viagem AS v
        INNER JOIN paises AS p ON v.id_destino = p.id_pais
        WHERE v.id_user = %s
        ORDER BY v.id_viagem ASC
    """, (user,))
    viagens = cursor.fetchall()

    close(conn, cursor)

    if not viagem:
        return {
            "custo": 0,
            "origem": "Brasil",
            "destino": "",
            "guardado": 0,
            "imagem": "",
            "sigla": "",
            "nome": "Usuário",
            "cotacao": "BRL",
            "simbolo": "R$",
            "dias": 0,
            "ida": None,
            "volta": None,
            "ultimo_mes": 0,
            "dias_restantes": 0,
            "notas": notas,
            "viagens": viagens
        }

    return {
        "custo": viagem[8],
        "origem": "Brasil",
        "destino": viagem[1],
        "guardado": float(viagem[13] or 0),
        "imagem": viagem[7],
        "sigla": viagem[6],
        "nome": viagem[11],
        "cotacao": viagem[9],
        "simbolo": viagem[10],
        "dias": viagem[15],
        "ida": viagem[16],
        "volta": viagem[17],
        "ultimo_mes": float(viagem[14] or 0),
        "dias_restantes": viagem[12],
        "notas": notas,
        "viagens": viagens
    }

# ====================== rotas de exibição ======================

@routes.route("/selecionar-viagem/<int:id_viagem>")
def selecionar_viagem(id_viagem):
    if "usuario_id" not in session:
        return redirect(url_for("routes.login"))

    conn, cursor = connection()
    cursor.execute("SELECT id_viagem FROM viagem WHERE id_viagem = %s AND id_user = %s", (id_viagem, session["usuario_id"]))
    existe = cursor.fetchone()
    close(conn, cursor)

    if existe:
        session["viagem"] = id_viagem
    return redirect(url_for("routes.index"))

# Mostra a página inicial
@routes.route("/")
def index():
    if "usuario_id" not in session:
        return redirect(url_for("routes.login"))

    conn, cursor = connection()
    cursor.execute("""
        SELECT v.id_viagem, p.pais, v.titulo, v.data_viagem, v.data_volta, v.id_destino
        FROM viagem v
        INNER JOIN paises p ON v.id_destino = p.id_pais
        WHERE v.id_user = %s
        ORDER BY v.id_viagem ASC
    """, (session["usuario_id"],))
    viagens = cursor.fetchall()
    cursor.execute("SELECT id_user, nome, username, email FROM usuarios WHERE id_user = %s", (session["usuario_id"],))
    perfil = cursor.fetchone()
    close(conn, cursor)

    if not viagens:
        session.pop("viagem", None)
        return render_template(
            'index.html',
            dash={"nome": perfil[1] if perfil else "Usuário", "viagens": []},
            perfil=perfil,
            paises=getPaises(),
            has_viagens=False,
            no_trip=True,
            id_viagem=None
        )

    id_viagem = session.get("viagem")
    if id_viagem is None or id_viagem not in [v[0] for v in viagens]:
        id_viagem = viagens[0][0]
        session["viagem"] = id_viagem

    dash = getDash(id_viagem)
    cotacao = get_cotacao(dash['cotacao'], "brl")
    custo_decimal = Decimal(str(dash.get('custo') or 0))
    guardado_decimal = Decimal(str(dash.get('guardado') or 0))
    dias_decimal = Decimal(str(dash.get('dias') or 0))

    valor_diario_em_brl = (Decimal(str(cotacao)) * custo_decimal) if cotacao is not None else custo_decimal
    meta = valor_diario_em_brl * dias_decimal
    percent = round((guardado_decimal / meta * Decimal('100')), 1) if meta else 0
    variacao = get_variacao_cotacao(dash['cotacao'], "brl")

    if guardado_decimal < meta:
        target = f"Faltam R${moeda(meta - guardado_decimal)} para sua meta"
    else:
        target = "Sua meta foi alcançada!"

    return render_template('index.html', hoje=date.today().isoformat(), dash=dash, perfil=perfil, cotacao=cotacao, variacao=variacao, target=target, meta=meta, id_viagem=id_viagem, percent=percent, paises=getPaises(), has_viagens=True, no_trip=False)

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
            cursor.execute("""
                SELECT id_user, nome, username, email, senha
                FROM usuarios
                WHERE email = %s OR username = %s
                LIMIT 1
            """, (usuario, usuario))
            usuario_db = cursor.fetchone()
            close(conn, cursor)

            if usuario_db:
                senha_hash = usuario_db[4]
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

@routes.route("/politica-de-privacidade")
def politica_privacidade():
    return render_template('politica_privacidade.html')

@routes.route("/cadastro")
def cadastro():
    session.pop('cadastro_validado', None)
    return render_template('cadastro.html')


@routes.route('/api/cadastro/enviar-codigo', methods=['POST'])
def api_enviar_codigo():
    dados = request.form.to_dict()
    nome = (dados.get('nome') or '').strip()
    username = (dados.get('username') or '').strip()
    email = normalize_email(dados.get('email'))
    senha = dados.get('senha') or ''
    aceita_termos = dados.get('aceita_termos') == 'on'

    if not nome or not email or not senha or not username:
        return jsonify({'sucesso': False, 'erro': 'Preencha nome, usuário, e-mail e senha.'}), 400

    if len(senha) < 6:
        return jsonify({'sucesso': False, 'erro': 'A senha deve ter pelo menos 6 caracteres.'}), 400

    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
        return jsonify({'sucesso': False, 'erro': 'Informe um e-mail válido.'}), 400

    if len(username) < 3:
        return jsonify({'sucesso': False, 'erro': 'O usuário deve ter pelo menos 3 caracteres.'}), 400

    if not aceita_termos:
        return jsonify({'sucesso': False, 'erro': 'Você precisa aceitar os termos de uso e LGPD.'}), 400

    conn, cursor = connection()
    cursor.execute("SELECT id_user FROM usuarios WHERE email = %s OR username = %s LIMIT 1", (email, username))
    usuario_existente = cursor.fetchone()
    close(conn, cursor)

    if usuario_existente:
        return jsonify({'sucesso': False, 'erro': 'Usuário ou e-mail já cadastrado.'}), 409

    try:
        pending = create_verification_code(email, {
            'nome': nome,
            'username': username,
            'senha': senha,
            'aceita_termos': aceita_termos,
        })
    except ValueError as exc:
        return jsonify({'sucesso': False, 'erro': str(exc)}), 400

    session['pending_email'] = pending['email']
    session.pop('cadastro_validado', None)
    payload = {'sucesso': True, 'email': pending['email']}
    if os.getenv('SMTP_MOCK', 'false').lower() == 'true':
        payload['codigo_teste'] = pending['codigo']
    return jsonify(payload)


@routes.route('/api/cadastro/verificar-codigo', methods=['POST'])
def api_verificar_codigo():
    global PENDING_USERS
    email = normalize_email(request.form.get('email'))
    codigo = (request.form.get('codigo') or '').strip()

    if not email or not codigo:
        return jsonify({'sucesso': False, 'erro': 'Informe o e-mail e o código.'}), 400

    if not re.fullmatch(r'^[0-9]{6}$', codigo):
        return jsonify({'sucesso': False, 'erro': 'O código deve conter exatamente 6 dígitos.'}), 400

    clear_expired_pending_users()
    pending = next((item for item in PENDING_USERS if item['email'] == email), None)

    if not pending:
        session.pop('pending_email', None)
        session.pop('cadastro_validado', None)
        return jsonify({'sucesso': False, 'erro': 'Nenhum código pendente foi encontrado para este e-mail.'}), 404

    if datetime.now() > pending['expira_em']:
        PENDING_USERS = [item for item in PENDING_USERS if item['email'] != email]
        session.pop('pending_email', None)
        session.pop('cadastro_validado', None)
        return jsonify({'sucesso': False, 'erro': 'O código expirou. Solicite um novo código.'}), 410

    if codigo != pending['codigo']:
        return jsonify({'sucesso': False, 'erro': 'Código inválido. Verifique e tente novamente.'}), 400

    session['pending_email'] = email
    session['cadastro_validado'] = email
    return jsonify({'sucesso': True, 'email': email})


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
    conn, cursor = connection()
    dados = request.form.to_dict()
    id_viagem = dados.get('id_viagem')
    tipo = (dados.get('tipo') or '').strip()
    valor = dados.get('valor')

    if not id_viagem or not tipo or not valor:
        close(conn, cursor)
        return jsonify({"sucesso": False, "erro": "Dados incompletos para registrar a movimentação."}), 400

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
    """, (id_viagem,))
    guardado = float(cursor.fetchone()[0] or 0)

    if tipo == 'retirada' and float(valor) > guardado:
        close(conn, cursor)
        return jsonify({"sucesso": False, "erro": "Valor da retirada excede o saldo disponível."}), 400

    cursor.execute("""
        INSERT INTO movimentacoes (id_viagem, valor, tipo) VALUES (%s, %s, %s)
    """, (id_viagem, valor, tipo))

    conn.commit()
    close(conn, cursor)

    return jsonify({"sucesso": True}), 200

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
    data_viagem = (dados.get('data_viagem') or '').strip()
    data_volta = (dados.get('data_volta') or '').strip()

    if not titulo or not destino or not data_viagem or not data_volta:
        return redirect(url_for("routes.index"))

    try:
        ida = date.fromisoformat(data_viagem)
        volta = date.fromisoformat(data_volta)
    except ValueError:
        return redirect(url_for("routes.index"))

    if ida < date.today() or volta < ida:
        return redirect(url_for("routes.index"))

    conn, cursor = connection()
    cursor.execute("""
        INSERT INTO viagem (id_user, id_origem, id_destino, titulo, data_viagem, data_volta)
        VALUES (%s, 1, %s, %s, %s, %s)
    """, (session['usuario_id'], destino, titulo, data_viagem, data_volta))
    conn.commit()
    nova_viagem_id = cursor.lastrowid
    close(conn, cursor)

    session["viagem"] = nova_viagem_id
    return redirect(url_for("routes.index"))

@routes.route("/cadastrar-user", methods=['POST'])
def cadastrar():
    global PENDING_USERS
    dados = request.form.to_dict()
    nome = (dados.get('nome') or '').strip()
    username = (dados.get('username') or '').strip()
    email = normalize_email(dados.get('email'))
    senha = dados.get('senha') or ''
    aceita_termos = request.form.get('aceita_termos') == 'on'

    if not nome or not email or not senha or not username:
        return render_template('cadastro.html', erro='Preencha nome, usuário, e-mail e senha.')

    if not aceita_termos:
        return render_template('cadastro.html', erro='Você precisa aceitar os termos de uso e LGPD para continuar.')

    if session.get('cadastro_validado') != email:
        return render_template('cadastro.html', erro='Valide o código enviado para o e-mail antes de criar a conta.')

    conn, cursor = connection()
    cursor.execute("SELECT id_user FROM usuarios WHERE email = %s OR username = %s LIMIT 1", (email, username))
    usuario_existente = cursor.fetchone()

    if usuario_existente:
        close(conn, cursor)
        return render_template('cadastro.html', erro='Usuário ou e-mail já cadastrado.')

    pending = next((item for item in PENDING_USERS if item['email'] == email), None)
    if not pending:
        close(conn, cursor)
        return render_template('cadastro.html', erro='Código pendente não encontrado. Solicite um novo código.')

    senha_hash = generate_password_hash(pending['senha'])
    cursor.execute("""
        INSERT INTO usuarios (nome, username, email, senha, aceitou_lgpd)
        VALUES (%s, %s, %s, %s, %s)
    """, (pending['nome'], pending['username'], pending['email'], senha_hash, pending['aceita_termos']))
    conn.commit()
    novo_user_id = cursor.lastrowid
    close(conn, cursor)

    PENDING_USERS = [item for item in PENDING_USERS if item['email'] != email]
    session.pop('pending_email', None)
    session.pop('cadastro_validado', None)
    session['usuario_id'] = novo_user_id
    session['usuario_nome'] = pending['nome']
    return redirect(url_for('routes.index'))


@routes.route('/verificar-email', methods=['GET', 'POST'])
def verificar_email():
    global PENDING_USERS
    email = normalize_email(request.form.get('email') or request.args.get('email') or session.get('pending_email'))
    acao = (request.form.get('acao') or request.args.get('acao') or 'cadastro').strip().lower()

    if request.method == 'GET':
        return render_template('verificar_email.html', email=email, erro=None, acao=acao)

    codigo = (request.form.get('codigo') or '').strip()
    if not email or not codigo:
        return render_template('verificar_email.html', email=email, erro='Informe o e-mail e o código recebido.', acao=acao)

    if not re.fullmatch(r'^[0-9]{6}$', codigo):
        return render_template('verificar_email.html', email=email, erro='O código deve conter exatamente 6 dígitos.', acao=acao)

    clear_expired_pending_users()
    pending = next((item for item in PENDING_USERS if item['email'] == email), None)

    if not pending:
        session.pop('pending_email', None)
        return render_template('cadastro.html', erro='Nenhum código pendente foi encontrado para este e-mail. Solicite um novo cadastro.')

    if datetime.now() > pending['expira_em']:
        PENDING_USERS = [item for item in PENDING_USERS if item['email'] != email]
        session.pop('pending_email', None)
        return render_template('cadastro.html', erro='O código expirou. Solicite um novo código.')

    if codigo != pending['codigo']:
        return render_template('verificar_email.html', email=email, erro='Código inválido. Verifique o e-mail e tente novamente.', acao=acao)

    session['pending_email'] = email

    if acao in {'reset_senha', 'trocar_senha'}:
        session['reset_email'] = email
        PENDING_USERS = [item for item in PENDING_USERS if item['email'] != email]
        return redirect(url_for('routes.redefinir_senha'))

    conn, cursor = connection()
    cursor.execute("SELECT id_user FROM usuarios WHERE email = %s OR username = %s LIMIT 1", (pending['email'], pending['username']))
    usuario_existente = cursor.fetchone()

    if usuario_existente:
        close(conn, cursor)
        PENDING_USERS = [item for item in PENDING_USERS if item['email'] != email]
        session.pop('pending_email', None)
        return render_template('cadastro.html', erro='Usuário ou e-mail já cadastrado.')

    senha_hash = generate_password_hash(pending['senha'])
    cursor.execute("""
        INSERT INTO usuarios (nome, username, email, senha, aceitou_lgpd)
        VALUES (%s, %s, %s, %s, %s)
    """, (pending['nome'], pending['username'], pending['email'], senha_hash, pending['aceita_termos']))
    conn.commit()
    novo_user_id = cursor.lastrowid
    close(conn, cursor)

    PENDING_USERS = [item for item in PENDING_USERS if item['email'] != email]
    session.pop('pending_email', None)
    session['usuario_id'] = novo_user_id
    session['usuario_nome'] = pending['nome']
    return redirect(url_for('routes.index'))


@routes.route('/reenviar-codigo', methods=['POST'])
def reenviar_codigo():
    global PENDING_USERS
    email = normalize_email(request.form.get('email'))
    acao = (request.form.get('acao') or 'cadastro').strip().lower()
    if not email:
        return render_template('cadastro.html', erro='E-mail não informado.')

    pending = next((item for item in PENDING_USERS if item['email'] == email), None)
    if pending and datetime.now() < pending['expira_em']:
        return render_template('verificar_email.html', email=email, erro='Ainda existe um código válido para este e-mail. Aguarde a expiração ou use o código atual.', acao=acao)

    conn, cursor = connection()
    cursor.execute("SELECT id_user FROM usuarios WHERE email = %s LIMIT 1", (email,))
    usuario_existente = cursor.fetchone()
    close(conn, cursor)

    if acao == 'cadastro' and usuario_existente:
        return render_template('cadastro.html', erro='Esse e-mail já está cadastrado.')

    pending_item = next((item for item in PENDING_USERS if item['email'] == email), None)
    if pending_item:
        PENDING_USERS = [item for item in PENDING_USERS if item['email'] != email]

    try:
        new_pending = create_verification_code(email, {
            'nome': pending_item['nome'] if pending_item else '',
            'username': pending_item['username'] if pending_item else '',
            'senha': pending_item['senha'] if pending_item else '',
            'aceita_termos': bool(pending_item.get('aceita_termos')) if pending_item else True,
            'tipo': acao,
        })
    except ValueError as exc:
        return render_template('cadastro.html', erro=str(exc))

    session['pending_email'] = new_pending['email']
    return render_template('verificar_email.html', email=new_pending['email'], erro=None, acao=acao)


@routes.route('/esqueci-senha', methods=['GET', 'POST'])
def esqueci_senha():
    email = normalize_email(request.form.get('email') or request.args.get('email'))
    erro = None

    if request.method == 'POST':
        if not email:
            erro = 'Informe o e-mail cadastrado.'
        else:
            conn, cursor = connection()
            cursor.execute("SELECT id_user FROM usuarios WHERE email = %s LIMIT 1", (email,))
            usuario_existente = cursor.fetchone()
            close(conn, cursor)

            if not usuario_existente:
                erro = 'Nenhum usuário encontrado com este e-mail.'
            else:
                pending = next((item for item in PENDING_USERS if item['email'] == email), None)
                if pending and datetime.now() < pending['expira_em']:
                    session['pending_email'] = email
                    return render_template('verificar_email.html', email=email, erro='Já existe um código válido para este e-mail. Use-o para continuar.', acao='reset_senha')

                try:
                    new_pending = create_verification_code(email, {'tipo': 'reset_senha'})
                except ValueError as exc:
                    erro = str(exc)
                else:
                    session['pending_email'] = new_pending['email']
                    return render_template('verificar_email.html', email=new_pending['email'], erro=None, acao='reset_senha')

    return render_template('esqueci_senha.html', email=email, erro=erro)


@routes.route('/redefinir-senha', methods=['GET', 'POST'])
def redefinir_senha():
    email = normalize_email(request.form.get('email') or request.args.get('email') or session.get('reset_email') or session.get('pending_email'))
    erro = None

    if request.method == 'POST':
        nova_senha = request.form.get('nova_senha') or ''
        confirmar = request.form.get('confirmar_senha') or ''

        if not email:
            erro = 'E-mail não informado.'
        elif len(nova_senha) < 6:
            erro = 'A nova senha deve ter pelo menos 6 caracteres.'
        elif nova_senha != confirmar:
            erro = 'As senhas não coincidem.'
        else:
            conn, cursor = connection()
            cursor.execute("UPDATE usuarios SET senha = %s WHERE email = %s", (generate_password_hash(nova_senha), email))
            conn.commit()
            close(conn, cursor)
            session.pop('reset_email', None)
            session.pop('pending_email', None)
            if 'usuario_id' in session:
                return redirect(url_for('routes.index'))
            return redirect(url_for('routes.login'))

    return render_template('redefinir_senha.html', email=email, erro=erro)


@routes.route('/trocar-senha', methods=['GET', 'POST'])
def trocar_senha():
    if 'usuario_id' not in session:
        return redirect(url_for('routes.login'))

    email = normalize_email(request.form.get('email') or request.args.get('email') or session.get('usuario_email'))
    if not email:
        email = normalize_email(session.get('usuario_email'))

    if request.method == 'POST':
        nova_senha = request.form.get('nova_senha') or ''
        confirmar = request.form.get('confirmar_senha') or ''
        if len(nova_senha) < 6:
            return render_template('redefinir_senha.html', email=email, erro='A nova senha deve ter pelo menos 6 caracteres.')
        if nova_senha != confirmar:
            return render_template('redefinir_senha.html', email=email, erro='As senhas não coincidem.')

        conn, cursor = connection()
        cursor.execute("UPDATE usuarios SET senha = %s WHERE id_user = %s", (generate_password_hash(nova_senha), session['usuario_id']))
        conn.commit()
        close(conn, cursor)
        return redirect(url_for('routes.index'))

    return render_template('redefinir_senha.html', email=email, erro=None)

# ====================== ROTAS DE PUT ======================

def json_error(message, status=400):
    return jsonify({"sucesso": False, "erro": message}), status


@routes.route("/api/viagem/<int:id_viagem>", methods=["PUT"])
def editar_viagem(id_viagem):
    dados = request.get_json(silent=True) or {}
    destino = dados.get("destino")
    data_viagem = (dados.get("data_viagem") or "").strip()
    data_volta = (dados.get("data_volta") or "").strip()

    if not destino or not data_viagem or not data_volta:
        return json_error("Destino e datas válidas são obrigatórias.")

    try:
        data_ida = date.fromisoformat(data_viagem)
        data_retorno = date.fromisoformat(data_volta)
    except ValueError:
        return json_error("As datas informadas não são válidas.")

    if data_ida < date.today() or data_retorno < data_ida:
        return json_error("A data de ida não pode ser anterior a hoje e a data de volta não pode ser anterior à data de ida.")

    conn, cursor = connection()
    cursor.execute("""
        UPDATE viagem
        SET id_destino = %s, data_viagem = %s, data_volta = %s
        WHERE id_viagem = %s AND id_user = %s
    """, (destino, data_viagem, data_volta, id_viagem, session["usuario_id"]))
    atualizado = cursor.rowcount
    conn.commit()
    close(conn, cursor)

    if not atualizado:
        return json_error("Viagem não encontrada.", 404)
    return jsonify({"sucesso": True})


@routes.route("/api/anotacao/<int:id_nota>", methods=["PUT"])
def editar_anotacao(id_nota):
    dados = request.get_json(silent=True) or {}
    texto = (dados.get("anotacao") or "").strip()
    if not texto:
        return json_error("A anotação não pode ficar vazia.")

    conn, cursor = connection()
    cursor.execute("""
        UPDATE anotacoes a
        INNER JOIN viagem v ON v.id_viagem = a.id_viagem
        SET a.anotacao = %s
        WHERE a.id_nota = %s AND v.id_user = %s
    """, (texto, id_nota, session["usuario_id"]))
    atualizado = cursor.rowcount
    conn.commit()
    close(conn, cursor)

    if not atualizado:
        return json_error("Anotação não encontrada.", 404)
    return jsonify({"sucesso": True})


@routes.route("/api/usuario/<int:id_user>", methods=["PUT"])
def editar_usuario(id_user):
    if id_user != session["usuario_id"]:
        return json_error("Acesso não autorizado.", 403)

    dados = request.get_json(silent=True) or {}
    nome = (dados.get("nome") or "").strip()
    username = (dados.get("username") or "").strip()
    email = (dados.get("email") or "").strip()
    senha = dados.get("senha") or ""
    if not nome or not username or not email:
        return json_error("Nome, usuário e e-mail são obrigatórios.")

    conn, cursor = connection()
    cursor.execute("""
        SELECT id_user FROM usuarios
        WHERE (email = %s OR username = %s) AND id_user <> %s
        LIMIT 1
    """, (email, username, id_user))
    if cursor.fetchone():
        close(conn, cursor)
        return json_error("Usuário ou e-mail já cadastrado.", 409)

    if senha:
        cursor.execute("UPDATE usuarios SET nome = %s, username = %s, email = %s, senha = %s WHERE id_user = %s", (nome, username, email, generate_password_hash(senha), id_user))
    else:
        cursor.execute("UPDATE usuarios SET nome = %s, username = %s, email = %s WHERE id_user = %s", (nome, username, email, id_user))
    conn.commit()
    close(conn, cursor)
    session["usuario_nome"] = nome
    return jsonify({"sucesso": True})


# ====================== ROTAS DE DELETE ======================

@routes.route("/api/anotacao/<int:id_nota>", methods=["DELETE"])
def deletar_anotacao(id_nota):
    conn, cursor = connection()
    cursor.execute("""
        DELETE a FROM anotacoes a
        INNER JOIN viagem v ON v.id_viagem = a.id_viagem
        WHERE a.id_nota = %s AND v.id_user = %s
    """, (id_nota, session["usuario_id"]))
    deletado = cursor.rowcount
    conn.commit()
    close(conn, cursor)
    if not deletado:
        return json_error("Anotação não encontrada.", 404)
    return jsonify({"sucesso": True})


@routes.route("/api/viagem/<int:id_viagem>", methods=["DELETE"])
def deletar_viagem(id_viagem):
    conn, cursor = connection()
    cursor.execute("SELECT id_viagem FROM viagem WHERE id_viagem = %s AND id_user = %s", (id_viagem, session["usuario_id"]))
    if not cursor.fetchone():
        close(conn, cursor)
        return json_error("Viagem não encontrada.", 404)
    cursor.execute("DELETE FROM anotacoes WHERE id_viagem = %s", (id_viagem,))
    cursor.execute("DELETE FROM movimentacoes WHERE id_viagem = %s", (id_viagem,))
    cursor.execute("DELETE FROM viagem WHERE id_viagem = %s AND id_user = %s", (id_viagem, session["usuario_id"]))
    conn.commit()
    close(conn, cursor)
    return jsonify({"sucesso": True})


@routes.route("/api/usuario/<int:id_user>", methods=["DELETE"])
def deletar_usuario(id_user):
    if id_user != session["usuario_id"]:
        return json_error("Acesso não autorizado.", 403)

    conn, cursor = connection()
    cursor.execute(
        "DELETE FROM anotacoes WHERE id_viagem IN (SELECT id_viagem FROM viagem WHERE id_user = %s)",
        (id_user,)
    )
    cursor.execute(
        "DELETE FROM movimentacoes WHERE id_viagem IN (SELECT id_viagem FROM viagem WHERE id_user = %s)",
        (id_user,)
    )
    cursor.execute("DELETE FROM viagem WHERE id_user = %s", (id_user,))
    cursor.execute("DELETE FROM usuarios WHERE id_user = %s", (id_user,))
    conn.commit()
    close(conn, cursor)
    session.clear()
    return jsonify({"sucesso": True})

