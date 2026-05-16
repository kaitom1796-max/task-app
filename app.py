from flask import Flask, render_template, request, jsonify
import sqlite3

app = Flask(__name__)

DB_NAME = 'todo.db'

# データベースとテーブル（タスクを入れる箱）を準備する関数
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # tasksという名前のテーブルがなければ作る
    # id（自動で増える背番号）と、text（タスクの文字）の2つの列を持たせる
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# アプリ起動時にデータベースを初期化
init_db()

@app.route('/')
def index():
    # 画面を開いたときに、データベースから保存されているタスクをすべて読み込む
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id, text FROM tasks')
    rows = cursor.fetchall()
    conn.close()
    
    # 画面側のJavaScriptで扱いやすい形式（辞書のリスト）に変換
    saved_tasks = [{"id": row[0], "text": row[1]} for row in rows]
    
    # index.htmlにデータを渡して表示させる
    return render_template('index.html', tasks=saved_tasks)


@app.route('/add_task', methods=['POST'])
def add_task():
    data = request.get_json()
    task_text = data.get('task')
    
    if task_text:
        # データベースにタスクを「挿入（INSERT）」する
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO tasks (text) VALUES (?)', (task_text,))
        conn.commit()
        
        # 今しがた追加されたタスクのID（背番号）を取得する
        new_id = cursor.lastrowid
        conn.close()
        
        new_task = {"id": new_id, "text": task_text}
        return jsonify({"status": "success", "task": new_task})
    
    return jsonify({"status": "error"}), 400


@app.route('/delete_task/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    # データベースから指定されたIDのタスクを「削除（DELETE）」する
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()
    
    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(debug=True)