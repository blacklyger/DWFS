from . import db
from flask_login import UserMixin


class User(UserMixin, db.Model):

    id          = db.Column(db.Integer, primary_key=True)
    username    = db.Column(db.String(100), unique=True)
    password    = db.Column(db.String(100))

    def __init__(self, username, password, role):
        self.username = username
        self.password = password

class Media(UserMixin, db.Model):
    
    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(100))
    subject      = db.Column(db.String(100))
    filename     = db.Column(db.String(100))
    unique_id    = db.Column(db.String(10), unique=True)

    def __init__(self, name, subject, filename, unique_id):
        self.name         = name
        self.subject      = subject
        self.filename     = filename
        self.unique_id    = unique_id


class Subjects(UserMixin, db.Model):
    
    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(100))
    subject      = db.Column(db.String(20))

    def __init__(self, name, subject):
        self.name         = name
        self.subject      = subject

