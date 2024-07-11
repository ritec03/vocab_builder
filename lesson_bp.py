from flask import Blueprint, request, jsonify, current_app

from database_orm import DatabaseManager, ValueDoesNotExistInDB
from exercise import LessonTask, SpacedRepetitionLessonGenerator

lessons_bp = Blueprint('lessons', __name__)


@lessons_bp.route('/users/<int:user_id>/lessons', methods=['POST'])
def request_lesson(user_id: int):
    """
    Retrieves or generates lesson for user_id and returns the first task
    {
        "lesson_id": int,
        "task": {
            "order": Tuple[int,int],
            "first_task": json representation of a task
        }
    }
    """
    try:
        db_manager: DatabaseManager = current_app.db_manager
        user = db_manager.get_user_by_id(user_id)
        if not user:
            return jsonify({"error": f"User with user id {user_id} does not exist."}), 404

        lesson_head = db_manager.retrieve_lesson(user_id)
        if lesson_head:
            return jsonify(lesson_head), 201
        else:
            lesson_gen = SpacedRepetitionLessonGenerator(user_id, db_manager)
            try:
                lesson_plan = lesson_gen.generate_lesson()
            except:
                return jsonify({"error": "Failed to generate lesson."}), 500
            try:
                gen_lesson_head = db_manager.save_lesson_plan(user_id, lesson_plan)
            except:
                return jsonify({"error": "Failed to save the lesson."}), 500
            return jsonify(gen_lesson_head), 201
    except:
        return jsonify({"error": "Server encountered an error."}), 500


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
                "order": Tuple[int, int]
                "task": json task representation
            } | None if no more tasks and the lesson is complete.
        }
    """
    try:
        db_manager: DatabaseManager = current_app.db_manager
        data = request.json
        # TODO check user answer?
        user = db_manager.get_user_by_id(user_id)
        if not user:
            return jsonify({"error": f"User with user id {user_id} does not exist."}), 404
        try:
            answer = data["answer"]
            task_id = data["task_id"]
            order = data["task_order"]
        except KeyError:
            return jsonify({"error": "Request data is missing required fields."}), 500

        lesson_task = LessonTask(user_id, db_manager, lesson_id)
        try:
            history_entry = lesson_task.evaluate_task(answer, task_id, order)
        except:
            return jsonify({"error": "Failed to evaluate task."}), 500
        try:
            next_task = lesson_task.get_next_task()
        except:
            return jsonify({"error": "Failed to retrieve the next task."}), 500
        return jsonify({"score": list(history_entry.evaluation_result), "next_task": next_task}), 201
    except:
        return jsonify({"error": "Server encountered an error."}), 500
