from flask import Blueprint, request, jsonify, current_app

from database_orm import DatabaseManager, ValueDoesNotExistInDB

users_bp = Blueprint('users', __name__)

# TODO add guards for data

@users_bp.route('/users', methods=['POST'])
def create_user():
    data = request.json
    db_manager: DatabaseManager = current_app.db_manager
    try:
        user_id = db_manager.insert_user(data['user_name'])
        return jsonify({"user_id": user_id}), 201
    except Exception as e:
        print(e)
        return jsonify({"error": "User with the username already exists."}), 409

@users_bp.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    db_manager: DatabaseManager = current_app.db_manager
    try:
        user = db_manager.get_user_by_id(user_id)
    except:
        return jsonify({"error": "Database encountered an erorr."}), 500
    if user:
        return jsonify(user), 200
    else:
        return jsonify({"error": "User not found"}), 404

@users_bp.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    db_manager: DatabaseManager = current_app.db_manager
    try:
        db_manager.remove_user(user_id)
        return jsonify({"status": "User deleted"}), 200
    except ValueDoesNotExistInDB:
        return jsonify({"error": "User not found"}), 404
    except Exception:
        return jsonify({"error": "Database encountered an erorr."}), 500
