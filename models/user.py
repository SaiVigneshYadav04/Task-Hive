# Database model for User accounts
from models import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    # Profile details
    gender = db.Column(db.String(20), nullable=True)
    dob = db.Column(db.String(20), nullable=True)
    profile_pic = db.Column(db.String(255), nullable=True)

    # Worker stats
    tasks_completed = db.Column(db.Integer, default=0)
    total_rating = db.Column(db.Float, default=0.0)
    rating_count = db.Column(db.Integer, default=0)
    
    # Payments
    upi_id = db.Column(db.String(100), nullable=True)
