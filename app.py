from flask import Flask, render_template
from database import get_db_connection
from datetime import timedelta
app = Flask(__name__)

from controller.routes import routes
app.register_blueprint(routes)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
