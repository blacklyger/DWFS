from . import db
from flask_login import UserMixin

class User(UserMixin, db.Model):

    __tablename__ = "users"

    id          = db.Column(db.Integer, primary_key=True)
    username    = db.Column(db.String(100), unique=True)
    password    = db.Column(db.String(255))
    role        = db.Column(db.String(100))

    def __init__(self, username, password, role):
        self.username = username
        self.password = password
        self.role     = role

    @property
    def is_admin(self):
        return self.role == "Admin"

class Media(db.Model):

    id        = db.Column(db.Integer, primary_key=True)
    name      = db.Column(db.String(100))
    subject   = db.Column(db.String(100))
    filename  = db.Column(db.String(100))
    path      = db.Column(db.String(500))
    category  = db.Column(db.String(10))
    unique_id = db.Column(db.String(200), unique=True)
    in_folder = db.Column(db.String(200))
    faccess   = db.Column(db.Boolean, default=False)

    def __init__(self, name, subject, filename, path, category, unique_id, in_folder, faccess = False):
        self.name      = name
        self.subject   = subject
        self.filename  = filename
        self.path      = path
        self.category  = category
        self.unique_id = unique_id
        self.in_folder = in_folder
        self.faccess   = faccess

    def is_dir(self):
        return self.category == "folder"

    def set_foreign_access(self, value: bool):
        self.faccess = value
        db.session.commit()

    def has_foreign_access(self):
        return bool(self.faccess)


class Subjects(db.Model):

    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(100))
    subject      = db.Column(db.String(100))

    def __init__(self, name, subject):
        self.name         = name
        self.subject      = subject


class AccountRequest(db.Model):

    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(100), unique=True)
    # Only the password hash is stored, never the plaintext password.
    password   = db.Column(db.String(255))
    date       = db.Column(db.DateTime)
    ip_address = db.Column(db.String(100))

    def __init__(self, username, password, date, ip_address):
        self.username   = username
        self.password   = password
        self.date       = date
        self.ip_address = ip_address
