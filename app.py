import os
from flask import Flask, render_template
from database import get_db_connection
from datetime import timedelta
from utils.currency import moeda, moeda_cotacao

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "tripplan-secret-key")
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=365)
app.config["SESSION_REFRESH_EACH_REQUEST"] = False
app.config["SITE_NAME"] = os.environ.get("SITE_NAME", "PlannerTrip")
app.config["SITE_URL"] = os.environ.get("SITE_URL", "https://seu-dominio.com")
app.config["SITE_DESCRIPTION"] = os.environ.get(
    "SITE_DESCRIPTION",
    "Planeje sua viagem com metas financeiras, organização de datas, anotações e controle de orçamento em um só lugar."
)

from controller.routes import routes
app.register_blueprint(routes)

app.jinja_env.filters["moeda"] = moeda
app.jinja_env.filters["moeda_cotacao"] = moeda_cotacao

if __name__ == '__main__':
    import os
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
