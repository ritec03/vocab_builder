from dataclasses import asdict
import logging
from flask import Blueprint, request, jsonify, current_app

from database_orm import DatabaseManager, Order
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
            "first_task": {
                "order": {
                    "sequence_num": int,
                    "attempt": int
                },
                "task": json representation of a task
            }
        }

    Raises:
        404: If the user with the given user_id does not exist.
        500: If there is an error while retrieving or generating the lesson.

    """
    try:
        db_manager: DatabaseManager = current_app.db_manager # type: ignore
        user = db_manager.get_user_by_id(user_id)
        if not user:
            return jsonify({"error": f"User with user id {user_id} does not exist."}), 404

        lesson_head = db_manager.retrieve_lesson(user_id)
        logger.info(f"A lesson was successfully retrieved. The leason head is {lesson_head}")
        if lesson_head:
            task = lesson_head["first_task"]["task"]
            if not task:
                logger.warning("Task is empty.")
            lesson_head["first_task"]["task"] = task.to_json()
            lesson_head["first_task"]["order"] = asdict(lesson_head["first_task"]["order"])
            logger.info(f"The lesson head is {lesson_head}")
            if not lesson_head["first_task"]["task"]:
                logger.warning("Task is empty after converting to dict.")
            return jsonify(lesson_head), 201
        else:
            lesson_gen = SpacedRepetitionLessonGenerator(user_id, db_manager)
            try:
                lesson_plan = lesson_gen.generate_lesson()
                logger.info(f"Generated lesson: {lesson_plan}")
            except Exception as e:
                logger.error(f"Failed to generate lesson. Error: {str(e)}")
                return jsonify({"error": "Failed to generate lesson."}), 500
            try:
                gen_lesson_head = db_manager.save_lesson_plan(user_id, lesson_plan)
            except:
                logger.error(f"Failed to save lesson. Error: {str(e)}")
                return jsonify({"error": "Failed to save the lesson."}), 500
            task = gen_lesson_head["first_task"]["task"]
            if not task:
                logger.warning("Task is empty.")
            gen_lesson_head["first_task"]["task"] = task.to_json()
            gen_lesson_head["first_task"]["order"] = asdict(gen_lesson_head["first_task"]["order"])
            if not gen_lesson_head["first_task"]["task"]:
                logger.warning("Task is empty after converting to dict.")
            logger.info(f"Generated lesson head: {gen_lesson_head}")
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
