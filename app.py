from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager, current_user
import os

from extensions import bcrypt
from models.user import User

# ROUTES
from routes.auth import auth_bp
from routes.catalog import catalog_bp
from routes.profile import profile_bp
from routes.family_rate import family_rate_bp

app = Flask(__name__, instance_relative_config=True)

# Initialize bcrypt
bcrypt.init_app(app)

app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "dev")

# ❗❗ REMOVE init_db() -- breaks Render
# init_db()

# LOGIN MANAGER
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(user_id)

# REGISTER BLUEPRINTS
app.register_blueprint(auth_bp)
app.register_blueprint(catalog_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(family_rate_bp)

@app.route("/")
def home():
    return redirect(url_for("catalog.games"))

if __name__ == "__main__":
    app.run(debug=True)
