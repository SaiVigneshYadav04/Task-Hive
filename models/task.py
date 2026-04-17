# Database models for Tasks, Progress, and Notifications
from models import db
from datetime import datetime

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    latitude = db.Column(db.String(100), nullable=True)
    longitude = db.Column(db.String(100), nullable=True)
    duration = db.Column(db.String(100), nullable=True, default="Flexible")
    category = db.Column(db.String(50))
    payment = db.Column(db.Integer)
    status = db.Column(db.String(20), default="open") # open, assigned, completed
    posted_by = db.Column(db.String(50), nullable=True)
    assigned_to = db.Column(db.String(50), nullable=True)
    payment_status = db.Column(db.String(20), default="unpaid") 

# Updates posted by workers to show progress
class TaskUpdate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, nullable=False)
    message = db.Column(db.String(255), nullable=False)
    percentage = db.Column(db.Integer, nullable=False)
    proof_image = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
# Applications from workers to do a task
class TaskApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, nullable=False)
    worker_id = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="pending") # pending, accepted, rejected
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# In-app notifications for users
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), nullable=True)
    link = db.Column(db.String(255), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Simple chat messages between poster and worker
class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    sender_id = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
