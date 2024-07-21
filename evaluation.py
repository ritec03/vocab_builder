
from typing import Dict, List, Set
from data_structures import LexicalItem, Score
from task import Task

class HistoryEntry:
    """
    Represents an entry of task, user response, and its evaluation.
    Each history entry can record evaluations for multiple words tested in the task.
    """
    # TODO add type checks for inputs
    def __init__(self, task: Task, response: str, evaluation_result: Set[Score], correction=None):
        # TODO evaluation result should restrict to one score per word.
        self.task = task
        self.response = response
        self.evaluation_result = evaluation_result
        self.correction = correction

class Evaluation:
    """
    The object that keeps the data about a lesson, including each exercise completed,
    user input for answer, and evaluation of target words for the task.
    """
    def __init__(self):
        self.history: List[HistoryEntry] = []

    def add_entry(self, task: Task, response: str, evaluation_result: Set[Score], correction=None):
        entry = HistoryEntry(task, response, evaluation_result, correction)
        self.history.append(entry)

    def get_history_length(self) -> int:
        return len(self.history)
    
    def _get_last_history(self) -> HistoryEntry:
        return self.history[0]
    
    def get_last_task(self) -> Task:
        return self._get_last_history().task
    
    def get_last_scores(self) -> Set[Score]:
        """
        Returns final score for the last evaluation (history entry)

        :return: List[Score] a list of tuple of (word_id, score)
        """
        return self._get_last_history().evaluation_result
    
    def get_last_words_scored_below(self, theshold: float) -> Set[LexicalItem]:
        """
        Returns a set of lexical items that were scored below the threshold
        in the last evaluation history entry.
        """
        last_low_scored_word_ids = list(map(
                (lambda x: x.word_id),
                filter(
                    (lambda x: x.score < theshold),
                    self.get_last_scores()
                )
            )
        )
        words_to_retry = set(filter(
                (lambda x: x.id in last_low_scored_word_ids),
                self._get_last_history().task.learning_items
            )
        )
        return words_to_retry
    
    def get_final_scores_latest(self) -> Set[Score]:
        """
        Returns final scores for all practiced words by 
        getting the latest score for each word evaluated in history.
        """
        # iterate from the latest history
        # create a set of word_ids
        words: Set[int] = set()
        final_scores: Set[Score] = set()
        for history in reversed(self.history):
            for score in history.evaluation_result:
                if score.word_id not in words:
                    final_scores.add(score)
                    words.add(score.word_id)
        return final_scores
    
    def get_final_scores_highest(self) -> Set[Score]:
        """
        Returns final scores for all practiced words by 
        getting the highest score for each word evaluated in history.
        """
        all_scores: Set[Score] = set().union(*[h.evaluation_result for h in self.history])
        highest_scores_dict: Dict[int, Score] = {}
        for score in list(all_scores):
            if score.word_id not in highest_scores_dict or score.score > highest_scores_dict[score.word_id].score:
                highest_scores_dict[score.word_id] = score
    
        highest_scores = set(highest_scores_dict.values())
        return highest_scores

    def to_json(self):
        return {
            "history": [entry.__dict__ for entry in self.history]
        }

