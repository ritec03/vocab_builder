import contextlib
import logging
import os
from flask import Flask
from data_structures import DATABASE_FILE, FLASK_INSTANCE_FOLDER, FULL_DATABASE_PATH
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
    app = Flask(__name__, instance_relative_config=True, instance_path=FLASK_INSTANCE_FOLDER)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=F'sqlite:///{FULL_DATABASE_PATH}',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    with contextlib.suppress(OSError):
        os.makedirs(app.instance_path)
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