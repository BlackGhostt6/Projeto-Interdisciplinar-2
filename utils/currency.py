import requests
import json
import os
from datetime import datetime, timedelta, date

CACHE = "utils/currency_cache.json"

def get_cotacao(origem, destino):
    chave = f"{origem}_{destino}"

    if os.path.exists(CACHE):
        with open(CACHE, "r") as arquivo:
            cache = json.load(arquivo)

        if chave in cache:
            data = datetime.fromisoformat(cache[chave]["atualizado"])

            if datetime.now() - data < timedelta(hours=6):
                return cache[chave]["valor"]

    try:
        url = f"https://api.frankfurter.dev/v2/rate/{origem}/{destino}"
        resposta = requests.get(url, timeout=5)
        resposta.raise_for_status()

        valor = resposta.json()["rate"]

        cache = {}

        if os.path.exists(CACHE):
            with open(CACHE, "r") as arquivo:
                cache = json.load(arquivo)

        cache[chave] = {
            "valor": valor,
            "atualizado": datetime.now().isoformat()
        }

        with open(CACHE, "w") as arquivo:
            json.dump(cache, arquivo)

        return valor

    except requests.RequestException:
        if os.path.exists(CACHE):
            with open(CACHE, "r") as arquivo:
                cache = json.load(arquivo)

            if chave in cache:
                return cache[chave]["valor"]

        return None


def get_variacao_cotacao(origem, destino):
    hoje = date.today()
    ontem = hoje - timedelta(days=1)

    url_hoje = f"https://api.frankfurter.dev/v2/rate/{origem}/{destino}"
    url_ontem = f"https://api.frankfurter.dev/v2/rate/{origem}/{destino}?date={ontem}"

    resposta_hoje = requests.get(url_hoje, timeout=10)
    resposta_ontem = requests.get(url_ontem, timeout=10)

    if resposta_hoje.status_code != 200 or resposta_ontem.status_code != 200:
        return None

    cotacao_hoje = resposta_hoje.json()["rate"]
    cotacao_ontem = resposta_ontem.json()["rate"]

    variacao = round(((cotacao_hoje - cotacao_ontem) / cotacao_ontem) * 100, 4)
    return variacao

def moeda(valor):
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def moeda_cotacao(valor):
    if valor <1:
        return f"{valor:,.4f}".replace(",", "X").replace(".", ",").replace("X", ".")
    else:
        return f"{valor:,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")