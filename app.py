from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify
)
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)
import sqlite3

app = Flask(__name__)
app.secret_key = "secret_key"
DB_NAME = "todo.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)
    # tasksテーブルに due_date と priority を追加
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        text TEXT NOT NULL,
        due_date TEXT,
        priority TEXT DEFAULT '中',
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    conn.commit()
    conn.close()

init_db()

# ---- 認証ヘルパー (API用) ----
def api_auth(req):
    auth = req.authorization
    if not auth or not auth.username or not auth.password:
        return None
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username=?", (auth.username,)).fetchone()
    conn.close()
    if user and check_password_hash(user["password"], auth.password):
        return user["id"]
    return None

# ==============================================================================
# WEB FRONTEND ROUTES
# ==============================================================================

@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    page = int(request.args.get("page", 1))
    search = request.args.get("search", "")
    per_page = 5
    offset = (page - 1) * per_page

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    SELECT COUNT(*) FROM tasks 
    WHERE user_id=? AND text LIKE ?
    """, (session["user_id"], f"%{search}%"))
    total = cur.fetchone()[0]

    cur.execute("""
    SELECT * FROM tasks 
    WHERE user_id=? AND text LIKE ? 
    ORDER BY id DESC LIMIT ? OFFSET ?
    """, (session["user_id"], f"%{search}%", per_page, offset))
    tasks = cur.fetchall()
    conn.close()

    total_pages = (total + per_page - 1) // per_page if per_page > 0 else 1

    return render_template(
        "index.html",
        tasks=tasks,
        page=page,
        total_pages=total_pages,
        search=search
    )

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if len(username) < 3:
            flash("ユーザー名は3文字以上")
            return redirect(url_for("register"))
        if len(password) < 6:
            flash("パスワードは6文字以上")
            return redirect(url_for("register"))

        conn = get_db()
        try:
            conn.execute("INSERT INTO users(username,password) VALUES(?,?)",
                         (username, generate_password_hash(password)))
            conn.commit()
        except sqlite3.IntegrityError:
            flash("既に存在するユーザーです")
            return redirect(url_for("register"))
        finally:
            conn.close()

        flash("登録完了")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("home"))

        flash("ログイン失敗")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/add", methods=["POST"])
def add():
    if "user_id" not in session:
        return redirect(url_for("login"))

    text = request.form["task"].strip()
    due_date = request.form.get("due_date", "")
    priority = request.form.get("priority", "中")

    if len(text) < 1:
        flash("タスクを入力してください")
        return redirect(url_for("home"))

    conn = get_db()
    conn.execute("INSERT INTO tasks(user_id, text, due_date, priority) VALUES(?,?,?,?)",
                 (session["user_id"], text, due_date, priority))
    conn.commit()
    conn.close()

    return redirect(url_for("home"))

@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
def edit(task_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id=? AND user_id=?", 
                        (task_id, session["user_id"])).fetchone()

    if not task:
        conn.close()
        flash("タスクが見つかりません")
        return redirect(url_for("home"))

    if request.method == "POST":
        text = request.form["task"].strip()
        due_date = request.form.get("due_date", "")
        priority = request.form.get("priority", "中")

        if len(text) < 1:
            flash("タスクを入力してください")
            return redirect(url_for("edit", task_id=task_id))

        conn.execute("UPDATE tasks SET text=?, due_date=?, priority=? WHERE id=? AND user_id=?",
                     (text, due_date, priority, task_id, session["user_id"]))
        conn.commit()
        conn.close()
        flash("タスクを更新しました")
        return redirect(url_for("home"))

    conn.close()
    return render_template("edit.html", task=task)

@app.route("/delete/<int:task_id>")
def delete(task_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    conn.execute("DELETE FROM tasks WHERE id=? AND user_id=?", (task_id, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect(url_for("home"))

@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        username = request.form["username"].strip()
        new_password = request.form["password"]

        if len(new_password) < 6:
            flash("パスワードは6文字以上")
            return redirect(url_for("reset_password"))

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()

        if user:
            conn.execute("UPDATE users SET password=? WHERE id=?", 
                         (generate_password_hash(new_password), user["id"]))
            conn.commit()
            conn.close()
            flash("パスワードをリセットしました。ログインしてください。")
            return redirect(url_for("login"))
        else:
            conn.close()
            flash("ユーザー名が存在しません")
            return redirect(url_for("reset_password"))

    return render_template("reset_password.html")


# ==============================================================================
# REST API ENDPOINTS (Basic認証を使用)
# ==============================================================================

@app.route("/api/tasks", methods=["GET"])
def api_get_tasks():
    user_id = api_auth(request)
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    tasks = conn.execute("SELECT * FROM tasks WHERE user_id=?", (user_id,)).fetchall()
    conn.close()
    return jsonify([dict(t) for t in tasks])

@app.route("/api/tasks", methods=["POST"])
def api_create_task():
    user_id = api_auth(request)
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json or {}
    text = data.get("text", "").strip()
    due_date = data.get("due_date", "")
    priority = data.get("priority", "中")

    if not text:
        return jsonify({"error": "Missing 'text' field"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO tasks(user_id, text, due_date, priority) VALUES(?,?,?,?)",
                (user_id, text, due_date, priority))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()

    return jsonify({"id": new_id, "text": text, "due_date": due_date, "priority": priority}), 201

@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
def api_update_task(task_id):
    user_id = api_auth(request)
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json or {}
    text = data.get("text", "").strip()
    due_date = data.get("due_date", "")
    priority = data.get("priority", "中")

    if not text:
        return jsonify({"error": "Missing 'text' field"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE id=? AND user_id=?", (task_id, user_id))
    if not cur.fetchone():
        conn.close()
        return jsonify({"error": "Task not found"}), 404

    conn.execute("UPDATE tasks SET text=?, due_date=?, priority=? WHERE id=? AND user_id=?",
                 (text, due_date, priority, task_id, user_id))
    conn.commit()
    conn.close()

    return jsonify({"id": task_id, "text": text, "due_date": due_date, "priority": priority})

@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def api_delete_task(task_id):
    user_id = api_auth(request)
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE id=? AND user_id=?", (task_id, user_id))
    if not cur.fetchone():
        conn.close()
        return jsonify({"error": "Task not found"}), 404

    conn.execute("DELETE FROM tasks WHERE id=? AND user_id=?", (task_id, user_id))
    conn.commit()
    conn.close()

    return jsonify({"message": "Task deleted successfully"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True, port=5000)