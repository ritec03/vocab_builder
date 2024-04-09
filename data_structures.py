from ast import List, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, unique
from typing import Optional, Set

MAX_USER_NAME_LENGTH = 20
MAX_SCORE = 10
MIN_SCORE = 0
 
@unique
class TaskType(Enum):
    ONE_WAY_TRANSLATION = 1

@dataclass
class Score():
    """Represents score for a word."""
    word_id: int
    score: int

class LexicalItem():
    def __init__(self, item: str, pos: str, freq: int, id: int):
        self.item = item
        self.pos = pos
        self.freq = freq
        self.id = id
    
@dataclass
class TimePeriodCriterion:
    """Represents a criterion based on the time period during which tasks were last practiced."""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

@dataclass
class NumberOfWordsCriterion:
    """Represents a criterion based on the number of words involved in the tasks."""
    min_words: int = 1
    max_words: Optional[int] = None

@dataclass
class WordCriterion:
    """Represents a criterion to include specific words to practice.
    words: a set of word_ids
    """
    words: Set[int]

@dataclass
class TaskTypeCriterion:
    """Represents a criterion based on the type of task to choose."""
    task_types: Set[str]