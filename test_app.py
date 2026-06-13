import os
import pytest
import tempfile
import json
from base64 import b64encode

@pytest.fixture
def client():
    # テスト用の一時的なデータベースをセットアップ
    db_fd, temp_db_path = tempfile.mkstemp()
    import app as todo_app
    todo_app.DB_NAME = temp_db_path
    todo_app.app.config['TESTING'] = True
    
    with todo_app.app.test_client() as client:
        with todo_app.app.app_context():
            todo_app.init_db()
        yield client

    os.close(db_fd)
    os.unlink(temp_db_path)

def test_register_and_login(client):
    # ユーザー登録のテスト
    rv = client.post('/register', data=dict(username='testuser', password='password123'), follow_redirects=True)
    assert "登録完了".encode("utf-8") in rv.data or b'login' in rv.data

    # ログインのテスト
    rv = client.post('/login', data=dict(username='testuser', password='password123'), follow_redirects=True)
    assert "タスク管理".encode("utf-8") in rv.data

def test_password_reset(client):
    # 事前にユーザー作成
    client.post('/register', data=dict(username='resetuser', password='oldpassword'), follow_redirects=True)
    
    # パスワードリセット実行
    rv = client.post('/reset_password', data=dict(username='resetuser', password='newpassword123'), follow_redirects=True)
    assert "リセット".encode("utf-8") in rv.data or b'login' in rv.data

    # 新しいパスワードでログインできるか確認
    rv = client.post('/login', data=dict(username='resetuser', password='newpassword123'), follow_redirects=True)
    assert b'logout' in rv.data

def test_rest_api_lifecycle(client):
    # APIテスト用のユーザーをWebから登録
    client.post('/register', data=dict(username='apiuser', password='apipassword'), follow_redirects=True)
    
    # Basic認証ヘッダーの作成
    valid_credentials = b64encode(b"apiuser:apipassword").decode("utf-8")
    headers = {"Authorization": f"Basic {valid_credentials}"}

    # 1. タスク追加 (POST)
    task_data = {"text": "APIテストタスク", "due_date": "2026-12-31", "priority": "高"}
    res = client.post('/api/tasks', data=json.dumps(task_data), content_type='application/json', headers=headers)
    assert res.status_code == 201
    json_data = json.loads(res.data)
    task_id = json_data["id"]
    assert json_data["text"] == "APIテストタスク"

    # 2. タスク一覧取得 (GET)
    res = client.get('/api/tasks', headers=headers)
    assert res.status_code == 200
    tasks_list = json.loads(res.data)
    assert len(tasks_list) >= 1

    # 3. タスク編集 (PUT)
    updated_data = {"text": "編集されたタスク", "due_date": "2026-06-30", "priority": "低"}
    res = client.put(f'/api/tasks/{task_id}', data=json.dumps(updated_data), content_type='application/json', headers=headers)
    assert res.status_code == 200
    assert json.loads(res.data)["text"] == "編集されたタスク"

    # 4. タスク削除 (DELETE)
    res = client.delete(f'/api/tasks/{task_id}', headers=headers)
    assert res.status_code == 200