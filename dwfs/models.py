from . import db
from flask_login import UserMixin


class User(UserMixin, db.Model):

    __tablename__ = "users"

    id          = db.Column(db.Integer, primary_key=True)
    username    = db.Column(db.String(100), unique=True)
    password    = db.Column(db.String(100))
    role        = db.Column(db.String(100))

    def __init__(self, username, password, role):
        self.username = username
        self.password = password
        self.role     = role

    @property
    def is_admin(self):
        return True if self.role == "Admin" else False

class Media(UserMixin, db.Model):
    
    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(100))
    subject      = db.Column(db.String(100))
    filename     = db.Column(db.String(100))
    path         = db.Column(db.String(200))
    category     = db.Column(db.String(10))
    unique_id    = db.Column(db.String(10), unique=True)

    def __init__(self, name, subject, filename, path, category, unique_id):
        self.name         = name
        self.subject      = subject
        self.filename     = filename
        self.path         = path
        self.category     = category
        self.unique_id    = unique_id

    def is_dir(self):
        return True if self.category == "folder" else False


class Subjects(UserMixin, db.Model):
    
    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(100))
    subject      = db.Column(db.String(20))

    def __init__(self, name, subject):
        self.name         = name
        self.subject      = subject


class AccountRequest(UserMixin, db.Model):

    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(100), unique=True)
    password   = db.Column(db.String(100))
    date       = db.Column(db.DateTime)
    ip_address = db.Column(db.String(100))

    def __init__(self, username, password, date, ip_address):
        self.username   = username
        self.password   = password
        self.date       = date
        self.ip_address = ip_address