from abc import ABC, abstractmethod
from typing import List, Optional, Set, Tuple, Type
from data_structures import EXERCISE_THRESHOLD, NUM_NEW_WORDS_PER_LESSON, NUM_WORDS_PER_LESSON, CorrectionStrategy, LexicalItem, Score
from database_orm import DB, DatabaseManager
from evaluation import Evaluation
from task import Task
from task_generator import TaskFactory
from itertools import chain
import logging

logger = logging.getLogger(__name__)

class ErrorCorrectionStrategy(ABC):
    @abstractmethod
    def choose_correction_task(self, evaluation: Evaluation) -> Optional[Task]:
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
    # TODO there should be separate code that determines which target words failed
    def choose_correction_task(self, evaluation: Evaluation) -> Optional[Task]:
        """
        Based on the evaluation, chooses a task that is of the same type as the latest
        task to be re-tried.
        """
        # take last evaluation's task
        previous_task = evaluation.get_last_task()
        # get new target words
        words_to_retry = evaluation.get_last_words_scored_below(EXERCISE_THRESHOLD)
        if not words_to_retry:
            return None
        # produce equivalent task for same lexical items
        # make sure it's not the same task
        new_task = TaskFactory().get_task_for_word(words_to_retry, previous_task.template)
        if new_task.id == previous_task.id:
            raise Exception("Implement criteria not to choose the same task.")
        return new_task
    
class HintStrategy(ErrorCorrectionStrategy):
    def choose_correction_task(self, evaluation) -> Optional[Task]:
        # Logic to provide a hint for the same task
        pass

class ExplanationStrategy(ErrorCorrectionStrategy):
    def choose_correction_task(self, evaluation) -> Optional[Task]:
        # Logic to provide an explanation for the correct answer
        pass

def get_strategy_object(strategy_name: CorrectionStrategy) -> Type[ErrorCorrectionStrategy]:
    if strategy_name == CorrectionStrategy.HintStrategy:
        return HintStrategy
    elif strategy_name == CorrectionStrategy.EquivalentTaskStrategy:
        return EquivalentTaskStrategy
    elif strategy_name == CorrectionStrategy.ExplanationStrategy:
        return ExplanationStrategy
    else:
        raise ValueError("Invalid correction strategy name ", strategy_name)

class ExerciseSequence:
    """
    This class represents an exercise centered around a single task.
    An exercise may or may not require further exercises (corrections) depending
    on the user answer. 
    The criteria for passing or failing an exercise may be the word score.

    """
    def __init__(self, task: Task, strategies_sequence: List[CorrectionStrategy]):
        """
        Initializes an exercise sequence with a specific task and a predefined sequence of error correction strategies.

        :param task: The initial task to be presented to the user.
        :param strategies_sequence: A list of strategy keys defining the sequence of corrections.
        :param max_attempts: Maximum number of attempts (including the initial attempt) before the sequence is terminated.
        """
        self.task = task
        self.strategies_sequence = strategies_sequence
        self.attempt_count = 0

    def perform_run(self, evaluation: Evaluation) -> Evaluation:
        """
        Execute a step of the exercise sequence if there are any left, if not, just return the current evaluation
        manager object.

        :param user_response: The user's initial response to the task.
        :param evaluation: The EvaluationManager instance tracking the session's evaluation history.

        :reutrn: The evaluation result as a new and updated object.
        """
        if self.attempt_count == 0:
            evaluation = self.perform_task(self.task, evaluation)
        elif self.attempt_count > 0 and self.attempt_count < len(self.strategies_sequence):
            strategy_key = self.strategies_sequence[self.attempt_count]
            strategy = get_strategy_object(strategy_key)()
            new_task = strategy.choose_correction_task(evaluation)
            if new_task:
                evaluation = self.perform_task(new_task, evaluation)
            else:
                pass
        elif self.attempt_count >= len(self.strategies_sequence):
            return evaluation

        self.attempt_count += 1
        return evaluation
    
    def perform_task(self, task: Task, evaluation: Evaluation) -> Evaluation:
        """
        Records user response for the task, runs evaluations and appends evaluation
        to the evaluation object.
        """
        user_response = input(task.produce_task())
        evaluation_result = task.evaluate_user_input(user_response)
        evaluation.add_entry(task, user_response, evaluation_result)
        return evaluation
    
    def perform_sequence(self) -> Evaluation:
        """
        Performs entire sequence of runs based on number of error correction
        strategies and returns final evaluation.
        Implements stop criterion - score thershold?
        """
        evaluation = Evaluation()
        evaluation = self.perform_run(evaluation)
        for i in range(len(self.strategies_sequence)):
            evaluation = self.perform_run(evaluation)

        return evaluation

# need a method in lesson generator that takes in a set of learning items, relevant user data and returns a list of tasks
    # or a generator that generates tasks

class Lesson:
    def __init__(self, user_id: int, words: Set[LexicalItem], lesson_plan: List[Tuple[Task, List[CorrectionStrategy]]]):
        """
        Initialize a lesson with a set of words to be learned, each associated with a sequence of error correction strategies.

        :param words: A set of LexicalItem objects representing the words to be learned.
        :param lesson_plan: A list of tuples of tasks and the corresponding error correction
            strategies
        """
        # TODO add check that word ids in lesson plan are one to one to words set
        self.current_task_index = 0
        self.lesson_plan = lesson_plan
        self.practiced_words = {}  # Maps word ID to Evaluation objects.
        self.evaluation_list: List[Evaluation] = []
        self.user_id = user_id

    def perform_iteration(self, current_task_tuple: Tuple[Task, List[CorrectionStrategy]]):
        """
        Performs a single iteration of exercise sequence for a word from the set.
        """
        current_task, strategies_sequence = current_task_tuple
        self.exercise_sequence = ExerciseSequence(current_task, strategies_sequence)
        self.evaluation_list.append(self.exercise_sequence.perform_sequence())

    def save_final_scores(self) -> None:
        """
        Save final scores of each evaluation in the evaluation list into
        the database.

        Assumes that a target word occurs only in one evaluation.
        """
        # get evaluation scores
        # NOTE assuming that evaluations contain non-overlapping partition of target words
        final_eval_scores : List[Set[Score]] = [eval.get_final_scores_highest() for eval in self.evaluation_list]
        final_scores = set()
        for s in final_eval_scores:
            final_scores = final_scores.union(s)
        DB.update_user_scores(self.user_id, final_scores)
        logger.info(final_scores)
    
    def save_evaluations(self) -> None:
        """
        Save the evaluations for the user into the database
        """
        DB.save_user_lesson_data(self.user_id, self.evaluation_list)

    def perform_lesson(self): 
        """
        Performs tasks for the entire lesson plan in sequence,
        stores evaluations.
        """
        for task_tuple in self.lesson_plan:
            self.perform_iteration(task_tuple)
        self.save_final_scores()
        self.save_evaluations()

# create user class and think of user data
# create lesson generator that creates lesson material based on user data and words and available tasks.

class LessonGenerator():
    """
    Generator lesson plan for the user.  Lesson plan is generator as follows: 
    * the user learning data is retrieved
    * the user's previous lesson data is retrieved. 
    Based on this information a lesson plan is created with tasks,
    error correction strategies and target words.
    """
    def __init__(self, user_id: int):
        self.user_id = user_id

    def generate_lesson(self) -> Lesson:
        # NOTE later also take into account user lesson history
        # retrieve user learning data
        # retrieve user lesson evaluation history
        user_word_scores = DB.retrieve_user_scores(self.user_id)
        logger.info(user_word_scores)
        # choose target words
        target_words = self.choose_target_words(user_word_scores)
        # generate lesson plan
        lesson_plan = self.generate_lesson_plan(target_words)
        # return lesson
        return Lesson(self.user_id, target_words, lesson_plan)

    def choose_target_words(self, user_scores: Set[Score]) -> Set[LexicalItem]:
        # TODO also take into account time last practiced later
        # Choose 10 lowest scoring words or all if there are fewer than 10
        # TODO think how to randomize the choice of lowest scores.
        lowest_scores = sorted(list(user_scores), key=lambda x: x.score)[:NUM_NEW_WORDS_PER_LESSON]
        lowest_scored_word_ids = {score.word_id for score in lowest_scores}
        lowest_words = {DB.get_word_by_id(word_id) for word_id in lowest_scored_word_ids}

        # Calculate how many new words are needed
        num_new_words_needed = NUM_WORDS_PER_LESSON - len(lowest_words)

        # Retrieve new words if needed
        if num_new_words_needed > 0:
            new_words = DB.retrieve_words_for_lesson(self.user_id, num_new_words_needed)
        else:
            new_words = set()

        # Combine lowest scoring words and new words
        target_words = lowest_words.union(new_words)

        return target_words
    
    def generate_lesson_plan(self, words:Set[LexicalItem]) -> List[Tuple[Task, List[str]]]:
        # NOTE create a dummy plan by using one-word items only for now and no error correction
        # NOTE for now create lesson task which partitions target words without overlaps, i.e.
        # a target word is targeted by one task only
        # TODO think about how to do it.
        task_factory = TaskFactory()
        lesson_plan = []
        strategy_sequence = [
            CorrectionStrategy.EquivalentTaskStrategy, 
            CorrectionStrategy.EquivalentTaskStrategy, 
            CorrectionStrategy.EquivalentTaskStrategy
        ]
        for word in list(words):
            task = task_factory.get_task_for_word({word})
            lesson_plan.append((task, strategy_sequence))
        return lesson_plan

class Session():
    pass