from flask import Blueprint, request, jsonify, current_app

from database_orm import DatabaseManager, ValueDoesNotExistInDB

lessons_bp = Blueprint('lessons', __name__)

@lessons_bp.route('/users/<int:user_id>/lessons', methods=['POST'])
def request_lesson(user_id: int):
    """
    Retrieves or generates lesson for user_id and returns the first task
    {
        "lesson_id": int,
        "task": {
            "order": Tuple[int,int],
            "task": json representation of a task
        }
    }
    """

@lessons_bp.route('/users/<int:user_id>/lessons/<lesson_id>/tasks/submit', methods=['POST'])
def submit_answer(user_id: int, lesson_id: int):
    """
    Request structure:
        {
            "task_id": int
            "task_order": Tuple[int,int]
            "answer": str
        }

    Response structure:
        {
            "score": List[Dict[int, int]]
            "next_task": {
                "task": json task representation
                "order": Tuple[int, int]
            } | None if no more tasks and the lesson is complete.
        }
    """