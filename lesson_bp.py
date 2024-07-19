import json
import logging
from flask import Blueprint, request, jsonify, current_app

from database_orm import DatabaseManager, ValueDoesNotExistInDB
from exercise import LessonTask, SpacedRepetitionLessonGenerator
logger = logging.getLogger(__name__)

lessons_bp = Blueprint('lessons', __name__)

@lessons_bp.route('/users/<int:user_id>/lessons', methods=['POST'])
def request_lesson(user_id: int):
    """
    Retrieves or generates a lesson for the given user_id and returns the first task.

    Args:
        user_id (int): The ID of the user.

    Returns:
        A JSON response containing the lesson information and the first task:
        {
            "lesson_id": int,
            "task": {
                "order": Tuple[int, int],
                "first_task": json representation of a task
            }
        }

    Raises:
        404: If the user with the given user_id does not exist.
        500: If there is an error while retrieving or generating the lesson.

    """
    try:
        db_manager: DatabaseManager = current_app.db_manager
        user = db_manager.get_user_by_id(user_id)
        if not user:
            return jsonify({"error": f"User with user id {user_id} does not exist."}), 404

        lesson_head = db_manager.retrieve_lesson(user_id)
        if lesson_head:
            task = lesson_head["task"]["first_task"]
            if not task:
                logger.warning("Task is empty.")
            lesson_head["task"]["first_task"] = task.to_json()
            if not lesson_head["task"]["first_task"]:
                logger.warning("Task is empty after converting to dict.")
            return jsonify(lesson_head), 201
        else:
            lesson_gen = SpacedRepetitionLessonGenerator(user_id, db_manager)
            try:
                lesson_plan = lesson_gen.generate_lesson()
            except Exception as e:
                logger.error(f"Failed to generate lesson. Error: {str(e)}")
                return jsonify({"error": "Failed to generate lesson."}), 500
            try:
                gen_lesson_head = db_manager.save_lesson_plan(user_id, lesson_plan)
            except:
                logger.error(f"Failed to save lesson. Error: {str(e)}")
                return jsonify({"error": "Failed to save the lesson."}), 500
            task = gen_lesson_head["task"]["first_task"]
            if not task:
                logger.warning("Task is empty.")
            gen_lesson_head["task"]["first_task"] = task.to_json()
            if not gen_lesson_head["task"]["first_task"]:
                logger.warning("Task is empty after converting to dict.")
            return jsonify(gen_lesson_head), 201
    except Exception as e:
        logger.error(f"General error occurred. Error: {str(e)}")
        return jsonify({"error": "Server encountered an error."}), 500


@lessons_bp.route('/users/<int:user_id>/lessons/<lesson_id>/tasks/submit', methods=['POST'])
def submit_answer(user_id: int, lesson_id: int):
    """
    Submits the user's answer for a lesson task and returns the evaluation result and the next task.

    Args:
        user_id (int): The ID of the user submitting the answer.
        lesson_id (int): The ID of the lesson.

    Returns:
        A JSON response containing the evaluation result and the next task (if available).

        Response structure:
        {
            "score": List[Dict[int, int]],
            "next_task": {
                "order": Tuple[int, int],
                "task": json task representation
            }
        }
        OR if the lesson is completed
        {
            "score": List[Dict[int, int]],
            "next_task": None}
            "final_scores": List[Score]
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
        
        if not next_task:
            final_scores = db_manager.finish_lesson(user_id, lesson_id)
            return jsonify({"score": list(history_entry.evaluation_result), "next_task": None, "final_scores": list(final_scores)}), 201
        else:
            return jsonify({"score": list(history_entry.evaluation_result), "next_task": {
                "order": next_task["order"],
                "task": next_task["task"].to_json(),
            }}), 201
    except Exception as e:
        logger.error(f"General error occured. Error: {str(e)}")
        return jsonify({"error": "Server encountered an error."}), 500
