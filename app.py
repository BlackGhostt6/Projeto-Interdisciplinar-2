import os
from flask import Flask, render_template
from database import get_db_connection
from datetime import timedelta
from utils.currency import moeda, moeda_cotacao

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "tripplan-secret-key")
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
app.config["SESSION_REFRESH_EACH_REQUEST"] = False

from controller.routes import routes
app.register_blueprint(routes)

app.jinja_env.filters["moeda"] = moeda
app.jinja_env.filters["moeda_cotacao"] = moeda_cotacao

if __name__ == '__main__':
    import os
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
