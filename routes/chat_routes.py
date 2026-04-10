from flask import Blueprint, request, jsonify, session
from models import db
from models.task import Task, ChatMessage
from datetime import datetime

chat_bp = Blueprint('chat', __name__)

@chat_bp.route("/api/chat/<int:task_id>/send", methods=["POST"])
def send_message(task_id):
    if "user_id" not in session: return jsonify({"error": "Unauthorized"}), 401
    
    user_id = str(session["user_id"])
    task = Task.query.get(task_id)
    
    if not task:
        return jsonify({"error": "Task not found"}), 404
        
    
    if user_id != task.posted_by and user_id != task.assigned_to:
        return jsonify({"error": "Forbidden"}), 403
        
    data = request.get_json()
    msg_text = data.get("message")
    
    if not msg_text:
        return jsonify({"error": "Message empty"}), 400
        
    new_msg = ChatMessage(
        task_id=task_id,
        sender_id=user_id,
        message=msg_text
    )
    db.session.add(new_msg)
    db.session.commit()
    
    return jsonify({"success": True})

@chat_bp.route("/api/chat/<int:task_id>/messages", methods=["GET"])
def get_messages(task_id):
    if "user_id" not in session: return jsonify({"error": "Unauthorized"}), 401
    
    user_id = str(session["user_id"])
    task = Task.query.get(task_id)
    
    if not task:
        return jsonify({"error": "Task not found"}), 404
        
    if user_id != task.posted_by and user_id != task.assigned_to:
        return jsonify({"error": "Forbidden"}), 403
        
    messages = ChatMessage.query.filter_by(task_id=task_id).order_by(ChatMessage.timestamp.asc()).all()
    
    return jsonify([{
        "id": m.id,
        "sender_id": m.sender_id,
        "message": m.message,
        "time": m.timestamp.isoformat(),
        "is_me": m.sender_id == user_id
    } for m in messages])
