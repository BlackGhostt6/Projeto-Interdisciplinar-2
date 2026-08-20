import requests
import json
import os
from datetime import datetime, timedelta, date

CACHE = "utils/currency_cache.json"
API_URL = "https://economia.awesomeapi.com.br/json/last"


def _buscar_cotacao(origem, destino):
    par = f"{origem.upper()}-{destino.upper()}"
    resposta = requests.get(f"{API_URL}/{par}", timeout=5)
    resposta.raise_for_status()

    dados = resposta.json().get(par.replace("-", ""))
    if not dados or "bid" not in dados:
        raise ValueError("Resposta inválida da AwesomeAPI")

    variacao = dados.get("pctChange") or 0
    return float(dados["bid"]), float(variacao)

def get_cotacao(origem, destino):
    chave = f"{origem}_{destino}"

    # Tenta carregar o cache
    cache = {}

    try:
        if os.path.exists(CACHE):
            with open(CACHE, "r") as arquivo:
                cache = json.load(arquivo)
    except (json.JSONDecodeError, OSError):
        cache = {}

    # Usa o cache se ainda estiver válido
    if chave in cache:
        try:
            data = datetime.fromisoformat(cache[chave]["atualizado"])

            if datetime.now() - data < timedelta(minutes=5):
                return cache[chave]["valor"]
        except (KeyError, ValueError):
            pass

    # Tenta buscar uma cotação nova
    try:
        valor, _ = _buscar_cotacao(origem, destino)

        # Atualiza o cache
        cache[chave] = {
            "valor": valor,
            "atualizado": datetime.now().isoformat()
        }

        try:
            with open(CACHE, "w") as arquivo:
                json.dump(cache, arquivo)
        except OSError:
            pass

        return valor

    # Se der timeout ou qualquer erro de conexão,
    # usa o cache antigo
    except (requests.RequestException, ValueError, TypeError, KeyError):
        if chave in cache:
            return cache[chave]["valor"]

        return None

def get_variacao_cotacao(origem, destino):
    try:
        _, variacao = _buscar_cotacao(origem, destino)
        return round(variacao, 4)

    except (requests.RequestException, ValueError, TypeError, KeyError):
        return None
    
def moeda(valor):
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def moeda_cotacao(valor):
    if valor is None:   
        return "--"

    if valor <1:
        return f"{valor:,.4f}".replace(",", "X").replace(".", ",").replace("X", ".")
    else:
        return f"{valor:,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")