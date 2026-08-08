from flask import Flask, render_template
from database import get_db_connection
from datetime import timedelta
app = Flask(__name__)

app.secret_key = "7357hr5357h5hyr577k37377li5o375257"
app.permanent_session_lifetime = timedelta(days = 30)

from controller.routes import routes
app.register_blueprint(routes)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
