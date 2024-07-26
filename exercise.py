from abc import ABC, abstractmethod
from datetime import datetime
from math import floor
from typing import Dict, List, Optional, Set, Tuple, Type, TypedDict, Union
from data_structures import EXERCISE_THRESHOLD, NUM_WORDS_PER_LESSON, CorrectionStrategy, LexicalItem, Score, UserScore
from database_orm import DatabaseManager, Order, OrderedTask, ValueDoesNotExistInDB
from evaluation import Evaluation, HistoryEntry
from task import Task
from task_retriever import TaskFactory
import logging

logger = logging.getLogger(__name__)

class ErrorCorrectionStrategy(ABC):
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    @abstractmethod
    def try_generate_task_in_advance(self, task_sequence: List[Union[Task, CorrectionStrategy]]) -> Union[Task, CorrectionStrategy]:
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
        
    def try_generate_task_in_advance(self, task_sequence: List[Union[Task, CorrectionStrategy]]) -> Union[Task, CorrectionStrategy]:
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
            new_task = TaskFactory(self.db_manager).get_task_for_word(last_task_learning_items, last_task.template)
            if new_task.id == last_task.id:
                raise Exception("Implement criteria not to choose the same task.")
            return new_task
        else:
            return CorrectionStrategy.EquivalentTaskStrategy

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
        new_task = TaskFactory(self.db_manager).get_task_for_word(words_to_retry, previous_task.template)
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
    
class LessonTask():
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
            self.user_id,
            self.lesson_id,
            order,
            history_entry
        )
        return history_entry

    def get_next_task(self) -> Optional[OrderedTask]:
        """
        Accesses the lesson and returns the next task in sequence.
        If the task is not yet defined, generates it and returns it.
        Returns:
            {
                "order": Order
                "task": Task
            }
            None if there are no more tasks in the lesson.
        """
        next_task = self.db_manager.get_next_task_for_lesson(self.user_id, self.lesson_id)
        if not next_task:
            return None
        elif next_task["task"]:
            return {
                "order": next_task["order"],
                "task": next_task["task"]
            }
        elif next_task["eval"]:
            task_eval = next_task["eval"]
            if next_task["order"].attempt > 0:
                correction_strategy = next_task["error_correction"]
                # NOTE correction strategy is not none since it's NongeneratedNextTask
                strategy_obj = get_strategy_object(correction_strategy)(self.db_manager) # type: ignore
                new_task = strategy_obj.choose_correction_task(task_eval)
                if not new_task:
                    return None
            else:
                raise Exception("Not implemented for task creation that are not correction tasks")
            
            return {
                "order": next_task["order"],
                "task": new_task
            }
        else:
            raise Exception("An error in get next task.")


class ExerciseSequence:
    """
    This class represents an exercise centered around a single task.
    An exercise may or may not require further exercises (corrections) depending
    on the user answer. 
    The criteria for passing or failing an exercise may be the word score.

    """
    def __init__(self, db_manager: DatabaseManager, task: Task, strategies_sequence: List[CorrectionStrategy]):
        """
        Initializes an exercise sequence with a specific task and a predefined sequence of error correction strategies.

        :param task: The initial task to be presented to the user.
        :param strategies_sequence: A list of strategy keys defining the sequence of corrections.
        :param max_attempts: Maximum number of attempts (including the initial attempt) before the sequence is terminated.
        """
        self.task = task
        self.strategies_sequence = strategies_sequence
        self.attempt_count = 0
        self.db_manager = db_manager

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
            strategy = get_strategy_object(strategy_key)(self.db_manager)
            if new_task := strategy.choose_correction_task(evaluation):
                evaluation = self.perform_task(new_task, evaluation)
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
        for _ in range(len(self.strategies_sequence)):
            evaluation = self.perform_run(evaluation)

        return evaluation

# need a method in lesson generator that takes in a set of learning items, relevant user data and returns a list of tasks
    # or a generator that generates tasks

class Lesson:
    def __init__(self, db_manager: DatabaseManager, user_id: int, words: Set[LexicalItem], lesson_plan: List[Tuple[Task, List[CorrectionStrategy]]]):
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
        self.db_manager = db_manager

    def perform_iteration(self, current_task_tuple: Tuple[Task, List[CorrectionStrategy]]):
        """
        Performs a single iteration of exercise sequence for a word from the set.
        """
        current_task, strategies_sequence = current_task_tuple
        self.exercise_sequence = ExerciseSequence(self.db_manager, current_task, strategies_sequence)
        self.evaluation_list.append(self.exercise_sequence.perform_sequence())

    def save_final_scores(self, lesson_id: int) -> None:
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
        self.db_manager.update_user_scores(self.user_id, final_scores, lesson_id)
        logger.info(final_scores)
    
    def save_evaluations(self) -> int:
        """
        Save the evaluations for the user into the database
        returns: int lesson id
        """
        lesson_id = self.db_manager.save_user_lesson_data(self.user_id, self.evaluation_list)
        return lesson_id

    def perform_lesson(self):
        # TODO change for web app so that it performs a certain step in the lesson
        """
        Performs tasks for the entire lesson plan in sequence,
        stores evaluations.
        """
        for task_tuple in self.lesson_plan:
            self.perform_iteration(task_tuple)
        lesson_id = self.save_evaluations()
        self.save_final_scores(lesson_id)

# create user class and think of user data
# create lesson generator that creates lesson material based on user data and words and available tasks.

"""
Strategoes for lesson generator.
Suppose that I have code that does spaced repetition.
Where would the definition of such code be and what responsibilities
would it have and what data would it need?

There is a need to choose:
1. what words to study in a session
2. waht tasks to choose for words
3. what correction strategies to employ
4. how to evaluate user input

Spaced repetition would choose the words that have
higher scores further in advance and those that have lower scores
sooner!
It does not say anything about tasks or correction strategies or evaluation.

However, it seems seems more or less clear that such logic should be 
configured at teh lesson generator level and not anywhere downstream.
* thus configuration should be determiend by the generator, but can
    be provided by an additional module.

"""

class SpacedRepetitionLessonGenerator():
    # TODO define the scope of learning algorithm module more vigorously
    # and define which parts are configurable by it (task generation, correction, etc.)
    """
    Generator lesson plan for the user.  Lesson plan is generator as follows: 
    * the user learning data is retrieved
    * the user's previous lesson data is retrieved. 
    Based on this information a lesson plan is created with tasks,
    error correction strategies and target words.

    Very simple space repetition-esque module to generate the next lesson
    given the user.

    Take the word scores
    Take the time the word was last practiced
    priority is given:
    * words with low scores practiced longest time ago
    * words with low scores practiced not so long ago
    * words with high scores practiced long ago
    * words with high scores practiced not so long ago

    Arrange the words by time practiced
    Go from the beginning (oldest practiced) and pick words with low scores.
    Then if there is space pick high scored words from the beginning.
        * OR add new words.

    Parameters:
    * determining low-high score
    * how many new words to learn
        * learn new words if after picking low scores, plus some high
        scores there is space.

    Question: how to choose tasks in this case? Do i choose old or new tasks?
        * task choice will also be a separate component that can be composed with
            a particular learning strategy.

    """
    score_threshold = EXERCISE_THRESHOLD
    words_per_lesson = NUM_WORDS_PER_LESSON
    num_words_per_lesson = NUM_WORDS_PER_LESSON

    def __init__(self, user_id: int, db_manager: DatabaseManager):
        self.user_id = user_id
        self.db_manager = db_manager

    def generate_lesson(self) -> List[Tuple[Task, List[Union[CorrectionStrategy, Task]]]]:
        """
        Returns the first tuple of the lesson plan.
        """
        logger.info("Generating lesson plan.")
        user_word_scores = self.db_manager.get_latest_word_score_for_user(self.user_id)
        logger.info(f"The latest word scores for the user are {user_word_scores}")
        # choose target words
        target_words = self.choose_target_words(user_word_scores)
        # generate lesson plan
        # TODO cannot generate lesson plan with 0 words
        lesson_plan = self.generate_lesson_plan(target_words)
        # return the first tuple in the lesson plan
        return lesson_plan
    
    def process_scores(
            self, 
            scores: Dict[int, UserScore]
        ) -> Tuple[Dict[datetime, Set], Dict[datetime, Set]]:

        timestamp_low_scores: Dict[datetime, Set] = {}
        timestamp_high_scores: Dict[datetime, Set] = {}

        for o in scores.values():
            score = o["score"]
            timestamp = o["timestamp"]
            score_set = timestamp_high_scores if score.score >= self.score_threshold else timestamp_low_scores
            if timestamp not in score_set:
                score_set[timestamp] = {score}
            else:
                score_set[timestamp].add(score)

        return timestamp_low_scores, timestamp_high_scores
    
    def get_scores_for_lesson(self, timestamp_scores: Dict[datetime, Set]) -> Tuple[List[Score], int, int]:
        len_scores = len(set().union(*timestamp_scores.values())) if timestamp_scores else 0
        scores_for_lesson: List[Score] = []
        if len_scores <= 0:
            return [], len_scores, self.num_words_per_lesson
        timestamps = list(timestamp_scores.keys())
        timestamps.sort()

        for timestamp in timestamps:
            for score in timestamp_scores[timestamp]:
                if len(scores_for_lesson) < self.num_words_per_lesson:
                    scores_for_lesson.append(score)
                else:
                    break

        leftover_count = self.num_words_per_lesson - len(scores_for_lesson)
        return scores_for_lesson, len_scores, leftover_count


    def choose_target_words(self, user_scores: Dict[int, UserScore]) -> Set[LexicalItem]:
        """
        Retrieves the latest score for each practiced word by the user.
        Arrange it by time practiced, then from the oldest words:
        * start choosing words that are below the score_threshold.
            * if the cutoff happens to happen at a timestamp under which multiple
                words fall, choose the appropriate number of words randomly from that set.
        * if there are words left in words_per_lesson count, from the end, start
            choosing words that are equal or above the threshold
            * if the cutoff happens to happen at a timestamp under which multiple
                words fall, choose the appropriate number of words randomly from that set.
        * calculate the amount of new words to learn using method and add appropriate number
            of new words.
        """
        timestamp_low_scores, timestamp_high_scores = self.process_scores(user_scores)
        scores_of_words_to_include_in_lesson: List[Score] = []
        low_scored_to_review, _, leftover_count = self.get_scores_for_lesson(timestamp_low_scores)
        high_scores_to_select, num_of_all_high_scores, _ = self.get_scores_for_lesson(timestamp_high_scores)

        num_new_words_to_learn = self.determine_num_of_new_words(leftover_count, num_of_all_high_scores)
        logger.info(f"The number of new words is {num_new_words_to_learn}")

        scores_of_words_to_include_in_lesson = low_scored_to_review + high_scores_to_select[:(self.words_per_lesson - len(low_scored_to_review) - num_new_words_to_learn)]        

        words_for_review = {
            self.db_manager.get_word_by_id(score.word_id)
            for score in scores_of_words_to_include_in_lesson
        }
        if not all(words_for_review):
            raise ValueDoesNotExistInDB("A word object was not found in the database in words for review.")
        logger.info("Words for review are %s", ", ".join(map(str, list(words_for_review))))

        # Retrieve new words if needed
        if num_new_words_to_learn > 0:
            new_words = self.db_manager.retrieve_words_for_lesson(self.user_id, num_new_words_to_learn)
        else:
            new_words: Set[LexicalItem] = set()

        logger.info("New words to learn are %s", ", ".join(map(str, list(new_words))))
        words_for_review = words_for_review.union(new_words)
        logger.info(words_for_review)

        # NOTE none of the elements of words_for_review are None since we check it with any()
        return words_for_review # type: ignore
    
    def determine_num_of_new_words(self, leftover_count: int, high_scores_count: int) -> int:
        # BUG bug when the number of learned words is 0 overall.
        """
        This function can be modified
        invariant: should return equal or less than leftover_count
        args:
            leftover_count: num of words remaining to be picked
                after all low score words were picked.
        """
        logger.info(f"Leftover count is {leftover_count} ")
        new_words_num = 0
        if leftover_count <= 1:
            new_words_num = 0
        
        # if less than quarter, choose half of leftover
        if leftover_count < floor(self.num_words_per_lesson/4):
            new_words_num = floor(leftover_count/2)
        # if less than half, choose third of leftover:
        elif leftover_count >= floor(self.num_words_per_lesson/4) and leftover_count < floor(self.num_words_per_lesson/2):
            new_words_num = floor(leftover_count/3)
        # else choose quarter
        else:
            new_words_num = floor(leftover_count/4)

        logger.info(f"The number of new words is {new_words_num}")
        return new_words_num if high_scores_count >= leftover_count - new_words_num else leftover_count - high_scores_count
            
    
    def generate_lesson_plan(self, words:Set[LexicalItem]) -> List[Tuple[Task, List[Union[CorrectionStrategy, Task]]]]:
        """
        Generates lesson plan for the user based on the targetwords.
        Returns the lesson plan which is a list of tuples, where each tuple
        has the task and a list of correction tasks or strategies if tasks are not available.
        """
        # TODO do not allow empty word sets as input
        # NOTE create a dummy plan by using one-word items only for now
        # NOTE for now create lesson task which partitions target words without overlaps, i.e.
        # a target word is targeted by one task only
        # TODO think about how to do it.
        task_factory = TaskFactory(self.db_manager)
        lesson_plan = []
        # TODO devise a strategy of choosing correction strategy.
        # TODO test api with correction strategies too.
        strategy_sequence = [
            # CorrectionStrategy.EquivalentTaskStrategy, 
            # CorrectionStrategy.EquivalentTaskStrategy, 
            # CorrectionStrategy.EquivalentTaskStrategy
        ]
        for word in list(words):
            task = task_factory.get_task_for_word({word})
            task_sequence: List[Union[Task, CorrectionStrategy]] = [task]
            # generate strategy sequence tasks
            for strategy in strategy_sequence:
                strategy_class = get_strategy_object(strategy)
                strategy_obj = strategy_class(self.db_manager)
                task_or_strategy = strategy_obj.try_generate_task_in_advance(task_sequence)
                task_sequence.append(task_or_strategy)

            lesson_plan.append((task, task_sequence[1:]))
        if not lesson_plan[0][0]: # NOTE maybe emits error
            logger.warning("Lesson plan is empty.")
        return lesson_plan

class Session():
    pass
