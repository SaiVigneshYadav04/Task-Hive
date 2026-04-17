# Routes for handling payments and milestone claims
from flask import Blueprint, request, jsonify, session
from models.task import Task, Notification
from models.user import User
from models import db
import os

payment_bp = Blueprint("payment", __name__)

# Get worker's UPI details and the amount due (50% milestone)
@payment_bp.route("/get-worker-upi/<int:task_id>", methods=["GET"])
def get_worker_upi(task_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    if not task.assigned_to:
        return jsonify({"error": "Task has no worker assigned."}), 400

    worker = User.query.get(int(task.assigned_to))
    if not worker or not worker.upi_id:
        return jsonify({"error": "Worker hasn't added UPI ID yet."}), 400

    return jsonify({
        "upi_id": worker.upi_id,
        "worker_name": worker.name,
        "amount": float(task.payment) / 2
    })

# Mark a payment (Half or Full) as claimed by the poster
@payment_bp.route("/claim-payment/<int:task_id>/<milestone>", methods=["POST"])
def claim_payment(task_id, milestone):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    task = Task.query.get(task_id)
    if not task or str(task.posted_by) != str(session["user_id"]):
        return jsonify({"error": "Unauthorized"}), 403

    if milestone == "half":
        task.payment_status = "half_claimed"
        msg = "50% payment claimed! Waiting for worker to confirm."
    else:
        task.payment_status = "full_claimed"
        msg = "Final payment claimed! Waiting for worker to confirm."

    notif = Notification(
        user_id=str(task.assigned_to),
        message=f"Payment for {milestone} was claimed for: {task.title}. Please confirm if received.",
        link="/dashboard#my-tasks-section",
        type="payment_claimed"
    )
    db.session.add(notif)
    db.session.commit()

    return jsonify({"success": True, "message": msg})

# Worker confirms they actually received the money
@payment_bp.route("/confirm-receipt/<int:task_id>", methods=["POST"])
def confirm_receipt(task_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    task = Task.query.get(task_id)
    if not task or str(task.assigned_to) != str(session["user_id"]):
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json(silent=True) or {}
    milestone = data.get("milestone", "half")

    if milestone == "half":
        task.payment_status = "half_paid"
        notif_msg = f"50% Milestone payment confirmed for: {task.title}"
        notif_type = "payment_confirmed"
    else:
        task.payment_status = "fully_paid"
        task.status = "completed"
        worker = User.query.get(int(session["user_id"]))
        if worker:
            worker.tasks_completed = (worker.tasks_completed or 0) + 1
        notif_msg = f"Full payment confirmed! Task '{task.title}' is finished."
        notif_type = "completed"

    notif = Notification(
        user_id=str(task.posted_by),
        message=notif_msg,
        link="/dashboard",
        type=notif_type
    )
    db.session.add(notif)
    db.session.commit()

    return jsonify({"success": True, "message": "Payment confirmed!"})
