# Main Application Routes (Dashboard, Tasks, Profile, History)
from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for
from models.task import Task,TaskUpdate, TaskApplication, Notification
from models.user import User
from models import db
import os
from werkzeug.utils import secure_filename
from flask import current_app
import math
import re

dashboard_bp = Blueprint("dashboard", __name__)

# --- Helper Functions ---

# Function to calculate distance between two coordinates
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371.0  # Earth's radius in KM

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

# --- Dashboard & Task Feed ---

@dashboard_bp.route("/dashboard")
def dashboard_page():
    if "user_id" not in session:
        return redirect(url_for("auth.login_page"))

    user = User.query.get(session["user_id"])
    return render_template("dashboard.html", user=user)

# Get tasks nearby (within 5km) based on category
@dashboard_bp.route("/tasks", methods=["GET"])
def get_tasks():
    user_id = session.get("user_id")
    category = request.args.get("category")

    user_lat = request.args.get("lat", type=float)
    user_lng = request.args.get("lng", type=float)

    # Filter tasks that are open and not posted by the current user
    query = Task.query.filter(
        Task.status == "open",
        Task.posted_by != user_id,
        Task.posted_by != str(user_id)
    )
    
    CATEGORY_GROUPS = {
        "household": ["cleaning", "cooking", "laundry", "dishwashing", "organizing"],
        "shopping": ["grocery", "medicine", "parcel", "bill", "queue"],
        "delivery": ["food_delivery", "package_delivery", "document_delivery", "ride"],
        "repairs": ["electrical", "plumbing", "furniture", "appliance", "handyman"],
        "academic": ["assignment", "notes", "tutoring", "project", "presentation"],
        "tech": ["data_entry", "typing", "design", "website", "software"],
        "personal": ["elderly", "babysitting", "petcare", "companion"],
        "events": ["setup", "decoration", "photography", "crowd", "invitation"],
        "beauty": ["makeup", "mehndi", "hair", "skincare", "nails", "grooming"],
        "misc": ["moving", "waiting", "small_tasks", "other"]
    }

    if category and category != "all":
        if category in CATEGORY_GROUPS:
            query = query.filter(Task.category.in_(CATEGORY_GROUPS[category]))
        else:
            query = query.filter(Task.category == category)

    tasks = query.all()
    filtered_tasks = []

    for t in tasks:
        distance_km = None

        if user_lat and user_lng and t.latitude and t.longitude:
            distance_km = haversine_distance(user_lat, user_lng, float(t.latitude), float(t.longitude))

            # Only show tasks within 5KM
            if distance_km > 5.0:
                continue

        filtered_tasks.append({
            "id": t.id,
            "title": t.title,
            "category": t.category,
            "payment": t.payment,
            "description": t.description,
            "duration": t.duration,
            "distance": round(distance_km, 1) if distance_km is not None else None
        })

    return jsonify(filtered_tasks)

# Get tasks related to the logged in user (Posted or Accepted)
@dashboard_bp.route("/my-tasks", methods=["GET"])
def get_my_tasks():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session["user_id"]

    posted_tasks = Task.query.filter(Task.posted_by==user_id, Task.status != "completed").all()
    accepted_tasks = Task.query.filter(Task.assigned_to==str(user_id), Task.status != "completed").all()

    def serialize_task(t, role):
        updates = TaskUpdate.query.filter_by(task_id=t.id).order_by(TaskUpdate.timestamp.asc()).all()

        contact_name = "Waiting for worker..."
        contact_phone = None

        if role == "poster" and t.assigned_to:
            worker = User.query.get(int(t.assigned_to))
            if worker:
                contact_name = worker.name
                contact_phone = worker.phone
        elif role == "worker" and t.posted_by:
            poster = User.query.get(int(t.posted_by))
            if poster:
                contact_name = poster.name
                contact_phone = poster.phone

        return {
            "id": t.id, "title": t.title, "status": t.status,
            "payment": t.payment, "payment_status": t.payment_status,
            "category": t.category, "description": t.description,
            "contact_name": contact_name,
            "contact_phone": contact_phone,
            "duration": t.duration,
            "updates": [{"message": u.message, "percentage": u.percentage,
                         "time": u.timestamp.isoformat() + "Z",
                         "proof_image": u.proof_image} for u in updates]
        }

    return jsonify({
        "posted": [serialize_task(t, "poster") for t in posted_tasks],
        "accepted": [serialize_task(t, "worker") for t in accepted_tasks]
    })


# --- Task Actions (Posting, Applying, Progress) ---

# Post a new task
@dashboard_bp.route("/post-task", methods=["POST"])
def post_task():
    user = User.query.get(session["user_id"])
    if not user.upi_id:
        return redirect("/profile?missing_upi=1")

    new_task = Task(
        title=request.form["title"],
        description=request.form["description"],
        category=request.form["category"],
        payment=request.form["payment"],
        duration=request.form.get("duration", "Flexible"),
        latitude=request.form.get("latitude"),
        longitude=request.form.get("longitude"),
        status="open",
        posted_by=session["user_id"]
    )

    db.session.add(new_task)
    db.session.commit()

    return redirect(url_for("dashboard.dashboard_page"))

# Apply for a task
@dashboard_bp.route("/apply-task/<int:task_id>", methods=["POST"])
def apply_task(task_id):
    user_id = session["user_id"]
    worker = User.query.get(user_id)
    if not worker.upi_id:
        return jsonify({"error": "upi_missing"}), 400
        
    data = request.get_json()
    message = data.get("message", "I can help with this!")

    try:
        existing = TaskApplication.query.filter_by(task_id=task_id, worker_id=str(user_id)).first()

        if existing:
            if not existing.status or existing.status not in ["pending", "accepted", "rejected"]:
                existing.status = "pending"
                existing.message = message
                db.session.commit()
                return jsonify({"message": "Application submitted successfully!"})
            else:
                return jsonify({"error": "You have already applied for this task."}), 400

        new_app = TaskApplication(
            task_id=task_id,
            worker_id=str(user_id),
            message=message,
            status="pending"
        )
        db.session.add(new_app)

        task = Task.query.get(task_id)
        worker = User.query.get(user_id)
        notif = Notification(
            user_id=task.posted_by,
            message=f"{worker.name} applied for your task: {task.title}",
            link=f"/review-applicants/{task.id}"
        )
        db.session.add(notif)
        db.session.commit()

        return jsonify({"message": "Application submitted! The poster will review your pitch."})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "An error occurred. Check server logs."}), 500

# Post progress updates with proof images
@dashboard_bp.route("/add-task-update/<int:task_id>", methods=["POST"])
def add_task_update(task_id):
    if "user_id" not in session: return jsonify({"error": "Unauthorized"}), 401

    task = Task.query.get(task_id)
    message = request.form.get("message")
    percentage = int(request.form.get("percentage"))

    # Milestone enforcement
    if percentage > 50 and task.payment_status == "unpaid":
        return jsonify({"error": "Cannot update past 50% until requester releases the first milestone payment."}), 400

    proof_filename = None
    if 'proof' in request.files:
        file = request.files['proof']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            proof_filename = f"task_{task.id}_proof_{filename}"
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], proof_filename)
            file.save(filepath)

    new_update = TaskUpdate(
        task_id=task_id, message=message, percentage=percentage, proof_image=proof_filename
    )
    worker = User.query.get(session["user_id"])
    notif = Notification(
        user_id=task.posted_by,
        message=f"{worker.name} updated progress to {percentage}% on '{task.title}'",
        link="/dashboard#my-tasks-section"
    )
    db.session.add(notif)
    db.session.add(new_update)
    db.session.commit()
    return jsonify({"message": "Status & proof uploaded successfully!"})

# Hire a specific applicant
@dashboard_bp.route("/hire-worker/<int:application_id>", methods=["POST"])
def hire_worker(application_id):
    if "user_id" not in session: return jsonify({"error": "Unauthorized"}), 401

    task_app = TaskApplication.query.get(application_id)
    task = Task.query.get(task_app.task_id)
    worker = User.query.get(int(task_app.worker_id))
    worker_name = worker.name if worker else "Worker"

    task.status = "assigned"
    task.assigned_to = task_app.worker_id

    task_app.status = "accepted"
    TaskApplication.query.filter(TaskApplication.task_id == task.id, TaskApplication.id != task_app.id).update({"status": "rejected"})

    notif = Notification(
        user_id=task_app.worker_id,
        message=f"You were hired for: {task.title}!",
        link="/dashboard#my-tasks-section"
    )

    db.session.add(notif)
    db.session.commit()
    return jsonify({"message": f"Successfully hired {worker_name}! Task moved to active."})

# Rate the worker after a task
@dashboard_bp.route("/rate-worker/<int:task_id>", methods=["POST"])
def rate_worker(task_id):
    if "user_id" not in session: return jsonify({"error": "Unauthorized"}), 401

    task = Task.query.get(task_id)
    if task.posted_by != str(session["user_id"]):
        return jsonify({"error": "Only the poster can rate workers."}), 403

    data = request.get_json(silent=True) or {}
    rating = data.get("rating")

    if not rating:
        return jsonify({"error": "Rating is required."}), 400

    worker = User.query.get(int(task.assigned_to))
    if worker:
        worker.total_rating = (worker.total_rating or 0.0) + float(rating)
        worker.rating_count = (worker.rating_count or 0) + 1
        db.session.commit()
        return jsonify({"success": True, "message": "Rating submitted! Now proceed to pay the worker."})
    
    return jsonify({"error": "Worker not found."}), 404

# Remove the assigned worker
@dashboard_bp.route("/unassign-task/<int:task_id>", methods=["POST"])
def unassign_task(task_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    task = Task.query.get(task_id)

    if task.posted_by != str(session["user_id"]):
        return jsonify({"error": "Only the task poster can unassign a worker."}), 403

    if task.payment_status != "unpaid":
        return jsonify({"error": "Cannot unassign after payment has started."}), 400

    if task.assigned_to:
        notif = Notification(
            user_id=task.assigned_to,
            message=f"You were unassigned from: {task.title}.",
            link="/dashboard"
        )
        db.session.add(notif)

    task.status = "open"
    task.assigned_to = None
    TaskUpdate.query.filter_by(task_id=task.id).delete()

    db.session.commit()
    return jsonify({"message": "Worker removed. Task is back on the open feed!"})

# Delete a task entirely
@dashboard_bp.route("/cancel-task/<int:task_id>", methods=["POST"])
def cancel_task(task_id):
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found."}), 404

    if str(task.posted_by) != str(session["user_id"]):
        return jsonify({"error": "Only the creator can delete this."}), 403

    from models.task import TaskApplication, TaskUpdate
    TaskApplication.query.filter_by(task_id=task.id).delete()
    TaskUpdate.query.filter_by(task_id=task.id).delete()

    db.session.delete(task)
    db.session.commit()

    return jsonify({"message": "Task deleted successfully!"})


# --- Profile & History ---

@dashboard_bp.route("/profile")
def profile_page():
    if "user_id" not in session:
        return redirect(url_for("auth.login_page"))

    user = User.query.get(session["user_id"])
    return render_template("profile.html", user=user)

# Update profile info (Name, Phone, Bio, Pic)
@dashboard_bp.route("/update-profile", methods=["POST"])
def update_profile():
    if "user_id" not in session:
        return redirect(url_for("auth.login_page"))

    user = User.query.get(session["user_id"])

    user.name = request.form.get("name")
    user.phone = request.form.get("phone")
    user.gender = request.form.get("gender")
    user.dob = request.form.get("dob")
    upi_id = request.form.get("upi_id")
    if not upi_id:
        return redirect("/profile?missing_upi=1")
    user.upi_id = upi_id

    if 'profile_pic' in request.files:
        file = request.files['profile_pic']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            unique_filename = f"user_{user.id}_{filename}"
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)
            user.profile_pic = unique_filename

    db.session.commit()
    return redirect(url_for("dashboard.profile_page") + "?saved=1")

@dashboard_bp.route("/history")
def history_page():
    if "user_id" not in session: return redirect(url_for("auth.login_page"))
    user = User.query.get(session["user_id"])
    return render_template("history.html", user=user)

# API for history of completed tasks
@dashboard_bp.route("/api/history", methods=["GET"])
def get_history():
    if "user_id" not in session: return jsonify({"error": "Unauthorized"}), 401
    user_id = session["user_id"]

    posted = Task.query.filter_by(posted_by=str(user_id), status="completed").all()
    worked = Task.query.filter_by(assigned_to=str(user_id), status="completed").all()

    def serialize(t, role):
        other_person = "Unknown"
        if role == "posted" and t.assigned_to:
            w = User.query.get(int(t.assigned_to))
            other_person = w.name if w else "Unknown Worker"
        elif role == "worked" and t.posted_by:
            p = User.query.get(int(t.posted_by))
            other_person = p.name if p else "Unknown Poster"

        return {
            "id": t.id,
            "title": t.title,
            "category": t.category,
            "payment": t.payment,
            "role": role,
            "other_person": other_person
        }
    history_data = [serialize(t, "posted") for t in posted] + [serialize(t, "worked") for t in worked]
    return jsonify(history_data)


# --- API Endpoints ---

@dashboard_bp.route("/review-applicants/<int:task_id>")
def review_page(task_id):
    if "user_id" not in session: return redirect(url_for("auth.login_page"))
    user = User.query.get(session["user_id"])
    task = Task.query.get(task_id)
    if not task or task.posted_by != str(user.id):
        return redirect(url_for("dashboard.dashboard_page"))
    return render_template("review_applicants.html", user=user, task=task)

@dashboard_bp.route("/api/applicants/<int:task_id>")
def get_applicants(task_id):
    apps = TaskApplication.query.filter_by(task_id=task_id, status="pending").all()
    result = []
    for app in apps:
        worker = User.query.get(int(app.worker_id))
        if worker:
            r_count = worker.rating_count or 0
            t_rating = worker.total_rating or 0.0
            t_completed = worker.tasks_completed or 0
            avg_rating = round(t_rating / r_count, 1) if r_count > 0 else 0.0
            result.append({
                "id": app.id, "worker_name": worker.name,
                "worker_pic": worker.profile_pic, "message": app.message,
                "rating": avg_rating, "tasks_completed": t_completed
            })
    return jsonify(result)

@dashboard_bp.route("/api/leaderboard", methods=["GET"])
def get_leaderboard():
    if "user_id" not in session: return jsonify([])
    category = request.args.get("category", "all")

    if category == "all":
        top_workers = User.query.filter(User.tasks_completed > 0).order_by(User.tasks_completed.desc()).limit(10).all()
        leaderboard_data = []
        for worker in top_workers:
            r_count = worker.rating_count or 0
            t_rating = worker.total_rating or 0.0
            avg_rating = round(t_rating / r_count, 1) if r_count > 0 else 0.0
            leaderboard_data.append({
                "name": worker.name, "tasks_completed": worker.tasks_completed or 0,
                "rating": avg_rating, "profile_pic": worker.profile_pic
            })
        return jsonify(leaderboard_data)
    else:
        completed_tasks = Task.query.filter_by(status="completed", category=category).all()
        worker_counts = {}
        for t in completed_tasks:
            if t.assigned_to:
                worker_id = str(t.assigned_to)
                worker_counts[worker_id] = worker_counts.get(worker_id, 0) + 1
        sorted_workers = sorted(worker_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        leaderboard_data = []
        for worker_id, count in sorted_workers:
            worker = User.query.get(int(worker_id))
            if worker:
                r_count = worker.rating_count or 0
                t_rating = worker.total_rating or 0.0
                avg_rating = round(t_rating / r_count, 1) if r_count > 0 else 0.0
                leaderboard_data.append({
                    "name": worker.name, "tasks_completed": count,
                    "rating": avg_rating, "profile_pic": worker.profile_pic
                })
        return jsonify(leaderboard_data)

@dashboard_bp.route("/leaderboard")
def leaderboard_page():
    if "user_id" not in session: return redirect(url_for("auth.login_page"))
    user = User.query.get(session["user_id"])
    return render_template("leaderboard.html", user=user)

@dashboard_bp.route("/api/notifications", methods=["GET"])
def get_notifications():
    if "user_id" not in session: return jsonify([])
    notifs = Notification.query.filter_by(user_id=str(session["user_id"])).order_by(Notification.timestamp.desc()).limit(10).all()
    return jsonify([{
        "id": n.id, "message": n.message, "link": n.link, "is_read": n.is_read
    } for n in notifs])

@dashboard_bp.route("/api/notifications/read/<int:notif_id>", methods=["POST"])
def read_notification(notif_id):
    notif = Notification.query.get(notif_id)
    if notif and notif.user_id == str(session.get("user_id")):
        notif.is_read = True
        db.session.commit()
    return jsonify({"success": True})

@dashboard_bp.route("/api/payment-info/<int:task_id>", methods=["GET"])
def get_payment_info(task_id):
    task = Task.query.get(task_id)
    if not task or not task.assigned_to: return jsonify({"error": "Task not found"}), 404
    worker = User.query.get(int(task.assigned_to))
    amount_match = re.search(r'\d+', str(task.payment).replace(',', ''))
    total_amount = float(amount_match.group()) if amount_match else 0
    amount_due = total_amount / 2
    return jsonify({"worker_name": worker.name, "worker_upi": worker.upi_id, "amount_due": amount_due})

@dashboard_bp.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("auth.login_page"))
