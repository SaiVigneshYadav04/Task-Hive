from flask import Blueprint, request, jsonify
from models import db
from models.task import Task

task_bp = Blueprint("task", __name__)

@task_bp.route("/create-task", methods=["POST"])
def create_task():

    data = request.json

    task = Task(
        title=data["title"],
        description=data["description"],
        category=data["category"],
        payment=data["payment"],
        latitude=data["latitude"],
        longitude=data["longitude"],
        posted_by=data["user_id"]
    )

    db.session.add(task)
    db.session.commit()

    return jsonify({"message": "Task created successfully"})

@task_bp.route("/accept-task", methods=["POST"])
def accept_task():

    data = request.json

    task = Task.query.get(data["task_id"])

    task.accepted_by = data["user_id"]
    task.status = "accepted"

    db.session.commit()

    return jsonify({"message": "Task accepted"})

@task_bp.route("/complete-task", methods=["POST"])
def complete_task():

    data = request.json

    task = Task.query.get(data["task_id"])

    task.status = "completed"

    db.session.commit()

    return jsonify({"message": "Task completed"})
