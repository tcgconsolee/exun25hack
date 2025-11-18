import os
from flask import Flask, render_template, redirect, url_for, request, flash, session, jsonify
from flask_login import (
    LoginManager, UserMixin, login_user, current_user,
    login_required, logout_user
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

class Users(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

with app.app_context():
    db.create_all()

    username = "nuxenite"
    if not Users.query.filter_by(username=username).first():
        new_user = Users(
            username=username,
            password=generate_password_hash("supernova"),  
            is_admin=True  
        )
        db.session.add(new_user)
        db.session.commit()
        print("Created user:", username)
    else:
        print("User already exists:", username)

@login_manager.user_loader
def loader_user(user_id):
    return Users.query.get(int(user_id))


@app.route("/")
@app.route("/index")
@login_required
def index():
    return render_template("index.html")

@app.route("/lab")
@login_required
def venues():
    return render_template("lab.html")

@app.route("/surveillance")
@login_required
def announcements():
    return render_template("surveillance.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form["uname"].strip()
        password = request.form["psw"].strip()
        
        if not username or not password:
            flash("Please fill in all fields.", "error")
            return redirect(url_for("login"))

        if username.lower().startswith("nuxenite"):
            query = text(f"SELECT * FROM users WHERE username = '{username}'")
            result = db.session.execute(query)
            user_row = result.fetchone()
            app.logger.debug("Raw query = %s", query)
            
            if user_row:
                user = Users.query.get(user_row[0])
                
                if user:
                    if check_password_hash(user.password, password):
                        login_user(user)
                        flash("Login successful!", "success")
                        return redirect(url_for("index"))
                    else:
                        flash("Invalid password.", "error")
                        return redirect(url_for("login"))
                else:
                    flash("Invalid credentials.", "error")
                    return redirect(url_for("login"))
            else:
                hashed_pw = generate_password_hash(password)
                new_user = Users(username=username, password=hashed_pw)
                db.session.add(new_user)
                db.session.commit()
                login_user(new_user)
                flash("New account created and logged in.", "success")
                return redirect(url_for("index"))
        
        else:
            user = Users.query.filter_by(username=username).first()
            
            if user:
                if not check_password_hash(user.password, password):
                    flash("Invalid password.", "error")
                    return redirect(url_for("login"))
                login_user(user)
                flash("Login successful!", "success")
                return redirect(url_for("index"))
            else:
                hashed_pw = generate_password_hash(password)
                new_user = Users(username=username, password=hashed_pw)
                db.session.add(new_user)
                db.session.commit()
                login_user(new_user)
                flash("New account created and logged in.", "success")
                return redirect(url_for("index"))
    
    return render_template("login.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)