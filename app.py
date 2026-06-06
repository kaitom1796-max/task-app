from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        text TEXT NOT NULL,
        FOREIGN KEY(user_id)
        REFERENCES users(id)
    )
    """)

    conn.commit()
    conn.close()


init_db()


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
    SELECT COUNT(*)
    FROM tasks
    WHERE user_id=?
    AND text LIKE ?
    """,
    (
        session["user_id"],
        f"%{search}%"
    ))

    total = cur.fetchone()[0]

    cur.execute("""
    SELECT *
    FROM tasks
    WHERE user_id=?
    AND text LIKE ?
    ORDER BY id DESC
    LIMIT ?
    OFFSET ?
    """,
    (
        session["user_id"],
        f"%{search}%",
        per_page,
        offset
    ))

    tasks = cur.fetchall()

    conn.close()

    total_pages = (total + per_page - 1) // per_page

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
        cur = conn.cursor()

        try:

            cur.execute(
                """
                INSERT INTO users(username,password)
                VALUES(?,?)
                """,
                (
                    username,
                    generate_password_hash(password)
                )
            )

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

        cur = conn.cursor()

        cur.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        )

        user = cur.fetchone()

        conn.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

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

    if len(text) < 1:
        flash("タスクを入力してください")
        return redirect(url_for("home"))

    conn = get_db()

    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO tasks(user_id,text)
        VALUES(?,?)
        """,
        (
            session["user_id"],
            text
        )
    )

    conn.commit()
    conn.close()

    return redirect(url_for("home"))


@app.route("/delete/<int:task_id>")
def delete(task_id):

    conn = get_db()

    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM tasks
        WHERE id=?
        AND user_id=?
        """,
        (
            task_id,
            session["user_id"]
        )
    )

    conn.commit()
    conn.close()

    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)