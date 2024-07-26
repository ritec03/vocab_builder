from abc import ABC, abstractmethod
from data_structures import EXERCISE_THRESHOLD, CorrectionStrategy, LexicalItem
from database_orm import DatabaseManager
from evaluation import Evaluation
from task import Task
from task_retriever import TaskFactory
import logging

logger = logging.getLogger(__name__)


class ErrorCorrectionStrategy(ABC):
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    @abstractmethod
    def try_generate_task_in_advance(
        self, task_sequence: list[Task | CorrectionStrategy]
    ) -> Task | CorrectionStrategy:
        """
        Try to generate a correction task in advance and return it.
        If it is not possible, return CorrectionStrategy.
        A task can be created in advance if it does not require anything additional (like user input,
        or if it only tests for one lexical item, or if some tasks are just stored and can be used
        right away).

        Params:
            task_sequence: a sequence of original task plus error correction tasks that
                were created in advance
        """
        pass

    @abstractmethod
    def choose_correction_task(self, evaluation: Evaluation) -> Task | None:
        """
        Applies a correction strategy to the task based on the user's response and the evaluation manager.

        :param task: The task object on which the user responded.
        :param user_response: The user's response to the task.
        :param evaluation: The evaluation manager object storing evaluation history.

        :return: The evaluation result as a new and updated object.
        """
        pass


"""
Strategy where a different task is given
Strategy where answer is revealed with blanks of words (target words) or with letters missing
Strategy where some words are translated

Composing error correction? Like get with blank words first, but then add some letters back.

somehow the error correction tasks should also be saved and linked to their tasks?
Error correction templates?

The strategy will apply an error correction template

For now just focus on something that takes into account the previous task (correction) only

TODO make error correction strategy return correction task and let exercise sequence to evaluate
"""


class EquivalentTaskStrategy(ErrorCorrectionStrategy):
    """
    This strategy produces a different task with the same template
    for the target words.
    """

    def try_generate_task_in_advance(
        self, task_sequence: list[Task | CorrectionStrategy]
    ) -> Task | CorrectionStrategy:
        """
        Try to generate a correction task in advance and return it.
        If it is not possible, return CorrectionStrategy.
        A task can be created in advance if it does not require anything additional (like user input,
        or if it only tests for one lexical item, or if some tasks are just stored and can be used
        right away).

        Params:
            task_sequence: a sequence of original task plus error correction tasks that
                were created in advance
        """
        # if the last task has one lexical item to learn, then generate a task
        last_task = task_sequence[-1]
        if isinstance(last_task, CorrectionStrategy):
            return CorrectionStrategy.EquivalentTaskStrategy
        last_task_learning_items = last_task.learning_items
        if len(last_task_learning_items) == 1:
            return self.get_task_for_words(last_task_learning_items, last_task)
        else:
            return CorrectionStrategy.EquivalentTaskStrategy

    # TODO there should be separate code that determines which target words failed
    def choose_correction_task(self, evaluation: Evaluation) -> Task | None:
        # sourcery skip: use-named-expression
        """
        Based on the evaluation, chooses a task that is of the same type as the latest
        task to be re-tried.

        Args:
            evaluation (Evaluation): The evaluation object containing the previous tasks and words.

        Returns:
            Task | None: The chosen task to be re-tried, or None if no words need to be retried.
        """
        # take last evaluation's task
        previous_task = evaluation.get_last_task()
        # get new target words
        words_to_retry = evaluation.get_last_words_scored_below(EXERCISE_THRESHOLD)
        if words_to_retry:
            return self.get_task_for_words(words_to_retry, previous_task)
        else:
            return None

    # TODO Rename this here and in `try_generate_task_in_advance` and `choose_correction_task`
    def get_task_for_words(self, target_words: set[LexicalItem], task: Task) -> Task:
        """
        Get task for target words that is different from the given task.

        Args:
            target_words (set[LexicalItem]): A set of target words for which to get a task.
            task (Task): The given task.

        Returns:
            Task: A new task that is different from the given task.

        Raises:
            Exception: If the new task is the same as the given task.
        """
        new_task = TaskFactory(self.db_manager).get_task_for_word(
            target_words, task.template
        )
        if new_task.id == task.id:
            raise Exception("Implement criteria not to choose the same task.")
        return new_task


class HintStrategy(ErrorCorrectionStrategy):
    def choose_correction_task(self, evaluation) -> Task | None:
        # Logic to provide a hint for the same task
        pass


class ExplanationStrategy(ErrorCorrectionStrategy):
    def choose_correction_task(self, evaluation) -> Task | None:
        # Logic to provide an explanation for the correct answer
        pass


def get_strategy_object(
    strategy_name: CorrectionStrategy,
) -> type[ErrorCorrectionStrategy]:
    if strategy_name == CorrectionStrategy.HintStrategy:
        return HintStrategy
    elif strategy_name == CorrectionStrategy.EquivalentTaskStrategy:
        return EquivalentTaskStrategy
    elif strategy_name == CorrectionStrategy.ExplanationStrategy:
        return ExplanationStrategy
    else:
        raise ValueError("Invalid correction strategy name ", strategy_name)
