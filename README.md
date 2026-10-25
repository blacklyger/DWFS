# DWFS – self-hosted file sharing for schools

**DWFS** (*"Don't wanna wait for files and stuff"*) is a self-hostable web application for
uploading, organizing and sharing files. I built it during the COVID-19 pandemic for my school.
Teachers and students needed a fast and uncomplicated way to exchange material during remote
teaching, and downloads from the school's existing platform were too slow.

DWFS was presented at the school, but it was not adopted by its teachers and students. It was
still used and tested in real-world scenarios, and that practical use shaped many of the later
features (see [Project history](#project-history)).

The main design goals were **simplicity**, **speed** and **security**. Anyone who receives a
link can download a file without an account, while uploads, folder management and sharing
settings stay protected behind authentication.

## Features

- **Subjects and folders:** each user organizes files by subject (e.g. *Mathe*, *Informatik*), with nested folders
- **Multi-file upload** with a live progress bar and transfer rate
- **Share links:** every file and folder gets an unguessable link that can be downloaded without an account
- **Shared upload folders ("Fremdzugang"):** the owner can let link holders upload into a folder, e.g. so students can hand in assignments
- **ZIP download** of selected files and folders (folders are included recursively)
- **Search** within a subject or folder, plus pagination
- **Account requests:** visitors can request an account, and an admin approves it
- **Roles:** `User` and `Admin`. Admins create accounts and approve requests
- Rename, regenerate share links and delete, all from the browser

## Security

Users upload arbitrary files and the app writes to the server's filesystem, so DWFS treats
every request parameter as hostile. The table maps each threat to the control that handles it
and the place in the code where it lives.

| Threat | Control | Where |
|---|---|---|
| **Path traversal** (`../`, encoded `%2e%2e`, absolute paths) | All disk access goes through a single choke point, `confine()`. It resolves the final path and refuses anything outside the data directory. Every path segment, file, folder, subject and user name is validated with an allow-list. The client only sends the URL of the current page, and the server re-derives and validates the directory from it. | `dwfs/security.py` |
| **SQL injection** | All database access goes through the SQLAlchemy ORM with bound parameters. No SQL is assembled from strings. LIKE wildcards in search input are escaped. | `dwfs/search.py`, all models |
| **CSRF** | `Flask-WTF` CSRFProtect is enabled globally for every POST request, including AJAX (via the `X-CSRFToken` header). Logout is a POST request. | `dwfs/__init__.py`, templates |
| **Broken access control / IDOR** | Every state-changing route requires a login and filters by the current user as owner. Admin routes use an `admin_required` decorator. Foreign-access settings can only be changed by the folder owner. Shared folders accept uploads/deletions only when the owner enabled it, and only for files inside that folder. | `dwfs/main.py`, `dwfs/share.py`, `dwfs/auth.py` |
| **Stored XSS through uploads** | Only harmless types (PDF, images, audio/video, text) are shown inline. Everything else, including HTML, is served as `attachment`, together with `X-Content-Type-Options: nosniff`. | `download_file()` in `dwfs/main.py` |
| **XSS in the UI** | Jinja2 autoescaping is used in all templates. Dynamically rendered search results are escaped in JavaScript (`escapeHtml`) or inserted via `.text()`. | `dwfs/static/js/base.js` |
| **Malicious uploads** | An extension allow-list is applied, filenames are sanitized with `secure_filename`, and the upload size is configurable (`MAX_CONTENT_LENGTH`). | `add_media_data()` |
| **Guessable share links** | Links use 16-character IDs from `secrets` (≈ 95 bits of entropy) instead of `random`. | `generate_uid()` |
| **Credential theft / brute force** | Passwords are hashed with **scrypt**, including pending account requests (never plaintext). There is a minimum password length, a login throttle (5 failures → 15 min lock per IP and user), constant-time behaviour for unknown users, a session reset on login (against session fixation), and the current password is required to change it. | `dwfs/auth.py`, `dwfs/security.py` |
| **Session hijacking** | Session cookies are `HttpOnly`, `SameSite=Lax` and `Secure` by default. Flask-Login's strong session protection is enabled. | `dwfs/__init__.py` |
| **Open redirect** | Redirect targets taken from form data are restricted to local paths. | `safe_redirect_target()` |
| **Clickjacking, content injection** | Response headers: Content-Security-Policy (incl. `frame-ancestors 'none'`, `object-src 'none'`), `X-Frame-Options: DENY`, `Referrer-Policy`, and HSTS when cookies are `Secure`. Third-party assets are pinned with Subresource Integrity. | `set_security_headers()` |
| **Secret leakage** | No secrets in the repository. The `SECRET_KEY` comes from the environment or is generated once (file mode `0600`). The database, keys and uploads are git-ignored. | `load_secret_key()`, `.gitignore` |

All of these controls are covered by automated tests (`tests/test_dwfs.py`). The tests try
path traversal, SQL injection, CSRF, privilege escalation, IDOR, open redirects and XSS uploads
against the real application.

### Security review (2026)

Before publishing, I reviewed the original pandemic-era code base and fixed these findings:

- **Critical:** `/register` was reachable without a login, so anyone could create an admin account. Account approval and several file routes had no authentication or authorization checks.
- **High:** Path traversal was possible through client-supplied paths and unvalidated user/subject names. Pending account requests stored passwords in plaintext. Uploaded HTML was rendered inline (stored XSS). The `SECRET_KEY` was hardcoded.
- **Medium:** Share IDs came from a non-cryptographic PRNG. There was an open redirect via form fields and DOM XSS in the search results. ZIP archives were written into the public `static/` folder. Rename operations left stale paths in the database.

## Quick start

Requirements: Python 3.10+.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Create the first admin (registration of further users is admin-only)
flask --app dwfs create-admin admin

# Local development over plain HTTP (secure cookies need HTTPS)
DWFS_COOKIE_SECURE=0 python run_app.py
```

Open <http://127.0.0.1:5000> and log in.

### Production

Run DWFS with a WSGI server behind a TLS-terminating reverse proxy (e.g. nginx or Caddy):

```bash
pip install gunicorn
DWFS_BEHIND_PROXY=1 gunicorn --bind 127.0.0.1:8000 --workers 4 run_app:application
```

Set `client_max_body_size` in nginx to match `DWFS_MAX_UPLOAD_MB`.

### Configuration

All settings are environment variables:

| Variable | Default | Description |
|---|---|---|
| `DWFS_SECRET_KEY` | generated in `instance/secret_key` | Key for signing sessions and CSRF tokens |
| `DWFS_DATABASE_URL` | `sqlite:///instance/dwfs.sqlite` | Any SQLAlchemy database URL |
| `DWFS_DATA_DIR` | `./data` | Directory for uploaded files |
| `DWFS_MAX_UPLOAD_MB` | `2048` | Maximum request size in MB |
| `DWFS_COOKIE_SECURE` | `1` | Send cookies only over HTTPS. Set `0` only for local tests |
| `DWFS_BEHIND_PROXY` | `0` | Trust `X-Forwarded-*` headers from one reverse proxy |

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Project structure

```
dwfs/
├── __init__.py   App factory, configuration, security headers, CLI (create-admin)
├── security.py   Path confinement, input validation, secure IDs, login throttle
├── auth.py       Login, logout, admin-only registration
├── main.py       Subjects, uploads, downloads, ZIP export, account requests
├── folder.py     Folder creation
├── share.py      Public share pages and foreign-access uploads
├── search.py     Search within subjects/folders
├── models.py     SQLAlchemy models
├── templates/    Jinja2 templates (Bulma CSS)
└── static/       JavaScript, CSS, images
tests/            Functional and security tests (pytest)
```

## Known limitations

- The login throttle is kept in memory per worker process. For larger deployments, add rate limiting at the reverse proxy (e.g. nginx `limit_req`) as well.
- The CSP still needs `'unsafe-inline'` for scripts because of inline event handlers in the templates.
- Uploaded files are not scanned for malware.
- Share links work like passwords: anyone with the link can download. Use *regenerate share links* to revoke one.

## Project history

- **2020-05-04**: Repository created, at the start of the first COVID-19 school closures
- **2020-05-07**: First release with login, subjects, uploads (extension allow-list) and download links
- **2020-06-10**: Upload size limit, file sizes, deleting subjects, admin tool for assigning subjects to users
- **2020-12-03**: Renaming of subjects and files
- **2020-12-25**: Nested folders, account requests with admin approval, admin role, regenerating share IDs
- **2021-02-04**: Public share page for folders and "foreign access" (link holders can upload, e.g. to hand in assignments)
- **2021-02-08**: Sanity checks and controls for foreign access
- **2021-03-13**: Share links can be regenerated per file
- **2021-12-08**: Search within subjects and folders
- **2022-03-13**: Responsive tables, sanitized folder names, better search
- **2022-06-13**: Stricter filename sanitizing, file sizes in search results
- **2022-06-26**: Download of several files as a ZIP archive
- **2024-08-13**: Pagination, AJAX upload with progress bar and transfer rate
- **2026-10-24**: Security review and hardening (see above), automated test suite, new documentation

## Tech stack

Python · Flask · SQLAlchemy · Flask-Login · Flask-WTF · Jinja2 · jQuery · Bulma
