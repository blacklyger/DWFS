import io
import zipfile
from pathlib import Path

from dwfs import app as flask_app, db
from dwfs.models import AccountRequest, Media, User
from conftest import PASSWORD, csrf_token, login, make_user


def upload(user, client, url, *files):
    data = {f"file_{i}": (io.BytesIO(content), name) for i, (name, content) in enumerate(files)}
    data.update(csrf_token=user.token, current_subject="Mathe", file_path=url)
    return client.post("/add_media", data=data, content_type="multipart/form-data")


def query(fn):
    with flask_app.app_context():
        return fn()


def media(filename):
    return query(lambda: Media.query.filter_by(filename=filename).first())


def set_foreign_access(uid, value):
    with flask_app.app_context():
        Media.query.filter_by(unique_id=uid).first().set_foreign_access(value)


# --- Functionality -----------------------------------------------------------

def test_upload_list_and_download(client, user):
    assert upload(user, client, user.base, ("notes.txt", b"hello")).data == b"OK"

    page = client.get("/edit_subject/Mathe").get_data(as_text=True)
    assert "notes.txt" in page

    response = client.get(f"/download/{media('notes.txt').unique_id}")
    assert response.status_code == 200 and response.data == b"hello"


def test_folders_rename_and_zip(client, user):
    user.post("/add_folder", folder_name="Kapitel1", current_subject="Mathe", current_path=user.base)
    assert upload(user, client, f"{user.base}/Kapitel1", ("a.txt", b"A")).data == b"OK"

    # Renaming the folder and the subject keeps all stored paths consistent.
    user.post("/rename_file", old_filename="Kapitel1", new_filename="Kapitel2", current_subject="Mathe", rename_path=user.base)
    user.post("/rename_subject", old_subject_name="Mathe", new_subject_name="Mathematik")

    assert client.get(f"/download/{media('a.txt').unique_id}").data == b"A"

    token = csrf_token(client, "/subjects")
    response = client.post("/download_files", data={
        "csrf_token": token, "current_subject": "Mathematik",
        "current_path": "http://localhost/edit_subject/Mathematik", "change[]": ["Kapitel2"],
    })
    names = zipfile.ZipFile(io.BytesIO(response.data)).namelist()
    assert names == ["Kapitel2/a.txt"]


def test_share_folder_with_foreign_access(client, user, app):
    user.post("/add_folder", folder_name="Abgabe", current_subject="Mathe", current_path=user.base)
    folder = media("Abgabe")
    share_url = f"/share/alice/Mathe/Abgabe/{folder.unique_id}"
    user.post("/foreign_access", value="Ja", folder_uid=folder.unique_id)
    client.post("/logout", data={"csrf_token": user.token})

    # An anonymous visitor with the link may upload into the shared folder.
    token = csrf_token(client, share_url)
    client.post("/add_shared_files", content_type="multipart/form-data", data={
        "csrf_token": token, "folder_uid": folder.unique_id, "media_to_add": (io.BytesIO(b"x"), "loesung.pdf"),
    })
    uploaded = media("loesung.pdf")
    assert uploaded.in_folder == folder.unique_id
    assert Path(app.config["DATA_DIR"], "alice", "Mathe", "Abgabe", "loesung.pdf").is_file()


def test_account_request_flow(client, app):
    make_user("admin", "Admin")
    token = csrf_token(client, "/request_account")
    client.post("/req_new_acc", data={"username": "bob", "password": PASSWORD, "csrf_token": token})

    # The password is only stored as a hash.
    assert query(lambda: AccountRequest.query.first().password).startswith("scrypt:")

    login(client, "admin")
    client.post("/create_request_account", data={"access": "yes bob", "csrf_token": csrf_token(client, "/show_account_requests")})
    client.post("/logout", data={"csrf_token": csrf_token(client, "/profile")})

    assert login(client, "bob").headers["Location"].endswith("/profile")


# --- Authentication & authorization -----------------------------------------

def test_registration_is_admin_only(client, app):
    make_user("mallory")
    token = csrf_token(client)
    response = client.post("/register", data={"username": "evil", "password": PASSWORD, "selector": "Admin", "csrf_token": token})
    assert "/login" in response.headers["Location"]

    login(client, "mallory")
    token = csrf_token(client, "/profile")
    response = client.post("/register", data={"username": "evil", "password": PASSWORD, "selector": "Admin", "csrf_token": token})
    assert response.status_code == 403
    assert not query(lambda: User.query.filter_by(username="evil").first())


def test_account_approval_requires_admin(client, app):
    with flask_app.app_context():
        db.session.add(AccountRequest("eve", "scrypt:x", None, None))
        db.session.commit()
    make_user("mallory")
    login(client, "mallory")
    response = client.post("/create_request_account", data={"access": "yes eve", "csrf_token": csrf_token(client, "/profile")})
    assert response.status_code == 403
    assert not query(lambda: User.query.filter_by(username="eve").first())


def test_state_changing_routes_require_login(client, app):
    token = csrf_token(client)
    for url in ["/add_media", "/remove_media", "/add_subject", "/remove_subject", "/rename_subject",
                "/rename_file", "/add_folder", "/regenerate_uids", "/download_files", "/search_query",
                "/foreign_access", "/change_password", "/create_request_account", "/add_subject_dev"]:
        response = client.post(url, data={"csrf_token": token})
        assert response.status_code == 302 and "/login" in response.headers["Location"], url


def test_foreign_access_only_by_owner(client, user):
    user.post("/add_folder", folder_name="Privat", current_subject="Mathe", current_path=user.base)
    folder = media("Privat")
    client.post("/logout", data={"csrf_token": user.token})

    make_user("mallory")
    login(client, "mallory")
    response = client.post("/foreign_access", data={"value": "Ja", "folder_uid": folder.unique_id, "csrf_token": csrf_token(client, "/profile")})
    assert response.status_code == 404
    assert not media("Privat").has_foreign_access()


def test_shared_folder_is_read_only_without_foreign_access(client, user):
    user.post("/add_folder", folder_name="Info", current_subject="Mathe", current_path=user.base)
    upload(user, client, f"{user.base}/Info", ("plan.pdf", b"x"))
    upload(user, client, user.base, ("other.pdf", b"y"))
    folder = media("Info")
    client.post("/logout", data={"csrf_token": user.token})

    token = csrf_token(client)
    response = client.post("/remove_shared_files", data={"folder_uid": folder.unique_id, "media_to_remove": media("plan.pdf").unique_id, "csrf_token": token})
    assert response.status_code == 403

    # Even with foreign access, only files of *this* folder can be removed.
    set_foreign_access(folder.unique_id, True)
    client.post("/remove_shared_files", data={"folder_uid": folder.unique_id, "media_to_remove": media("other.pdf").unique_id, "csrf_token": token})
    assert media("other.pdf")


def test_login_bruteforce_throttle(client, app):
    make_user("alice")
    for _ in range(5):
        login(client, "alice", "wrong-password")
    response = login(client, "alice")
    assert "/login" in response.headers["Location"]


def test_password_change_requires_current_password(client, user):
    user.post("/change_password", current_password="wrong", password="new-password-123", password_confirm="new-password-123")
    client.post("/logout", data={"csrf_token": user.token})
    assert login(client, "alice").headers["Location"].endswith("/profile")


# --- CSRF ---------------------------------------------------------------------

def test_csrf_token_required(client, app):
    make_user("alice")
    response = client.post("/login", data={"username": "alice", "password": PASSWORD})
    assert response.status_code == 400


# --- Path traversal & input validation ---------------------------------------

def test_path_traversal_in_client_path_is_rejected(client, user, app):
    for path in [f"{user.base}/../../bob", f"{user.base}/%2e%2e/%2e%2e", "http://localhost/edit_subject/Other/x", "/etc/passwd"]:
        response = user.post("/add_folder", folder_name="x", current_subject="Mathe", current_path=path)
        assert response.status_code in (400, 404), path

    response = user.post("/add_folder", folder_name="x", current_subject="../alice", current_path=user.base)
    assert response.status_code in (400, 404)
    assert sorted(p.name for p in app.config["DATA_DIR"].iterdir()) == ["alice"]


def test_malicious_filenames_are_sanitized(client, user, app):
    upload(user, client, user.base, ("../../../escape.txt", b"x"))
    assert media("escape.txt").path == str(Path(app.config["DATA_DIR"], "alice", "Mathe"))
    assert not Path(app.config["DATA_DIR"], "escape.txt").exists()

    user.post("/add_subject", subject_name="../../etc")
    user.post("/add_folder", folder_name="../..", current_subject="Mathe", current_path=user.base)
    assert sorted(p.name for p in app.config["DATA_DIR"].iterdir()) == ["alice"]


def test_invalid_usernames_rejected(client, app):
    token = csrf_token(client, "/request_account")
    for name in ["../admin", "a", "x" * 40, "bad name", "<script>"]:
        client.post("/req_new_acc", data={"username": name, "password": PASSWORD, "csrf_token": token})
    assert query(lambda: AccountRequest.query.count()) == 0


def test_disallowed_extensions_rejected(client, user):
    response = upload(user, client, user.base, ("shell.php", b"<?php"), ("ok.txt", b"ok"))
    assert b"shell.php" in response.data
    assert not media("shell.php") and media("ok.txt")


def test_open_redirect_blocked(client, user):
    response = user.post("/remove_media", current_subject="Mathe", current_path="https://evil.example/phish")
    assert response.status_code == 400  # foreign URL is not a valid DWFS path

    response = user.post("/add_folder", folder_name="y", current_subject="Mathe", current_path=f"{user.base}")
    assert response.headers["Location"].startswith("/edit_subject/Mathe")


# --- SQL injection ----------------------------------------------------------

def test_sql_injection_attempts_are_harmless(client, user):
    upload(user, client, user.base, ("geheim.txt", b"x"))

    response = user.post("/search_query", value="' OR 1=1 --", current_subject="Mathe", path=user.base)
    assert response.get_json() == []

    response = user.post("/search_query", value="%", current_subject="Mathe", path=user.base)
    assert response.get_json() == []  # LIKE wildcards are escaped

    response = user.post("/search_query", value="gheim", current_subject="Mathe", path=user.base)
    assert [r["filename"] for r in response.get_json()] == ["geheim.txt"]

    client.post("/logout", data={"csrf_token": user.token})
    response = login(client, "alice' OR '1'='1", "' OR '1'='1")
    assert "/login" in response.headers["Location"]


def test_users_cannot_see_each_others_files(client, user):
    upload(user, client, user.base, ("alice.txt", b"x"))
    client.post("/logout", data={"csrf_token": user.token})

    make_user("mallory")
    login(client, "mallory")
    token = csrf_token(client, "/profile")
    response = client.post("/search_query", data={"value": "alice", "current_subject": "Mathe", "path": user.base, "csrf_token": token})
    assert response.status_code == 404
    assert client.get("/edit_subject/Mathe").status_code == 302


# --- XSS / content handling -------------------------------------------------

def test_html_uploads_are_never_rendered_inline(client, user):
    upload(user, client, user.base, ("page.html", b"<script>alert(1)</script>"), ("doc.pdf", b"%PDF"))

    response = client.get(f"/download/{media('page.html').unique_id}")
    assert response.headers["Content-Disposition"].startswith("attachment")

    response = client.get(f"/download/{media('doc.pdf').unique_id}")
    assert response.headers["Content-Disposition"].startswith("inline")
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_security_headers(client, app):
    headers = client.get("/").headers
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_share_ids_are_unguessable(client, user):
    user.post("/add_folder", folder_name="A", current_subject="Mathe", current_path=user.base)
    uid = media("A").unique_id
    assert len(uid) == 16 and uid.isalnum()
