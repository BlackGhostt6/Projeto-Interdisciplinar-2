import json
import logging
import math
import os
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path

import requests


API_URL = "https://economia.awesomeapi.com.br/json/last"
CACHE_FILE = Path(__file__).with_name("currency_cache.json")
CACHE_TTL = timedelta(minutes=5)
MAX_STALE_AGE = timedelta(hours=1)
_quote_cache = {}
_quote_cache_lock = threading.Lock()
logger = logging.getLogger(__name__)


def _load_cache():
    try:
        with CACHE_FILE.open(encoding="utf-8") as arquivo:
            dados_cache = json.load(arquivo)
    except FileNotFoundError:
        return
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Não foi possível carregar o cache de cotações: %s", exc)
        return

    if not isinstance(dados_cache, dict):
        logger.warning("O cache de cotações tem um formato inválido.")
        return

    for chave, dados in dados_cache.items():
        try:
            origem, destino = chave.replace("-", "_").split("_", 1)
            valor = float(dados["valor"])
            atualizado = datetime.fromisoformat(dados["atualizado"])
            variacao = dados.get("variacao")
            variacao = float(variacao) if variacao is not None else None
            if not math.isfinite(valor) or valor <= 0:
                continue
            if variacao is not None and not math.isfinite(variacao):
                continue
        except (AttributeError, KeyError, TypeError, ValueError):
            continue

        chave_normalizada = f"{origem.upper()}_{destino.upper()}"
        cacheada = _quote_cache.get(chave_normalizada)
        if cacheada and cacheada["atualizado"] >= atualizado:
            continue
        _quote_cache[chave_normalizada] = {
            "valor": valor,
            "variacao": variacao,
            "atualizado": atualizado,
        }


def _save_cache():
    dados_cache = {
        chave: {
            "valor": dados["valor"],
            "variacao": dados["variacao"],
            "atualizado": dados["atualizado"].isoformat(),
        }
        for chave, dados in _quote_cache.items()
    }

    arquivo_temporario = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=CACHE_FILE.parent,
            delete=False,
        ) as arquivo:
            arquivo_temporario = arquivo.name
            json.dump(dados_cache, arquivo)
        os.replace(arquivo_temporario, CACHE_FILE)
    except OSError as exc:
        logger.warning("Não foi possível salvar o cache de cotações: %s", exc)
        if arquivo_temporario:
            try:
                os.unlink(arquivo_temporario)
            except FileNotFoundError:
                pass


def _buscar_cotacao(origem, destino):
    par = f"{origem.upper()}-{destino.upper()}"
    resposta = requests.get(f"{API_URL}/{par}", timeout=(3, 8))
    resposta.raise_for_status()

    dados = resposta.json().get(par.replace("-", ""))
    if not dados or "bid" not in dados:
        raise ValueError("Resposta inválida da AwesomeAPI")

    valor = float(dados["bid"])
    variacao = float(dados.get("pctChange") or 0)
    if not math.isfinite(valor) or valor <= 0 or not math.isfinite(variacao):
        raise ValueError("Cotação inválida da AwesomeAPI")
    return valor, variacao


def get_cotacao_info(origem, destino):
    chave = f"{origem.upper()}_{destino.upper()}"
    if origem.upper() == destino.upper():
        return {"valor": 1.0, "variacao": 0.0, "desatualizada": False}

    agora = datetime.now()
    with _quote_cache_lock:
        cacheada = _quote_cache.get(chave)
        if cacheada and agora - cacheada["atualizado"] < CACHE_TTL:
            return {
                "valor": cacheada["valor"],
                "variacao": cacheada["variacao"],
                "desatualizada": False,
            }

        _load_cache()
        cacheada = _quote_cache.get(chave)
        if cacheada and agora - cacheada["atualizado"] < CACHE_TTL:
            return {
                "valor": cacheada["valor"],
                "variacao": cacheada["variacao"],
                "desatualizada": False,
            }

        try:
            valor, variacao = _buscar_cotacao(origem, destino)
        except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
            logger.warning(
                "Falha ao buscar cotação %s-%s: %r",
                origem.upper(),
                destino.upper(),
                exc,
            )
            if cacheada and agora - cacheada["atualizado"] <= MAX_STALE_AGE:
                return {
                    "valor": cacheada["valor"],
                    "variacao": cacheada["variacao"],
                    "desatualizada": True,
                }
            return {"valor": None, "variacao": None, "desatualizada": False}

        _quote_cache[chave] = {
            "valor": valor,
            "variacao": variacao,
            "atualizado": agora,
        }
        _save_cache()
        return {"valor": valor, "variacao": variacao, "desatualizada": False}


def get_cotacao(origem, destino):
    return get_cotacao_info(origem, destino)["valor"]


def get_variacao_cotacao(origem, destino):
    variacao = get_cotacao_info(origem, destino)["variacao"]
    if variacao is None:
        return None

    variacao = round(variacao, 4)
    if variacao > 0:
        return f"+{variacao:.4f}"
    if variacao < 0:
        return f"{variacao:.4f}"
    return "0"


def moeda(valor):
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def moeda_cotacao(valor):
    if valor is None:
        return "--"

    if valor < 1:
        return f"{valor:,.4f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{valor:,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")
