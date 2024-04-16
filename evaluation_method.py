from abc import ABC, abstractmethod
from data_structures import MAX_SCORE, MIN_SCORE, LexicalItem, Score
from llm_chains import invoke_evaluation_chain
from typing import Dict, Set, List

class EvaluationMethod(ABC):
    """
    Class that defines an evaluation strategy
    It operates with gold standard answer, user answer and a context (such as task).
    Context is defined by a class that uses the evaluation (such as by a concrete task class).
    """
    def __init__(self, context: Dict[str, str] = None):
        self.context = context

    @abstractmethod
    def evaluate(self, gold_standard:str, user_answer: str, target_words: Set[LexicalItem]) -> List[Score]:
        """
        Method that evaluates user answer against the gold standard with
        consideration of the context.
        """
        pass

class ExactMatchingEvaluation(EvaluationMethod):
    """
    Evaluation method for exact string matching.
    Case insensitive.
    """
    def evaluate(self, gold_standard:str, user_answer: str, target_words: Set[LexicalItem]) -> List[Score]:
        """
        Evaluate user answer against gold standard using exact string matching.
        """
        if gold_standard.lower().strip() == user_answer.lower().strip():
            return [Score(word.id, MAX_SCORE) for word in target_words]
        else:
            return [Score(word.id, MIN_SCORE) for word in target_words]
        
class AIEvaluation(EvaluationMethod):
    """
    Context should contain "task" field with stringified task.
    """
    def __init__(self, context: Dict[str, str]):
        self.context = context

    def evaluate(self, gold_standard:str, user_answer: str, target_words: Set[LexicalItem]) -> List[Score]:
        """
        Evaluation method that uses LLM-based evaluation of human input
        against the gold standard and context of the task.
        """
        # invoke evaluation chain.
        output = invoke_evaluation_chain(self.context["task"], gold_standard, user_answer, target_words)
        print(output)
        # Check that output is a dictionary that contains all words from target words as keys and
        # that all values are integers.
        if not isinstance(output, dict):
            raise ValueError("Output is not a dictionary")
        
        for word in target_words:
            if word.item not in output:
                raise ValueError(f"Output does not contain score for word: {word.item}")
            if not isinstance(output[word.item], int):
                raise ValueError(f"Score for word {word.item} is not an integer")
        
        # Convert the output into the final output form of List[Score]
        scores = [Score(word_id=word.id, score=output[word.item]) for word in target_words]
        return scores
