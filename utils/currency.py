import requests
from datetime import date, timedelta


def get_cotacao(origem, destino):
    url = f"https://api.frankfurter.dev/v2/rate/{origem}/{destino}"

    resposta = requests.get(url, timeout=10)

    if resposta.status_code != 200:
        return None

    return resposta.json()["rate"]


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