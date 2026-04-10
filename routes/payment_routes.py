from flask import Blueprint, request, jsonify, session
from models.task import Task, Notification
from models.user import User
from models import db
import razorpay
import hmac
import hashlib
import os

payment_bp = Blueprint("payment", __name__)

def get_razorpay_client():
    return razorpay.Client(auth=(
        os.environ.get("RAZORPAY_KEY_ID"),
        os.environ.get("RAZORPAY_KEY_SECRET")
    ))

# ─────────────────────────────────────────
# Create a Razorpay order for a milestone
# milestone = "half" (50%) or "full" (100%)
# ─────────────────────────────────────────
@payment_bp.route("/create-order/<int:task_id>/<milestone>", methods=["POST"])
def create_order(task_id, milestone):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    if str(task.posted_by) != str(session["user_id"]):
        return jsonify({"error": "Only the task poster can make payments."}), 403

    # Calculate amount in paise (Razorpay uses smallest currency unit)
    total = float(task.payment)
    if milestone == "half":
        amount_inr = total / 2
    else:
        amount_inr = total / 2  # second half

    amount_paise = int(amount_inr * 100)

    worker = User.query.get(int(task.assigned_to)) if task.assigned_to else None
    worker_name = worker.name if worker else "Worker"

    try:
        client = get_razorpay_client()
        order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": f"task_{task_id}_{milestone}",
            "notes": {
                "task_id": str(task_id),
                "milestone": milestone,
                "task_title": task.title,
                "worker": worker_name
            }
        })
        return jsonify({
            "order_id": order["id"],
            "amount": amount_paise,
            "key": os.environ.get("RAZORPAY_KEY_ID"),
            "task_title": task.title,
            "worker_name": worker_name,
            "milestone": milestone
        })
    except Exception as e:
        print(f"[Razorpay Error] {e}")
        return jsonify({"error": "Failed to create payment order. Check Razorpay keys."}), 500


# ─────────────────────────────────────────
# Verify Razorpay signature after payment
# ─────────────────────────────────────────
@payment_bp.route("/verify-payment", methods=["POST"])
def verify_payment():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    razorpay_order_id   = data.get("razorpay_order_id")
    razorpay_payment_id = data.get("razorpay_payment_id")
    razorpay_signature  = data.get("razorpay_signature")
    task_id             = data.get("task_id")
    milestone           = data.get("milestone")

    # Verify the HMAC-SHA256 signature
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    body = f"{razorpay_order_id}|{razorpay_payment_id}"
    expected_signature = hmac.new(
        bytes(key_secret, 'utf-8'),
        bytes(body, 'utf-8'),
        hashlib.sha256
    ).hexdigest()


    if expected_signature != razorpay_signature:
        return jsonify({"error": "Payment verification failed. Invalid signature."}), 400

    # Signature valid — update task payment status
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    if milestone == "half":
        task.payment_status = "half_paid"
        notif_msg = f"🎉 Client paid the 50% milestone for: {task.title}!"
    else:
        task.payment_status = "fully_paid"
        task.status = "completed"
        # Update worker task count
        if task.assigned_to:
            worker = User.query.get(int(task.assigned_to))
            if worker:
                worker.tasks_completed = (worker.tasks_completed or 0) + 1
        notif_msg = f"✅ Final payment received! '{task.title}' is complete."

    # Notify the worker
    notif = Notification(
        user_id=str(task.assigned_to),
        message=notif_msg,
        link="/dashboard#my-tasks-section"
    )
    db.session.add(notif)
    db.session.commit()

    return jsonify({"success": True, "message": "Payment verified and recorded!"})


# ─────────────────────────────────────────
# Fallback: manual UPI confirm (kept for
# cases where Razorpay keys are not set)
# ─────────────────────────────────────────
@payment_bp.route("/manual-payment-confirm/<int:task_id>", methods=["POST"])
def manual_payment_confirm(task_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    milestone = data.get("milestone", "half")

    task = Task.query.get(task_id)
    if not task or str(task.posted_by) != str(session["user_id"]):
        return jsonify({"error": "Unauthorized"}), 403

    if milestone == "half":
        task.payment_status = "half_paid"
        msg = "50% milestone marked as paid (manual)."
    else:
        task.payment_status = "payment_claimed"
        msg = "Full payment claimed. Waiting for worker confirmation."

    db.session.commit()
    return jsonify({"message": msg})
