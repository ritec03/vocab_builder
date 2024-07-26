from database_orm import (
    DatabaseManager,
    NextTask,
    NongeneratedNextTask,
    Order,
    OrderedTask,
)
from evaluation import HistoryEntry
from feedback_strategy import get_strategy_object


class LessonTask:
    def __init__(self, user_id: int, db_manager: DatabaseManager, lesson_id: int):
        self.user_id = user_id
        self.db_manager = db_manager
        self.lesson_id = lesson_id

    def evaluate_task(self, answer: str, task_id: int, order: Order) -> HistoryEntry:
        """
        Evaluates the task situated at the order within lesson plan
        according to its evaluation policy. Saves the evaluation for the task
        in lesson evaluation and updates lesson plan.
        Returns history entry representing evaluation of the task.
        Does not save results if encountered an exception.
        """
        # TODO check that the task at the order is the task I need
        task = self.db_manager.get_task_by_id(task_id)
        evaluation_result = task.evaluate_user_input(answer)
        history_entry = HistoryEntry(task, answer, evaluation_result)
        self.db_manager.save_evaluation_for_task(
            self.user_id, self.lesson_id, order, history_entry
        )
        return history_entry

    def get_next_task(self) -> OrderedTask | None:
        """
        Accesses the lesson and returns the next task in sequence.
        If the task is not yet defined, generates it and returns it.

        Returns:
            A dictionary with the following keys:
            - "order": The order of the task.
            - "task": The task itself.

            Returns None if there are no more tasks in the lesson.
        """
        next_task = self.db_manager.get_next_task_for_lesson(
            self.user_id, self.lesson_id
        )
        if not next_task:
            return None
        elif next_task["task"]:
            return {"order": next_task["order"], "task": next_task["task"]}
        elif next_task["eval"]:
            # by this point next_task is of type NongeneratedNextTask
            return self._get_next_correction_task(next_task)  # type: ignore
        else:
            raise Exception("An error occurred in get_next_task.")

    def _get_next_correction_task(
        self, next_task: NongeneratedNextTask
    ) -> OrderedTask | None:
        """
        Get the next correction task based on the evaluation of the previous task and error correction strategy.

        Args:
            next_task (NongeneratedNextTask): The next task information.

        Returns:
            OrderedTask | None: The next correction task if available, otherwise None.
        Raises:
            Exception: If task creation is not implemented for tasks that are not correction tasks.
        """
        task_eval = next_task["eval"]
        if next_task["order"].attempt <= 0:
            raise Exception(
                "Not implemented for task creation that are not correction tasks"
            )

        correction_strategy = next_task["error_correction"]
        # NOTE correction strategy is not none since it's NongeneratedNextTask
        strategy_obj = get_strategy_object(correction_strategy)(self.db_manager)
        if new_task := strategy_obj.choose_correction_task(task_eval):
            return {"order": next_task["order"], "task": new_task}
        else:
            return None
