import math
import threading
from datetime import datetime, timedelta

import requests


API_URL = "https://economia.awesomeapi.com.br/json/last"
CACHE_TTL = timedelta(minutes=5)
MAX_STALE_AGE = timedelta(hours=1)
_quote_cache = {}
_quote_cache_lock = threading.Lock()


def _buscar_cotacao(origem, destino):
    par = f"{origem.upper()}-{destino.upper()}"
    resposta = requests.get(f"{API_URL}/{par}", timeout=3)
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

        try:
            valor, variacao = _buscar_cotacao(origem, destino)
        except (requests.RequestException, ValueError, TypeError, KeyError):
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
