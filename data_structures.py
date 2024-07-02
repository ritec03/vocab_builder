from dataclasses import dataclass
from datetime import datetime
from enum import Enum, unique
from typing import Optional, Set
from math import floor

MAX_USER_NAME_LENGTH = 20
MAX_SCORE = 10
MIN_SCORE = 0
EXERCISE_THRESHOLD = MAX_SCORE/2
NUM_WORDS_PER_LESSON = 4
NUM_NEW_WORDS_PER_LESSON = floor(NUM_WORDS_PER_LESSON/3)

class FourChoiceAnswer(Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"

class CorrectionStrategy(Enum):
    HintStrategy = "HintStrategy"
    ExplanationStrategy = "ExplanationStrategy"
    EquivalentTaskStrategy = "EquivalentTaskStrategy"

@unique
class Language(Enum):
    ENGLISH = 1
    GERMAN = 2

@unique
class TaskType(Enum):
    ONE_WAY_TRANSLATION = 1
    FOUR_CHOICE = 2

@dataclass(frozen=True)
class User():
    id: int
    user_name: str

# need frozen to be able to use with sets and to ensure that it does not change
@dataclass(frozen=True)
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

    def __eq__(self, other):
        if isinstance(other, LexicalItem):
            return (
                self.item == other.item 
                and self.pos == other.pos 
                and self.freq == other.freq 
                and self.id == other.id
            )
        return False

    def __hash__(self):
        return hash((self.item, self.pos, self.freq, self.id))

@dataclass
class Resource():
    resource_id: int
    resource: str
    target_words: Set[LexicalItem]
    
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
