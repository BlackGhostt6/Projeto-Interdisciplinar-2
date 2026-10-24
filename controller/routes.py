from flask import Blueprint, current_app, render_template, request, jsonify, send_file, session, redirect, url_for
from database import (
    close,
    connection,
    ensure_auth_tables,
    is_transient_connection_error,
    release_request_connection,
)
from mysql.connector import Error as MySQLDatabaseError
from utils.currency import get_cotacao_info, moeda
from werkzeug.security import generate_password_hash, check_password_hash
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import json
import hashlib
import hmac
import os
import re
import secrets
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta, date, timezone
import requests

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
routes = Blueprint("routes", __name__)


class _VerificationRateLimitError(ValueError):
    pass


_SIGNED_MOVEMENT_VALUE_SQL = """
    CASE
        WHEN tipo = 'deposito' THEN ABS(valor)
        WHEN tipo = 'retirada' THEN -ABS(valor)
        ELSE 0
    END
"""


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_public_site_url():
    configured_url = (current_app.config.get("SITE_URL") or "").strip().rstrip("/")
    return configured_url or request.url_root.rstrip("/")


def normalize_email(email):
    return email.strip().lower() if isinstance(email, str) else ""


def _request_text(value):
    return value.strip() if isinstance(value, str) else ""


def validate_trip_dates(data_viagem, data_volta):
    if not data_viagem or not data_volta:
        raise ValueError('Destino e datas válidas são obrigatórias.')

    try:
        ida = date.fromisoformat(data_viagem)
        volta = date.fromisoformat(data_volta)
    except ValueError as exc:
        raise ValueError('As datas informadas não são válidas.') from exc

    if ida < date.today():
        raise ValueError('A data de ida não pode ser anterior a hoje.')

    if volta < ida:
        raise ValueError('A data de volta não pode ser anterior à data de ida.')

    return ida, volta


def _verification_code_hash(email, purpose, code):
    secret_key = current_app.secret_key
    if isinstance(secret_key, str):
        secret_key = secret_key.encode("utf-8")
    message = f"{email}\0{purpose}\0{code}".encode("utf-8")
    return hmac.new(secret_key, message, hashlib.sha256).hexdigest()


def _get_verification_challenge(email, purpose):
    ensure_auth_tables()
    conn, cursor = connection()
    cursor.execute("""
        SELECT code_hash, payload_json, expires_at, attempts
        FROM verification_challenges
        WHERE email = %s AND purpose = %s
    """, (normalize_email(email), purpose))
    challenge = cursor.fetchone()
    close(conn, cursor)
    if not challenge:
        return None

    return {
        "code_hash": challenge[0],
        "payload": json.loads(challenge[1]) if challenge[1] else {},
        "expires_at": challenge[2],
        "attempts": challenge[3],
    }


def _delete_verification_challenge(email, purpose):
    ensure_auth_tables()
    conn, cursor = connection()
    cursor.execute("""
        DELETE FROM verification_challenges
        WHERE email = %s AND purpose = %s
    """, (normalize_email(email), purpose))
    conn.commit()
    close(conn, cursor)


def _create_user_from_challenge(email, payload):
    name = (payload.get("nome") or "").strip()
    username = (payload.get("username") or "").strip()
    email = normalize_email(email)
    password_hash = payload.get("senha_hash")

    if not name or len(username) < 3 or not password_hash or not payload.get("aceita_termos"):
        return None, "Os dados do cadastro estão incompletos ou inválidos."

    conn, cursor = connection()
    cursor.execute("""
        SELECT id_user
        FROM usuarios
        WHERE email = %s OR username = %s
        LIMIT 1
    """, (email, username))
    if cursor.fetchone():
        close(conn, cursor)
        return None, "Usuário ou e-mail já cadastrado."

    cursor.execute("""
        INSERT INTO usuarios (nome, username, email, senha, aceitou_lgpd)
        VALUES (%s, %s, %s, %s, %s)
    """, (name, username, email, password_hash, True))
    conn.commit()
    user_id = cursor.lastrowid
    close(conn, cursor)
    _delete_verification_challenge(email, "cadastro")
    return {"id": user_id, "nome": name}, None


def _verify_verification_code(email, purpose, code):
    ensure_auth_tables()
    email = normalize_email(email)
    conn, cursor = connection()

    try:
        cursor.execute("""
            SELECT code_hash, payload_json, expires_at, attempts
            FROM verification_challenges
            WHERE email = %s AND purpose = %s
            FOR UPDATE
        """, (email, purpose))
        challenge = cursor.fetchone()
        if not challenge:
            conn.commit()
            return None

        code_hash, payload_json, expires_at, attempts = challenge
        if expires_at <= _utcnow():
            cursor.execute("""
                DELETE FROM verification_challenges
                WHERE email = %s AND purpose = %s
            """, (email, purpose))
            conn.commit()
            return None

        expected_hash = _verification_code_hash(email, purpose, code)
        if not hmac.compare_digest(code_hash, expected_hash):
            if attempts >= 9:
                cursor.execute("""
                    DELETE FROM verification_challenges
                    WHERE email = %s AND purpose = %s
                """, (email, purpose))
            else:
                cursor.execute("""
                    UPDATE verification_challenges
                    SET attempts = attempts + 1
                    WHERE email = %s AND purpose = %s
                """, (email, purpose))
            conn.commit()
            return None

        conn.commit()
        return json.loads(payload_json) if payload_json else {}
    except Exception:
        conn.rollback()
        raise
    finally:
        close(conn, cursor)


def send_verification_email(email, code):
    smtp_mock = os.getenv('SMTP_MOCK', 'false').lower() == 'true'
    if smtp_mock:
        print(f"[SMTP MOCK] Código para {email}: {code}")
        return True

    provider = (os.getenv('EMAIL_PROVIDER') or 'resend').lower()
    from_email = (
        os.getenv('RESEND_FROM')
        or os.getenv('EMAIL_FROM')
        or os.getenv('MAILGUN_FROM')
        or 'no-reply@tripplan.app'
    )

    if provider == 'resend':
        api_key = os.getenv('RESEND_API_KEY')
        if not api_key:
            raise ValueError('RESEND_API_KEY não configurada. Defina EMAIL_PROVIDER=resend e RESEND_API_KEY no ambiente do Railway.')

        response = requests.post(
            'https://api.resend.com/emails',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'from': from_email,
                'to': [email],
                'subject': 'Código de verificação - TripPlan',
                'html': (
                    f'<p>Seu código de verificação do TripPlan é: '
                    f'<strong>{code}</strong></p>'
                    '<p>Este código expira em 5 minutos.</p>'
                ),
                'text': (
                    f'Seu código de verificação do TripPlan é: {code}\n\n'
                    'Este código expira em 5 minutos.'
                ),
            },
            timeout=10,
        )

        if response.ok:
            return True

        detail = response.text[:200] if response.text else 'sem resposta detalhada'
        raise ValueError(f'Falha no envio do e-mail via Resend: {response.status_code} - {detail}')

    if provider == 'mailgun':
        api_key = os.getenv('MAILGUN_API_KEY')
        domain = os.getenv('MAILGUN_DOMAIN')
        if not api_key or not domain:
            raise ValueError('MAILGUN_API_KEY e MAILGUN_DOMAIN não configuradas. Defina EMAIL_PROVIDER=mailgun no ambiente do Railway.')

        response = requests.post(
            f'https://api.mailgun.net/v3/{domain}/messages',
            auth=('api', api_key),
            data={
                'from': from_email,
                'to': email,
                'subject': 'Código de verificação - TripPlan',
                'text': (
                    f'Seu código de verificação do TripPlan é: {code}\n\n'
                    'Este código expira em 5 minutos.'
                ),
            },
            timeout=10,
        )

        if response.ok:
            return True

        detail = response.text[:200] if response.text else 'sem resposta detalhada'
        raise ValueError(f'Falha no envio do e-mail via Mailgun: {response.status_code} - {detail}')

    raise ValueError(
        'Provider de e-mail não configurado. Defina EMAIL_PROVIDER=resend ou EMAIL_PROVIDER=mailgun '
        'e as variáveis da API no ambiente do Railway.'
    )


def create_verification_code(email, payload):
    normalized_email = normalize_email(email)
    purpose = payload.get("tipo", "cadastro")
    if purpose not in {"cadastro", "reset_senha", "trocar_senha"}:
        raise ValueError("Tipo de verificação inválido.")
    if purpose == "trocar_senha":
        purpose = "reset_senha"

    stored_payload = dict(payload)
    stored_payload.pop("tipo", None)
    password = stored_payload.pop("senha", None)
    if password is not None:
        stored_payload["senha_hash"] = generate_password_hash(password)

    code = f'{secrets.randbelow(900000) + 100000:06d}'
    expires_at = _utcnow() + timedelta(minutes=5)
    code_hash = _verification_code_hash(normalized_email, purpose, code)
    ensure_auth_tables()
    conn, cursor = connection()

    try:
        cursor.execute("""
            DELETE FROM verification_challenges
            WHERE expires_at <= UTC_TIMESTAMP()
        """)
        cursor.execute("""
            INSERT INTO verification_rate_limits (email, rate_day, send_count)
            VALUES (%s, UTC_DATE(), 1)
            ON DUPLICATE KEY UPDATE
                send_count = IF(rate_day = UTC_DATE(), LEAST(send_count + 1, 6), 1),
                rate_day = UTC_DATE()
        """, (normalized_email,))
        cursor.execute("""
            SELECT send_count
            FROM verification_rate_limits
            WHERE email = %s
            FOR UPDATE
        """, (normalized_email,))
        if cursor.fetchone()[0] > 5:
            conn.commit()
            raise _VerificationRateLimitError(
                'Você atingiu o limite de 5 códigos para este e-mail hoje. Tente novamente amanhã.'
            )

        cursor.execute("""
            INSERT INTO verification_challenges
                (email, purpose, code_hash, payload_json, expires_at, attempts)
            VALUES (%s, %s, %s, %s, %s, 0)
            ON DUPLICATE KEY UPDATE
                code_hash = VALUES(code_hash),
                payload_json = VALUES(payload_json),
                expires_at = VALUES(expires_at),
                attempts = 0
        """, (
            normalized_email,
            purpose,
            code_hash,
            json.dumps(stored_payload),
            expires_at,
        ))
        conn.commit()
    except _VerificationRateLimitError:
        raise
    except Exception as exc:
        conn.rollback()
        raise
    finally:
        close(conn, cursor)

    release_request_connection()
    try:
        send_verification_email(normalized_email, code)
    except Exception as exc:
        _delete_verification_challenge(normalized_email, purpose)
        raise ValueError(
            f'Não foi possível enviar o e-mail de verificação: {exc}'
        ) from exc

    return {"email": normalized_email, "codigo": code, "expira_em": expires_at}


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
        "/",
        "/robots.txt",
        "/sitemap.xml",
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

    conn, cursor = connection()
    cursor.execute("SELECT id_user FROM usuarios WHERE id_user = %s", (session["usuario_id"],))
    usuario_existe = cursor.fetchone()
    close(conn, cursor)

    if not usuario_existe:
        session.clear()
        return redirect(url_for("routes.login"))

# criar funções uteis pra evitar ficar reescrevendo codigo

@lru_cache(maxsize=1)
def getPaises():
    conn, cursor = connection()
    excluded = "brasil"
    cursor.execute("SELECT id_pais, pais FROM paises where not pais = %s ORDER BY pais",(excluded,))
    paises = cursor.fetchall()
    close(conn, cursor)
    return paises

def getDash(id, user_trips):
    conn, cursor = connection()
    user = session["usuario_id"]

    cursor.execute(f"""
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
                SELECT COALESCE(SUM({_SIGNED_MOVEMENT_VALUE_SQL}), 0)
                FROM movimentacoes
                WHERE id_viagem = v.id_viagem
            ) AS guardado,
            (
                SELECT COALESCE(SUM({_SIGNED_MOVEMENT_VALUE_SQL}), 0)
                FROM movimentacoes
                WHERE data_move >= DATE_SUB(CURDATE(), INTERVAL 1 MONTH)
                  AND id_viagem = v.id_viagem
            ) AS ultimo_mes,
            DATEDIFF(v.data_volta, v.data_viagem) + 1 AS dias,
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
            "viagens": user_trips
        }

    return {
        "custo": viagem[8],
        "origem": "Brasil",
        "destino": viagem[1],
        "guardado": Decimal(str(viagem[13] or 0)),
        "imagem": viagem[7],
        "sigla": viagem[6],
        "nome": viagem[11],
        "cotacao": viagem[9],
        "simbolo": viagem[10],
        "dias": viagem[15],
        "ida": viagem[16],
        "volta": viagem[17],
        "ultimo_mes": Decimal(str(viagem[14] or 0)),
        "dias_restantes": viagem[12],
        "notas": notas,
        "viagens": user_trips
    }


def _get_goal_target(guardado, meta):
    if meta <= 0:
        return "Não foi possível calcular sua meta. Confira o destino e as datas da viagem."
    if guardado < meta:
        return f"Faltam R${moeda(meta - guardado)} para sua meta"
    return "Sua meta foi alcançada!"


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

# Apresentação pública do PlannerTrip
@routes.route("/")
def landing():
    return render_template(
        "landing.html",
        site_url=get_public_site_url(),
        site_name=current_app.config["SITE_NAME"],
        site_description=current_app.config["SITE_DESCRIPTION"],
    )


@routes.route("/robots.txt")
def robots_txt():
    return send_file(Path(current_app.root_path) / "robots.txt", mimetype="text/plain")


@routes.route("/sitemap.xml")
def sitemap_xml():
    return send_file(Path(current_app.root_path) / "sitemap.xml", mimetype="application/xml")


# Mostra o painel do usuário
@routes.route("/inicio")
def index():
    if "usuario_id" not in session:
        return redirect(url_for("routes.login"))

    conn, cursor = connection()
    cursor.execute("""
        SELECT
            v.id_viagem, p.pais, v.titulo, v.data_viagem, v.data_volta, v.id_destino,
            u.id_user, u.nome, u.username, u.email
        FROM usuarios AS u
        LEFT JOIN viagem AS v ON v.id_user = u.id_user
        LEFT JOIN paises AS p ON p.id_pais = v.id_destino
        WHERE u.id_user = %s
        ORDER BY v.id_viagem ASC
    """, (session["usuario_id"],))
    resultado = cursor.fetchall()
    viagens = [row[:6] for row in resultado if row[0] is not None]
    perfil = resultado[0][6:10] if resultado else None
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

    dash = getDash(id_viagem, viagens)
    cotacao_info = get_cotacao_info(dash['cotacao'], "brl")
    cotacao = cotacao_info["valor"]
    custo_decimal = Decimal(str(dash.get('custo') or 0))
    guardado_decimal = Decimal(str(dash.get('guardado') or 0))
    dias_decimal = Decimal(str(dash.get('dias') or 0))

    if cotacao is None:
        meta = None
        percent = 0
        target = "Cotação indisponível. Não foi possível calcular a meta em reais."
    else:
        meta = Decimal(str(cotacao)) * custo_decimal * dias_decimal
        percent = min(
            round((guardado_decimal / meta * Decimal('100')), 1) if meta else 0,
            Decimal("100"),
        )
        target = _get_goal_target(guardado_decimal, meta)
    variacao = cotacao_info["variacao"]
    if variacao is not None:
        variacao = round(variacao, 4)
        variacao = f"+{variacao:.4f}" if variacao > 0 else f"{variacao:.4f}" if variacao < 0 else "0"

    return render_template('index.html', hoje=date.today().isoformat(), dash=dash, perfil=perfil, cotacao=cotacao, cotacao_desatualizada=cotacao_info["desatualizada"], variacao=variacao, target=target, meta=meta, id_viagem=id_viagem, percent=percent, paises=getPaises(), has_viagens=True, no_trip=False)

@routes.route("/login", methods=['GET', 'POST'])
def login():
    wants_json = request.accept_mimetypes.best == "application/json"

    if "usuario_id" in session:
        if wants_json:
            return jsonify({"sucesso": True, "redirect": url_for("routes.index")})
        return redirect(url_for("routes.index"))

    erro = None

    if request.method == 'POST':
        usuario = (request.form.get('usuario') or '').strip()
        senha = request.form.get('senha') or ''

        if not usuario or not senha:
            erro = 'Preencha usuário e senha.'
            if wants_json:
                return jsonify({"erro": erro}), 400
        else:
            try:
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

                    if senha_hash.startswith(('pbkdf2:', 'scrypt:', 'argon2:', 'bcrypt:')):
                        senha_valida = check_password_hash(senha_hash, senha)
                    else:
                        senha_valida = senha_hash == senha

                    if senha_valida:
                        if not senha_hash.startswith(('pbkdf2:', 'scrypt:', 'argon2:', 'bcrypt:')):
                            conn, cursor = connection()
                            cursor.execute(
                                "UPDATE usuarios SET senha = %s WHERE id_user = %s",
                                (generate_password_hash(senha), usuario_db[0]),
                            )
                            conn.commit()
                            close(conn, cursor)

                        session.clear()
                        session.permanent = True
                        session['usuario_id'] = usuario_db[0]
                        session['usuario_nome'] = usuario_db[1]
                        if wants_json:
                            return jsonify({
                                "sucesso": True,
                                "redirect": url_for('routes.index'),
                            })
                        return redirect(url_for('routes.index'))

                erro = 'Usuário ou senha inválidos.'
                if wants_json:
                    return jsonify({"erro": erro}), 401
            except MySQLDatabaseError as exc:
                if not is_transient_connection_error(exc):
                    raise
                current_app.logger.exception("Banco indisponível durante tentativa de login.")
                if wants_json:
                    return jsonify({"aguardando_servidor": True}), 503
                return (
                    render_template(
                        'login.html',
                        erro='Não foi possível acessar o servidor agora. Tente novamente em alguns segundos.',
                        usuario=usuario,
                    ),
                    503,
                )

    return render_template('login.html', erro=erro, usuario=request.form.get('usuario', ''))

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

    if len(senha) < 6 or len(senha) > 128:
        return jsonify({'sucesso': False, 'erro': 'A senha deve ter entre 6 e 128 caracteres.'}), 400

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
    email = normalize_email(request.form.get('email'))
    codigo = (request.form.get('codigo') or '').strip()

    if not email or not codigo:
        return jsonify({'sucesso': False, 'erro': 'Informe o e-mail e o código.'}), 400

    if not re.fullmatch(r'^[0-9]{6}$', codigo):
        return jsonify({'sucesso': False, 'erro': 'O código deve conter exatamente 6 dígitos.'}), 400

    payload = _verify_verification_code(email, "cadastro", codigo)
    if payload is None:
        session.pop('pending_email', None)
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

    cursor.execute(f"""
        SELECT
            DATE_FORMAT(m.data_move, '%Y-%m') AS mes,
            SUM({_SIGNED_MOVEMENT_VALUE_SQL}) AS total
        FROM movimentacoes AS m
        INNER JOIN viagem AS v ON v.id_viagem = m.id_viagem
        WHERE m.id_viagem = %s AND v.id_user = %s
        GROUP BY DATE_FORMAT(m.data_move, '%Y-%m')
        ORDER BY mes
    """, (id_viagem, session["usuario_id"]))

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
            SELECT a.id_nota, a.id_viagem, a.anotacao
            FROM anotacoes AS a
            INNER JOIN viagem AS v ON v.id_viagem = a.id_viagem
            WHERE a.id_nota = %s AND v.id_user = %s
        """, (nota, session["usuario_id"]))
        resultado = cursor.fetchone()
    else:
        cursor.execute("""
            SELECT a.id_nota, a.id_viagem, a.anotacao
            FROM anotacoes AS a
            INNER JOIN viagem AS v ON v.id_viagem = a.id_viagem
            WHERE v.id_user = %s
            ORDER BY a.id_nota DESC
            LIMIT 100
        """, (session["usuario_id"],))
        resultado = cursor.fetchall()

    close(conn, cursor)

    return jsonify(resultado)

# Busca por um ou mais usuários e retorna um json
@routes.route("/api/get-user", methods=['GET'])
def getUser():
    conn, cursor = connection()
    cursor.execute("""
        SELECT id_user, nome, username, email
        FROM usuarios
        WHERE id_user = %s
    """, (session["usuario_id"],))
    resultado = cursor.fetchone()

    close(conn, cursor)

    return jsonify(resultado)


# Busca por uma ou mais viagens e retorna um json
@routes.route("/api/get-trip", methods=['GET'])
def getTrip():
    conn, cursor = connection()
    viagem = request.args.get('id_viagem')

    if viagem:
        cursor.execute("""
            SELECT id_viagem, id_destino, titulo, data_viagem, data_volta
            FROM viagem
            WHERE id_viagem = %s AND id_user = %s
        """, (viagem, session["usuario_id"]))
        resultado = cursor.fetchone()
    else:
        cursor.execute("""
            SELECT id_viagem, id_destino, titulo, data_viagem, data_volta
            FROM viagem
            WHERE id_user = %s
            ORDER BY id_viagem DESC
            LIMIT 100
        """, (session["usuario_id"],))
        resultado = cursor.fetchall()

    close(conn, cursor)

    return jsonify(resultado)


# Busca por uma ou mais movimentações e retorna um json
@routes.route("/api/get-movement", methods=['GET'])
def getMovement():
    conn, cursor = connection()
    movimentacao = request.args.get('id_move')

    if movimentacao:
        cursor.execute("""
            SELECT m.id_move, m.id_viagem, m.valor, m.tipo, m.data_move
            FROM movimentacoes AS m
            INNER JOIN viagem AS v ON v.id_viagem = m.id_viagem
            WHERE m.id_move = %s AND v.id_user = %s
        """, (movimentacao, session["usuario_id"]))
        resultado = cursor.fetchone()
    else:
        cursor.execute("""
            SELECT m.id_move, m.id_viagem, m.valor, m.tipo, m.data_move
            FROM movimentacoes AS m
            INNER JOIN viagem AS v ON v.id_viagem = m.id_viagem
            WHERE v.id_user = %s
            ORDER BY m.id_move DESC
            LIMIT 100
        """, (session["usuario_id"],))
        resultado = cursor.fetchall()

    close(conn, cursor)

    return jsonify(resultado)

# ====================== ROTAS DE POST ===========''===========

@routes.route("/api/movimentacao", methods=['POST'])
def movimentacao():
    dados = request.form.to_dict()
    id_viagem = dados.get('id_viagem')
    tipo = (dados.get('tipo') or '').strip()
    valor_texto = (dados.get('valor') or '').strip()

    if not id_viagem or not tipo or not valor_texto:
        return jsonify({"sucesso": False, "erro": "Dados incompletos para registrar a movimentação."}), 400
    if not re.fullmatch(r"[1-9][0-9]*", id_viagem):
        return jsonify({"sucesso": False, "erro": "Viagem inválida."}), 400
    if tipo not in {"deposito", "retirada"}:
        return jsonify({"sucesso": False, "erro": "Tipo de movimentação inválido."}), 400

    try:
        valor = Decimal(valor_texto)
        valor_normalizado = valor.quantize(Decimal("0.01"))
    except InvalidOperation:
        return jsonify({"sucesso": False, "erro": "Informe um valor válido."}), 400
    if not valor.is_finite() or valor <= 0 or valor != valor_normalizado:
        return jsonify({"sucesso": False, "erro": "Informe um valor positivo com até duas casas decimais."}), 400

    conn, cursor = connection()
    try:
        cursor.execute("""
            SELECT id_viagem
            FROM viagem
            WHERE id_viagem = %s AND id_user = %s
            FOR UPDATE
        """, (id_viagem, session["usuario_id"]))
        if not cursor.fetchone():
            conn.rollback()
            return jsonify({"sucesso": False, "erro": "Viagem não encontrada."}), 404

        cursor.execute(f"""
            SELECT COALESCE(SUM({_SIGNED_MOVEMENT_VALUE_SQL}), 0)
            FROM movimentacoes
            WHERE id_viagem = %s
        """, (id_viagem,))
        guardado = Decimal(str(cursor.fetchone()[0] or 0))

        if tipo == 'retirada' and valor > guardado:
            conn.rollback()
            return jsonify({"sucesso": False, "erro": "Valor da retirada excede o saldo disponível."}), 400

        cursor.execute("""
            INSERT INTO movimentacoes (id_viagem, valor, tipo) VALUES (%s, %s, %s)
        """, (id_viagem, valor, tipo))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        close(conn, cursor)

    return jsonify({"sucesso": True}), 200

@routes.route("/api/anotacao", methods=['POST'])
def anotacao():
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return jsonify({"sucesso": False, "erro": "Dados inválidos para a anotação."}), 400
    id_viagem = dados.get('id_viagem')
    texto = _request_text(dados.get('anotacao'))
    if not id_viagem or not str(id_viagem).isdigit() or not texto:
        return jsonify({"sucesso": False, "erro": "Viagem e texto da anotação são obrigatórios."}), 400
    if len(texto) > 5000:
        return jsonify({"sucesso": False, "erro": "A anotação deve ter no máximo 5000 caracteres."}), 400

    conn, cursor = connection()
    try:
        cursor.execute("""
            SELECT id_viagem
            FROM viagem
            WHERE id_viagem = %s AND id_user = %s
        """, (id_viagem, session["usuario_id"]))
        if not cursor.fetchone():
            return jsonify({"sucesso": False, "erro": "Viagem não encontrada."}), 404

        cursor.execute("""
            INSERT INTO anotacoes (id_viagem, anotacao) VALUES (%s, %s)
        """, (id_viagem, texto))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        close(conn, cursor)

    return jsonify({"sucesso": True}), 201

@routes.route("/api/viagem", methods=['POST'])
def criar_viagem():
    if "usuario_id" not in session:
        return redirect(url_for("routes.login"))

    dados = request.form.to_dict()
    titulo = (dados.get('titulo') or '').strip()
    destino = (dados.get('destino') or '').strip()
    data_viagem = (dados.get('data_viagem') or '').strip()
    data_volta = (dados.get('data_volta') or '').strip()

    if not titulo or len(titulo) > 120 or not destino.isdigit() or not data_viagem or not data_volta:
        return redirect(url_for("routes.index"))

    try:
        validate_trip_dates(data_viagem, data_volta)
    except ValueError:
        return redirect(url_for("routes.index"))

    conn, cursor = connection()
    try:
        cursor.execute("""
            INSERT INTO viagem (id_user, id_origem, id_destino, titulo, data_viagem, data_volta)
            SELECT %s, 1, id_pais, %s, %s, %s
            FROM paises
            WHERE id_pais = %s
        """, (session['usuario_id'], titulo, data_viagem, data_volta, destino))
        if cursor.rowcount != 1:
            conn.rollback()
            return redirect(url_for("routes.index"))
        conn.commit()
        nova_viagem_id = cursor.lastrowid
    except Exception:
        conn.rollback()
        raise
    finally:
        close(conn, cursor)

    session["viagem"] = nova_viagem_id
    return redirect(url_for("routes.index"))

@routes.route("/cadastrar-user", methods=['POST'])
def cadastrar():
    email = normalize_email(session.get('cadastro_validado'))
    if not email:
        return render_template('cadastro.html', erro='Valide o código enviado para o e-mail antes de criar a conta.')

    pending = _get_verification_challenge(email, "cadastro")
    if not pending or pending["expires_at"] <= _utcnow():
        session.pop('cadastro_validado', None)
        session.pop('pending_email', None)
        return render_template('cadastro.html', erro='Código expirado ou não encontrado. Solicite um novo código.')

    user, erro = _create_user_from_challenge(email, pending["payload"])
    if erro:
        return render_template('cadastro.html', erro=erro)

    session.clear()
    session['usuario_id'] = user["id"]
    session['usuario_nome'] = user["nome"]
    return redirect(url_for('routes.index'))


@routes.route('/verificar-email', methods=['GET', 'POST'])
def verificar_email():
    email = normalize_email(request.form.get('email') or request.args.get('email') or session.get('pending_email'))
    acao = (request.form.get('acao') or request.args.get('acao') or 'cadastro').strip().lower()
    if acao not in {'cadastro', 'reset_senha', 'trocar_senha'}:
        acao = 'cadastro'

    if request.method == 'GET':
        return render_template('verificar_email.html', email=email, erro=None, acao=acao)

    codigo = (request.form.get('codigo') or '').strip()
    if not email or not codigo:
        return render_template('verificar_email.html', email=email, erro='Informe o e-mail e o código recebido.', acao=acao)

    if not re.fullmatch(r'^[0-9]{6}$', codigo):
        return render_template('verificar_email.html', email=email, erro='O código deve conter exatamente 6 dígitos.', acao=acao)

    purpose = "reset_senha" if acao in {"reset_senha", "trocar_senha"} else "cadastro"
    payload = _verify_verification_code(email, purpose, codigo)
    if payload is None:
        return render_template('verificar_email.html', email=email, erro='Código inválido. Verifique o e-mail e tente novamente.', acao=acao)

    if purpose == "reset_senha":
        session['reset_email'] = email
        session['reset_authorized_at'] = _utcnow().isoformat()
        session.pop('pending_email', None)
        _delete_verification_challenge(email, purpose)
        return redirect(url_for('routes.redefinir_senha'))

    user, erro = _create_user_from_challenge(email, payload)
    if erro:
        return render_template('cadastro.html', erro=erro)

    session.clear()
    session['usuario_id'] = user["id"]
    session['usuario_nome'] = user["nome"]
    return redirect(url_for('routes.index'))


@routes.route('/reenviar-codigo', methods=['POST'])
def reenviar_codigo():
    email = normalize_email(request.form.get('email'))
    acao = (request.form.get('acao') or 'cadastro').strip().lower()
    if acao not in {'cadastro', 'reset_senha', 'trocar_senha'}:
        return render_template('cadastro.html', erro='Tipo de verificação inválido.')
    if not email:
        return render_template('cadastro.html', erro='E-mail não informado.')

    purpose = "reset_senha" if acao in {"reset_senha", "trocar_senha"} else "cadastro"
    pending = _get_verification_challenge(email, purpose)
    if pending and pending["expires_at"] > _utcnow():
        message = (
            'Se o e-mail estiver cadastrado, um código será enviado.'
            if purpose == "reset_senha"
            else 'Ainda existe um código válido para este e-mail. Aguarde a expiração ou use o código atual.'
        )
        return render_template('verificar_email.html', email=email, erro=message, acao=acao)

    conn, cursor = connection()
    cursor.execute("SELECT id_user FROM usuarios WHERE email = %s LIMIT 1", (email,))
    usuario_existente = cursor.fetchone()
    close(conn, cursor)

    if purpose == "cadastro" and usuario_existente:
        return render_template('cadastro.html', erro='Esse e-mail já está cadastrado.')
    if purpose == "reset_senha" and not usuario_existente:
        return render_template(
            'verificar_email.html',
            email=email,
            erro='Se o e-mail estiver cadastrado, um código será enviado.',
            acao=acao,
        )
    if purpose == "cadastro" and not pending:
        return render_template('cadastro.html', erro='Dados de cadastro não encontrados. Inicie o cadastro novamente.')

    try:
        challenge_data = dict(pending["payload"]) if pending and purpose == "cadastro" else {}
        challenge_data["tipo"] = purpose
        new_pending = create_verification_code(email, challenge_data)
    except ValueError as exc:
        if purpose == "reset_senha":
            current_app.logger.warning("Falha ao reenviar código de recuperação: %s", exc)
            return render_template(
                'verificar_email.html',
                email=email,
                erro='Se o e-mail estiver cadastrado, um código será enviado.',
                acao=acao,
            )
        template = 'esqueci_senha.html' if purpose == "reset_senha" else 'cadastro.html'
        return render_template(template, email=email, erro=str(exc))

    session['pending_email'] = new_pending['email']
    message = (
        'Se o e-mail estiver cadastrado, um código será enviado.'
        if purpose == "reset_senha"
        else None
    )
    return render_template('verificar_email.html', email=new_pending['email'], erro=message, acao=acao)


@routes.route('/esqueci-senha', methods=['GET', 'POST'])
def esqueci_senha():
    email = normalize_email(request.form.get('email') or request.args.get('email'))
    erro = None

    if request.method == 'POST':
        if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
            erro = 'Informe um e-mail válido.'
        else:
            conn, cursor = connection()
            cursor.execute("SELECT id_user FROM usuarios WHERE email = %s LIMIT 1", (email,))
            usuario_existente = cursor.fetchone()
            close(conn, cursor)

            if usuario_existente:
                try:
                    pending = _get_verification_challenge(email, "reset_senha")
                    if not pending or pending["expires_at"] <= _utcnow():
                        create_verification_code(email, {'tipo': 'reset_senha'})
                    session['pending_email'] = email
                except ValueError as exc:
                    current_app.logger.warning("Falha ao criar desafio de recuperação de senha: %s", exc)
            return render_template(
                'verificar_email.html',
                email=email,
                erro='Se o e-mail estiver cadastrado, um código será enviado.',
                acao='reset_senha',
            )

    return render_template('esqueci_senha.html', email=email, erro=erro)


@routes.route('/redefinir-senha', methods=['GET', 'POST'])
def redefinir_senha():
    email = normalize_email(session.get('reset_email'))
    authorized_at = session.get('reset_authorized_at')
    erro = None

    try:
        reset_is_authorized = bool(
            email
            and authorized_at
            and _utcnow() - datetime.fromisoformat(authorized_at) <= timedelta(minutes=10)
        )
    except (TypeError, ValueError):
        reset_is_authorized = False

    if not reset_is_authorized:
        session.pop('reset_email', None)
        session.pop('reset_authorized_at', None)
        return redirect(url_for('routes.esqueci_senha'))

    if request.method == 'POST':
        nova_senha = request.form.get('nova_senha') or ''
        confirmar = request.form.get('confirmar_senha') or ''

        if not email:
            erro = 'E-mail não informado.'
        elif len(nova_senha) < 6 or len(nova_senha) > 128:
            erro = 'A nova senha deve ter entre 6 e 128 caracteres.'
        elif nova_senha != confirmar:
            erro = 'As senhas não coincidem.'
        else:
            conn, cursor = connection()
            cursor.execute("UPDATE usuarios SET senha = %s WHERE email = %s", (generate_password_hash(nova_senha), email))
            atualizado = cursor.rowcount
            conn.commit()
            close(conn, cursor)
            session.clear()
            if not atualizado:
                return redirect(url_for('routes.esqueci_senha'))
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
        if len(nova_senha) < 6 or len(nova_senha) > 128:
            return render_template('redefinir_senha.html', email=email, erro='A nova senha deve ter entre 6 e 128 caracteres.')
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
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return json_error("Dados inválidos para a viagem.")
    destino = _request_text(dados.get("destino"))
    data_viagem = _request_text(dados.get("data_viagem"))
    data_volta = _request_text(dados.get("data_volta"))

    if not destino.isdigit() or not data_viagem or not data_volta:
        return json_error("Destino e datas válidas são obrigatórias.")

    try:
        validate_trip_dates(data_viagem, data_volta)
    except ValueError as exc:
        return json_error(str(exc))

    conn, cursor = connection()
    try:
        cursor.execute("""
            SELECT v.id_viagem
            FROM viagem AS v
            INNER JOIN paises AS p ON p.id_pais = %s
            WHERE v.id_viagem = %s AND v.id_user = %s
            FOR UPDATE
        """, (destino, id_viagem, session["usuario_id"]))
        if not cursor.fetchone():
            conn.rollback()
            return json_error("Viagem ou destino não encontrado.", 404)

        cursor.execute("""
            UPDATE viagem
            SET id_destino = %s, data_viagem = %s, data_volta = %s
            WHERE id_viagem = %s AND id_user = %s
        """, (destino, data_viagem, data_volta, id_viagem, session["usuario_id"]))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        close(conn, cursor)

    return jsonify({"sucesso": True})


@routes.route("/api/anotacao/<int:id_nota>", methods=["PUT"])
def editar_anotacao(id_nota):
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return json_error("Dados inválidos para a anotação.")
    texto = _request_text(dados.get("anotacao"))
    if not texto:
        return json_error("A anotação não pode ficar vazia.")
    if len(texto) > 5000:
        return json_error("A anotação deve ter no máximo 5000 caracteres.")

    conn, cursor = connection()
    try:
        cursor.execute("""
            SELECT a.id_nota
            FROM anotacoes AS a
            INNER JOIN viagem AS v ON v.id_viagem = a.id_viagem
            WHERE a.id_nota = %s AND v.id_user = %s
            FOR UPDATE
        """, (id_nota, session["usuario_id"]))
        if not cursor.fetchone():
            conn.rollback()
            return json_error("Anotação não encontrada.", 404)

        cursor.execute("""
            UPDATE anotacoes
            SET anotacao = %s
            WHERE id_nota = %s
        """, (texto, id_nota))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        close(conn, cursor)

    return jsonify({"sucesso": True})


@routes.route("/api/usuario/<int:id_user>", methods=["PUT"])
def editar_usuario(id_user):
    if id_user != session["usuario_id"]:
        return json_error("Acesso não autorizado.", 403)

    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return json_error("Dados inválidos para o perfil.")
    nome = _request_text(dados.get("nome"))
    username = _request_text(dados.get("username"))
    email = normalize_email(dados.get("email"))
    senha = _request_text(dados.get("senha"))
    if not nome or not username or not email:
        return json_error("Nome, usuário e e-mail são obrigatórios.")
    if len(username) < 3:
        return json_error("O usuário deve ter pelo menos 3 caracteres.")
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
        return json_error("Informe um e-mail válido.")
    if senha and (len(senha) < 6 or len(senha) > 128):
        return json_error("A senha deve ter entre 6 e 128 caracteres.")

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
