import logging
import os
from flask import Flask
from database_orm import DatabaseManager
from user_bp import users_bp
from lesson_bp import lessons_bp
from flask_cors import CORS

logger = logging.getLogger(__name__)
logging.basicConfig(
    filename='test_log.log', 
    encoding='utf-8', 
    level=logging.DEBUG
)

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI='sqlite:///database.db',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    app.db_manager = DatabaseManager(app)
    app.register_blueprint(users_bp)
    app.register_blueprint(lessons_bp)

    CORS(app)

    return app

if __name__ == "__main__":
    init_db = DatabaseManager(None)
    app = create_app()
    # disable reloader to avoid loading data to db twice on initializing.
    app.run(port=8000, debug=True, use_reloader=False)