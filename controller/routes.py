from flask import Blueprint, render_template, request, jsonify, send_file, session, redirect, url_for
from database import get_db_connection
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta, date

load_dotenv()
routes = Blueprint("routes", __name__)

# criar funções uteis pra evitar ficar reescrevendo codigo

#rotas de exibição

@routes.route("/")
def index():
    return render_template('index.html')