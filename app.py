# Main Entry Point for Task-Hive
from flask import Flask, render_template
from models import db
from models.user import User
from models.task import Task
from routes.dashboard_routes import dashboard_bp
import sys
import os
from dotenv import load_dotenv

# Load environment variables (Secret keys, Database URLs)
load_dotenv()

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from routes.auth_routes import auth_bp
from routes.payment_routes import payment_bp
from routes.chat_routes import chat_bp

app = Flask(__name__)

# Folder for profile pictures/proof images
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Application Security and Configuration
app.secret_key = os.environ.get("SECRET_KEY", "super_secret_dev_fallback_key")
database_url = os.environ.get("DATABASE_URL", "sqlite:///Task-Hive.db")

# Fix for PostgreSQL URLs (Railway/Render etc)
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url

# Initialize Database
db.init_app(app)

# Create tables if they don't exist (Important for deployment)
with app.app_context():
    db.create_all()

# Register site sections (Blueprints)
app.register_blueprint(dashboard_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(payment_bp)
app.register_blueprint(chat_bp)

# Basic Routes
@app.route("/")
def home():
    return render_template("home_page.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/forgot-password")
def forgot_password():
    return render_template("forgot_password.html")

# Local testing port
if __name__ == "__main__":
    app.run(debug=True, port=2004)
