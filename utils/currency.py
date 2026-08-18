import requests
import json
import os
from datetime import datetime, timedelta, date

CACHE = "utils/currency_cache.json"

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

            if datetime.now() - data < timedelta(hours=6):
                return cache[chave]["valor"]
        except (KeyError, ValueError):
            pass

    # Tenta buscar uma cotação nova
    try:
        url = f"https://api.frankfurter.dev/v2/rate/{origem}/{destino}"

        resposta = requests.get(url, timeout=5)
        resposta.raise_for_status()

        valor = resposta.json()["rate"]

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
    except requests.RequestException:
        if chave in cache:
            return cache[chave]["valor"]

        return None

def get_variacao_cotacao(origem, destino):
    hoje = date.today()
    ontem = hoje - timedelta(days=1)

    try:
        url_hoje = f"https://api.frankfurter.dev/v2/rate/{origem}/{destino}"
        url_ontem = f"https://api.frankfurter.dev/v2/rate/{origem}/{destino}?date={ontem}"

        resposta_hoje = requests.get(url_hoje, timeout=5)
        resposta_ontem = requests.get(url_ontem, timeout=5)

        resposta_hoje.raise_for_status()
        resposta_ontem.raise_for_status()

        cotacao_hoje = resposta_hoje.json()["rate"]
        cotacao_ontem = resposta_ontem.json()["rate"]

        variacao = ((cotacao_hoje - cotacao_ontem) / cotacao_ontem) * 100

        return round(variacao, 4)

    except requests.RequestException:
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