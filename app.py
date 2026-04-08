from flask import Flask, render_template
from models import db
from models.user import User
from models.task import Task
from routes.dashboard_routes import dashboard_bp
import sys
import os
from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from routes.auth_routes import auth_bp

app = Flask(__name__)
app.register_blueprint(dashboard_bp)

UPLOAD_FOLDER ='/home/Task-Hive/Task-Hive/static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.secret_key = os.environ.get("SECRET_KEY")

database_url = os.environ.get("DATABASE_URL", "sqlite:///Task-Hive.db")

if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url

db.init_app(app)

app.register_blueprint(auth_bp)

@app.route("/")
def home():
    return render_template("home_page.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/forgot-password")
def forgot_password():
    return render_template("forgot_password.html")

if __name__ == "__main__":

    with app.app_context():

        db.create_all()

    app.run(debug=True)
