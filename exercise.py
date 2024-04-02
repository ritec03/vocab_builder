"""
Exercise types
* create corresponding abstraction
Evaluation/error correction
* defines paths for error correction
* defines evaluation
Exercise
* defines exercise for a word
* uses corresponding exercise type
* uses corresponding user correction strategy
"""


"""
Exercise class will define exercise instances for a lesson.
Exercise instance will be focused on a set of words (from one to several)
and will apply an exercise type to the set of words thus creating an
exercise. The exercise class will also 


Exercise will focus on words "verschwinden".

the exercise type will be a multiple choice question that will contain
a sentence in german and the underlied word "verschwinden" and several
choices of english words among which the user is asked to select the word
that best matches the word in german.

As soon as the user chooses the answer, the exercise type provides evaluation
strategy for correctness, which in this case is simple and is correct or incorrect.
If the answer is incorrect, a correction strategy is chosen. 

Who chooses exercise type for a particular set of words?
* exercise types will have a certain difficulty and depending on that
they will be assigned.

So there will be exercise, and correction scheme. 
"""
from abc import ABC, abstractmethod
import copy
from typing import List

class Task(ABC):
    def __init__(self, template, resources):
        """
        Initialize a new task with a template and resources.
        
        :param template: A string template for the task, where placeholders are to be filled with resources.
        :param resources: A dictionary of resources (e.g., words, sentences) to fill in the template.
        """
        self.template = template
        self.resources = resources
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
    def evaluate_user_input(self, user_input) -> int:
        pass

    def get_evaluation(self, user_input: str, evaluation: Evaluation) -> Evaluation:
        """
        Evaluates the user's input against the correct answer and 
        creates a new evaluation manager object with the latest evaluation added to it.
        
        :param user_input: The user's input as a response to the task.
        :param evaluation: The EvaluationManager instance tracking the session's evaluation history.
        :return: The evaluation result as a new and updated object.
        """
        evaluation_result: int = self.evaluate_user_input()
        new_evaluation = copy.deepcopy(evaluation)
        new_evaluation.add_entry(self, user_input, evaluation_result)
        return new_evaluation

class HistoryEntry:
    def __init__(self, task: Task, response: str, evaluation_result: int, correction=None):
        self.task = task
        self.response = response
        self.evaluation_result = evaluation_result
        self.correction = correction

class Evaluation:
    def __init__(self):
        self.history = []

    def add_entry(self, task: Task, response: str, evaluation_result: int, correction=None):
        entry = HistoryEntry(task, response, evaluation_result, correction)
        self.history.append(entry)

    def get_history(self):
        return self.history

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

    def execute_correction(self, task: Task, user_response: str, evaluation: Evaluation) -> Evaluation:
        """
        Applies the correction strategy to the task.

        :param task: The task object.
        :param user_response: The user's response to the task.
        :param evaluation: The EvaluationManager object.
        """
        new_evaluation = self.strategy.apply_correction(task, user_response, evaluation)
        return new_evaluation

class ExerciseSequence:
    def __init__(self, task: Task, strategies_sequence: List[str], max_attempts:int=3):
        """
        Initializes an exercise sequence with a specific task and a predefined sequence of error correction strategies.

        :param task: The initial task to be presented to the user.
        :param strategies_sequence: A list of strategy keys (e.g., ['hint', 'explanation']) defining the sequence of corrections.
        :param max_attempts: Maximum number of attempts (including the initial attempt) before the sequence is terminated.
        """
        self.task = task
        self.strategies_sequence = strategies_sequence
        self.max_attempts = max_attempts
        self.attempt_count = 0

    def get_strategy_object(task_key: str) -> Task:
        raise NotImplementedError()

    def perform_run(self, user_response:str, evaluation: Evaluation) -> Evaluation:
        """
        Execute a step of the exercise sequence if there are any left, if not, just return the current evaluation
        manager object.

        :param user_response: The user's initial response to the task.
        :param evaluation: The EvaluationManager instance tracking the session's evaluation history.

        :reutrn: The evaluation result as a new and updated object.
        """
        if self.attempt_count == self.max_attempts:
            return evaluation
        elif self.attempt_count == 0:
            evaluation = self.task.get_evaluation(user_response, evaluation)
        elif self.attempt_count > 0:
            strategy_key = self.strategies_sequence[self.attempt_count]
            strategy = self.get_strategy_object(strategy_key)
            error_correction_handler = ErrorCorrectionHandler(strategy)
            evaluation = error_correction_handler.execute_correction(self.task, user_response, evaluation)

        self.attempt_count += 1
        return evaluation
