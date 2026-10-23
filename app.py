import os
from flask import Flask, render_template
from database import close_request_connection
from datetime import timedelta
from utils.currency import moeda, moeda_cotacao

app = Flask(__name__)
secret_key = os.environ.get("SECRET_KEY")
is_railway = bool(
    os.environ.get("RAILWAY_ENVIRONMENT")
    or os.environ.get("RAILWAY_PROJECT_ID")
)
if is_railway and not secret_key:
    raise RuntimeError("Configure uma SECRET_KEY persistente no ambiente do Railway.")
app.secret_key = secret_key or os.urandom(32)
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
app.config["SESSION_REFRESH_EACH_REQUEST"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get("SESSION_COOKIE_SECURE", str(is_railway)).lower() == "true"
)
app.config["SITE_NAME"] = os.environ.get("SITE_NAME", "PlannerTrip")
app.config["SITE_URL"] = os.environ.get(
    "SITE_URL",
    "https://plannertrip.gabrielsantiago.dev.br",
).strip().rstrip("/")
app.config["SITE_DESCRIPTION"] = os.environ.get(
    "SITE_DESCRIPTION",
    "Planeje sua viagem com metas financeiras, organização de datas, anotações e controle de orçamento em um só lugar."
)

from controller.routes import routes
app.register_blueprint(routes)
app.teardown_appcontext(close_request_connection)

app.jinja_env.filters["moeda"] = moeda
app.jinja_env.filters["moeda_cotacao"] = moeda_cotacao

if __name__ == '__main__':
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
