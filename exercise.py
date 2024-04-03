from abc import ABC, abstractmethod
import copy
from typing import List, Set, Tuple, Dict

from database import Score, save_user_lesson_data

class LexicalItem():
    def __init__(self, item: str, pos: str, freq: int, id: int):
        self.item = item
        self.pos = pos
        self.freq = freq
        self.id = id

class Task(ABC):
    def __init__(self, template: str, resources: List[str], learning_items: Set[LexicalItem]):
        """
        Initialize a new task with a template and resources.
        
        :param template: A string template for the task, where placeholders are to be filled with resources.
        :param resources: A dictionary of resources (e.g., words, sentences) to fill in the template.
        :param learning_items: a set of words to be learned
        """
        self.template = template
        self.resources = resources
        self.learning_items = learning_items
        self.correctAnswer = None  # This should be set by subclasses where the task is fully defined.

    @abstractmethod
    def produce_task(self) -> str:
        """
        Produces the task by combining the template with resources. This should be implemented by subclasses to
        fill the template with appropriate resources, creating a specific instance of the task.
        
        :return: The complete task as a string.
        """
        pass

    @abstractmethod
    def evaluate_user_input(self, user_input) -> List[Tuple[int, int]]:
        """
        :return: list of tuples of word id and score
        """
        pass

    def get_evaluation(self, user_input: str, evaluation: Evaluation) -> Evaluation:
        """
        Evaluates the user's input against the correct answer and 
        creates a new evaluation manager object with the latest evaluation added to it.
        
        :param user_input: The user's input as a response to the task.
        :param evaluation: The EvaluationManager instance tracking the session's evaluation history.
        :return: The evaluation result as a new and updated object.
        """
        evaluation_result = self.evaluate_user_input()
        new_evaluation = copy.deepcopy(evaluation)
        new_evaluation.add_entry(self, user_input, evaluation_result)
        return new_evaluation

class HistoryEntry:
    def __init__(self, task: Task, response: str, evaluation_result: List[Tuple[int, int]], correction=None):
        # evaluation result is a list of tuples of word_id and score (multiple words can be evaluated
        # in one evaluation)
        self.task = task
        self.response = response
        self.evaluation_result = evaluation_result
        self.correction = correction

class Evaluation:
    def __init__(self):
        self.history = []

    def add_entry(self, task: Task, response: str, evaluation_result: List[Tuple[int, int]], correction=None):
        entry = HistoryEntry(task, response, evaluation_result, correction)
        self.history.append(entry)

    def get_history(self):
        return self.history
    
    def get_final_score(self) -> List[Tuple[int, int]]:
        """
        Returns final score for the evaluation,
        which is the evaluation result of the last history entry

        :return: List[Tuple[int, int]] a list of tuple of (word_id, score)
        """
        raise NotImplementedError()

class ErrorCorrectionStrategy(ABC):
    @abstractmethod
    def apply_correction(self, task: Task, user_response: str, evaluation: Evaluation) -> Evaluation:
        """
        Applies a correction strategy to the task based on the user's response and the evaluation manager.
        
        :param task: The task object on which the user responded.
        :param user_response: The user's response to the task.
        :param evaluation: The evaluation manager object storing evaluation history.

        :return: The evaluation result as a new and updated object.
        """
        pass

class HintStrategy(ErrorCorrectionStrategy):
    def apply_correction(self, task, user_response, evaluation) -> Evaluation:
        # Logic to provide a hint for the same task
        pass

class ExplanationStrategy(ErrorCorrectionStrategy):
    def apply_correction(self, task, user_response, evaluation) -> Evaluation:
        # Logic to provide an explanation for the correct answer
        pass

class ErrorCorrectionHandler:
    def __init__(self, strategy: ErrorCorrectionStrategy):
        self.strategy = strategy

    def execute_correction(self, task: Task, evaluation: Evaluation) -> Evaluation:
        """
        Applies the correction strategy to the task.

        :param task: The task object.
        :param evaluation: The EvaluationManager object.
        """
        new_evaluation = self.strategy.apply_correction(task, evaluation)
        return new_evaluation

class ExerciseSequence:
    def __init__(self, task: Task, strategies_sequence: List[str]):
        """
        Initializes an exercise sequence with a specific task and a predefined sequence of error correction strategies.

        :param task: The initial task to be presented to the user.
        :param strategies_sequence: A list of strategy keys (e.g., ['hint', 'explanation']) defining the sequence of corrections.
        :param max_attempts: Maximum number of attempts (including the initial attempt) before the sequence is terminated.
        """
        self.task = task
        self.strategies_sequence = strategies_sequence
        self.attempt_count = 0

    def get_strategy_object(strategy_key: str) -> Task:
        """
        Factory method to get an instance of ErrorCorrectionStrategy based on a key.

        :param strategy_key: The key identifying the strategy.
        :return: An instance of a subclass of ErrorCorrectionStrategy.
        """
        strategy_map = {
            'hint': HintStrategy,
            'explanation': ExplanationStrategy,
            # Additional strategies can be added here.
        }
        strategy_class = strategy_map.get(strategy_key)
        if strategy_class:
            return strategy_class()
        raise ValueError(f"Unknown strategy key: {strategy_key}")

    def perform_run(self, evaluation: Evaluation) -> Evaluation:
        """
        Execute a step of the exercise sequence if there are any left, if not, just return the current evaluation
        manager object.

        :param user_response: The user's initial response to the task.
        :param evaluation: The EvaluationManager instance tracking the session's evaluation history.

        :reutrn: The evaluation result as a new and updated object.
        """
        if self.attempt_count == len(self.strategies_sequence):
            return evaluation
        elif self.attempt_count == 0:
            # NOTE get user response here - very simple for now
            user_response = input(self.task.produce_task())
            evaluation = self.task.get_evaluation(user_response, evaluation)
        elif self.attempt_count > 0:
            strategy_key = self.strategies_sequence[self.attempt_count]
            strategy = self.get_strategy_object(strategy_key)
            error_correction_handler = ErrorCorrectionHandler(strategy)
            evaluation = error_correction_handler.execute_correction(self.task, evaluation)

        self.attempt_count += 1
        return evaluation
    
    def perform_sequence(self) -> Evaluation:
        """
        Performs entire sequence of runs based on number of error correction
        strategies and returns final evaluation.
        Implements stop criterion - score thershold?
        """
        pass

# need a method in lesson generator that takes in a set of learning items, relevant user data and returns a list of tasks
    # or a generator that generates tasks 

class Lesson:
    def __init__(self, words: Set[LexicalItem], lesson_plan: List[Tuple[Task, List[str]]]):
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

    def perform_iteration(self, current_task_tuple: Tuple[Task, List[str]]):
        """
        Performs a single iteration of exercise sequence for a word from the set.
        """
        current_task, strategies_sequence = current_task_tuple
        self.current_evaluation = Evaluation()
        self.exercise_sequence = ExerciseSequence(current_task, strategies_sequence)
        self.evaluation_list.append(self.exercise_sequence.perform_sequence(self.current_evaluation))

    def save_final_scores(self) -> None:
        """
        Save final scores of each evaluation in the evaluation list into
        the database.
        """
        # TODO what to do when there is more thna one score for a word?
        raise NotImplementedError()
    
    def save_evaluations(self) -> None:
        """
        Save the evaluations for the user into the database
        """
        raise NotImplementedError()

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
        # retrieve user learning data
        # retrieve user lesson evaluation history
        user_word_scores, user_lesson_history = self.retrieve_user_data()
        # choose target words
        target_words = self.choose_target_words(user_word_scores)
        # generate lesson plan
        lesson_plan = self.generate_lesson_plan(target_words, user_lesson_history)
        # return lesson
        return Lesson(target_words, lesson_plan)
    
    def retrieve_user_data() -> Tuple[List[Score], List[Evaluation]]:
        raise NotImplementedError()
    
    def choose_target_words(self, user_scores: List[Score]) -> Set[LexicalItem]:
        raise NotImplementedError()

    def generate_lesson_plan(self, words:Set[LexicalItem], user_lesson_history: List[Evaluation]) -> List[Tuple[Task, List[str]]]:
        raise NotImplementedError()

    