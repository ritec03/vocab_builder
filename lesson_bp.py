from dataclasses import asdict
import logging
from flask import Blueprint, request, jsonify, current_app

from database_orm import DatabaseManager, Order
from exercise import LessonTask, SpacedRepetitionLessonGenerator
logger = logging.getLogger(__name__)

lessons_bp = Blueprint('lessons', __name__)

@lessons_bp.route('/users/<int:user_id>/lessons', methods=['POST'])
def create_lesson(user_id: int):
    """
    Creates a new lesson for a given user.

    Args:
        user_id (int): The ID of the user for whom the lesson is created.

    Returns:
        A JSON response containing the lesson information and the first task:
        {
            "lesson_id": int,
            "first_task": {
                "order": {
                    "sequence_num": int,
                    "attempt": int
                },
                "task": json representation of a task
            }
        }, 201

        Error Statuses:
        - 404: User not found
        - 400: There is already an uncompleted lesson for this user
        - 500: Failed to generate lesson or save the lesson

    Raises:
        Exception: If there is an error while creating the lesson.

    """
    db_manager: DatabaseManager = current_app.db_manager
    try:
        user = db_manager.get_user_by_id(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # Check for existing uncompleted lessons
        existing_lesson = db_manager.retrieve_lesson_serializeable(user_id)
        if existing_lesson:
            return jsonify({"error": "There is already an uncompleted lesson for this user"}), 400

        lesson_gen = SpacedRepetitionLessonGenerator(user_id, db_manager)
        try:
            lesson_plan = lesson_gen.generate_lesson()
            logger.info(f"Generated lesson: {lesson_plan}")
        except Exception as e:
            logger.error(f"Failed to generate lesson. Error: {str(e)}")
            return jsonify({"error": "Failed to generate lesson."}), 500
        try:
            gen_lesson_head = db_manager.save_lesson_plan_serializable(user_id, lesson_plan)
        except:
            logger.error(f"Failed to save lesson. Error: {str(e)}")
            return jsonify({"error": "Failed to save the lesson."}), 500
        logger.info(f"Generated lesson head: {gen_lesson_head}")
        return jsonify(gen_lesson_head), 201

    except Exception as e:
        logger.error(f"Failed to create a lesson. Error: {str(e)}")
        return jsonify({"error": "Failed to create lesson"}), 500
    
@lessons_bp.route('/users/<int:user_id>/lessons', methods=['GET'])
def get_lesson(user_id: int):
    """
    Retrieve a lesson for a given user.

    Args:
        user_id (int): The ID of the user.

    Returns:
        {
            "lesson_id": int,
            "first_task": {
                "order": {
                    "sequence_num": int,
                    "attempt": int
                },
                "task": json representation of a task
            }
        }, 200

    Raises:
        Exception: If there is an error retrieving the lesson.

    """
    db_manager: DatabaseManager = current_app.db_manager
    try:
        lesson_head = db_manager.retrieve_lesson_serializeable(user_id)
        if not lesson_head:
            logger.info("No active lesson available for this user.")
            return create_lesson(user_id)
        return jsonify(lesson_head), 200
    except Exception as e:
        logger.error(f"Failed to retrieve lesson. Error: {str(e)}")
        return jsonify({"error": "Failed to retrieve lesson"}), 500


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
            "score": List[Dict[str, Union[LexicalItem, int]]],
            "next_task": {
                "order": {
                    "sequence_num": int,
                    "attempt": int
                },
                "task": json task representation
            }
        }
        OR if the lesson is completed
        {
            "score": List[Dict[str, Union[LexicalItem, int]]],
            "next_task": None}
            "final_scores": List[Dict[str, Union[LexicalItem, int]]]
        }
    """
    # TODO implement behaviour for unfinished or interrupted lessons.
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
            history_entry = lesson_task.evaluate_task(answer, task_id, Order(**order))
            logger.info(f"Evaluated task. Result: {history_entry.evaluation_result}")
        except:
            return jsonify({"error": "Failed to evaluate task."}), 500
        try:
            next_task = lesson_task.get_next_task()
        except:
            return jsonify({"error": "Failed to retrieve the next task."}), 500
        
        task_score = db_manager.convert_scores(history_entry.evaluation_result)
        task_score = list(map(lambda score_dict: {"word": score_dict["word"].to_json(), "score": score_dict["score"]}, task_score))
        logger.info(f"Task score: {task_score}")
        if not next_task:
            final_scores = db_manager.finish_lesson(user_id, lesson_id)
            final_scores = list(map(lambda score_dict: {"word": score_dict["word"].to_json(), "score": score_dict["score"]}, final_scores))
            logger.info(f"Final scores: {final_scores}")
            return jsonify({"score": task_score, "next_task": None, "final_scores": list(final_scores)}), 201
        else:
            return jsonify({"score": task_score, "next_task": {
                "order": asdict(next_task["order"]),
                "task": next_task["task"].to_json(),
            }}), 201
    except Exception as e:
        logger.error(f"General error occured. Error: {str(e)}")
        return jsonify({"error": "Server encountered an error."}), 500
