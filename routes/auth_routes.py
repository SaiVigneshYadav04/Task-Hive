from flask import Blueprint, jsonify, request, redirect, url_for, render_template, session
from werkzeug.security import generate_password_hash, check_password_hash
from models.user import User
from models import db
import smtplib
import random
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv
import requests
import urllib.parse

load_dotenv()

auth_bp = Blueprint("auth", __name__)

SENDER_EMAIL = os.environ.get("MAIL_USERNAME")
SENDER_PASSWORD = os.environ.get("MAIL_PASSWORD")

def send_otp_email(recipient_email, otp):
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print(f"\n[DEV MODE] SMTP not configured. Simulated sending OTP to {recipient_email}: {otp}\n")
        return True

    msg = MIMEText(f"""Hii! 
Welcome to Task-Hive!
Your 6-digit email verification code is: {otp}.
Enter this code in the app to complete your registration.              
Thanks,
Task-Hive Team""")
    msg['Subject'] = "Task-Hive Account Verification!!"
    msg['From'] = SENDER_EMAIL
    msg['To'] = recipient_email

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, recipient_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

@auth_bp.route("/register")
def register_page():
    return render_template("register.html")


@auth_bp.route("/register-user", methods=["POST"])
def register_user():
    data = request.json
    name = data.get("fullname")
    email = data.get("email")
    phone = data.get("phone")
    password = data.get("password")

    existing_user = User.query.filter_by(email=email).first()

    if existing_user:
        return jsonify({"error": "This email is already registered."}), 400

    otp = str(random.randint(100000, 999999))
    session['temp_user'] = {
        "name": name,
        "email": email,
        "phone": phone,
        "password": generate_password_hash(password)
    }
    session['otp'] = otp

    email_sent = send_otp_email(email, otp)
    
    if email_sent:
        return jsonify({"message": "OTP sent successfully!"})
    else:
        return jsonify({"error": "Failed to send email. Please check your server console."}), 500


@auth_bp.route("/confirm-otp", methods=["POST"])
def confirm_otp():
    data = request.json
    user_entered_otp = data.get("otp")
    real_otp = session.get("otp")

    if user_entered_otp and user_entered_otp == real_otp:
        temp_user = session.get("temp_user")
        
        new_user = User(
            name=temp_user["name"],
            email=temp_user["email"],
            phone=temp_user["phone"],
            password=temp_user["password"]
        )

        db.session.add(new_user)
        db.session.commit()

        session["user_id"] = new_user.id  
        session.pop("temp_user", None)
        session.pop("otp", None)

        return jsonify({"redirect": url_for("dashboard.dashboard_page")})
    else:
        return jsonify({"error": "Incorrect code. Please try again."}), 400

@auth_bp.route("/login")
def login_page():
    return render_template("login_page.html")

@auth_bp.route("/login-user", methods=["POST"])
def login_user():
    email = request.form["email"]
    password = request.form["password"]

    user = User.query.filter_by(email=email).first()

    if not user:
        return render_template("login_page.html", email_error="This email doesn't exist.", email_input=email)

    if not check_password_hash(user.password, password):
        return render_template("login_page.html", password_error="Incorrect password.", email_input=email)

    session["user_id"] = user.id
    return redirect(url_for("dashboard.dashboard_page"))


def send_password_reset_email(recipient_email, otp):
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print(f"\n[DEV MODE] SMTP not configured. Simulated sending Reset OTP to {recipient_email}: {otp}\n")
        return True

    msg = MIMEText(f"""Hello,
We received a request to reset your Task-Hive password.

Your 6-digit password reset code is: {otp}

If you did not request this, please ignore this email.

Thanks,
Task-Hive Team""")
    msg['Subject'] = "Task-Hive Password Reset Code"
    msg['From'] = SENDER_EMAIL
    msg['To'] = recipient_email

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, recipient_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

@auth_bp.route("/send-reset-otp", methods=["POST"])
def send_reset_otp():
    data = request.json
    email = data.get("email")

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "No account found with this email address."}), 404

    otp = str(random.randint(100000, 999999))
    session['reset_otp'] = otp
    session['reset_email'] = email

    if send_password_reset_email(email, otp):
        return jsonify({"message": "OTP sent successfully! Check your inbox."})
    else:
        return jsonify({"error": "Failed to send email. Check VS Code console."}), 500

@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.json
    user_entered_otp = data.get("otp")
    new_password = data.get("new_password")
    
    real_otp = session.get("reset_otp")
    email = session.get("reset_email")

    if not real_otp or not email:
        return jsonify({"error": "Session expired. Please request a new OTP."}), 400

    if user_entered_otp == real_otp:
        user = User.query.filter_by(email=email).first()
        if user:
            user.password = generate_password_hash(new_password)
            db.session.commit()

            session.pop("reset_otp", None)
            session.pop("reset_email", None)
            
            return jsonify({"message": "Password reset successfully! You can now log in."})
        return jsonify({"error": "User not found."}), 404
    else:
        return jsonify({"error": "Invalid OTP. Please try again."}), 400
    

@auth_bp.route("/google-login")
def google_login():

    google_auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
        "redirect_uri": url_for("auth.google_callback", _external=True),
        "response_type": "code",
        "scope": "openid email profile"
    }
    
    url = f"{google_auth_url}?{urllib.parse.urlencode(params)}"
    return redirect(url)

@auth_bp.route("/google-callback")
def google_callback():

    code = request.args.get("code")
    if not code:
        return redirect(url_for("auth.login_page"))

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
        "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
        "redirect_uri": url_for("auth.google_callback", _external=True),
        "grant_type": "authorization_code"
    }
    token_res = requests.post(token_url, data=data).json()
    access_token = token_res.get("access_token")

    if not access_token:
        return redirect(url_for("auth.login_page"))

    userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
    headers = {"Authorization": f"Bearer {access_token}"}
    user_info = requests.get(userinfo_url, headers=headers).json()

    email = user_info.get("email")
    name = user_info.get("name")

    user = User.query.filter_by(email=email).first()

    if not user:
        user = User(
            name=name,
            email=email,
            phone="",
            password=generate_password_hash("GOOGLE_AUTH_PLACEHOLDER")
        )
        db.session.add(user)
        db.session.commit()

    session["user_id"] = user.id
    return redirect(url_for("dashboard.dashboard_page"))
