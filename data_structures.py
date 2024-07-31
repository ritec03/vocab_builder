from dataclasses import dataclass
from datetime import datetime
from enum import Enum, unique
from typing import Final, TypedDict
from math import floor
from dotenv import load_dotenv
import os

MAX_USER_NAME_LENGTH = 20
MAX_SCORE = 10
MIN_SCORE = 0
EXERCISE_THRESHOLD = MAX_SCORE/2
NUM_WORDS_PER_LESSON = 5
NUM_NEW_WORDS_PER_LESSON = floor(NUM_WORDS_PER_LESSON/3)

load_dotenv()

TASKS_FILE_DIRECTORY: Final = "db_data/tasks.json"
TEMPLATED_FILE_DIRECTORY: Final = "db_data/templates.json"
DATABASE_FILE = os.getenv("DATABASE_FILE")
FLASK_INSTANCE_FOLDER = os.getenv("FLASK_INSTANCE_FOLDER")
OPEN_AI_KEY = os.getenv("OPEN_AI_KEY")

if not DATABASE_FILE:
    raise ValueError("Please set the DATABASE_FILE environment variable.")
if not FLASK_INSTANCE_FOLDER:
    raise ValueError("Please set the FLASK_INSTANCE_FOLDER environment variable.")
if not OPEN_AI_KEY:
    raise ValueError("Please set the OPEN_AI_KEY environment variable.")

FULL_DATABASE_PATH = os.path.join(FLASK_INSTANCE_FOLDER, DATABASE_FILE)

class FourChoiceAnswer(Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"

class CorrectionStrategy(Enum):
    HintStrategy = "HintStrategy"
    ExplanationStrategy = "ExplanationStrategy"
    EquivalentTaskStrategy = "EquivalentTaskStrategy"
    NoStrategy = "NoStrategy" # TODO add logic for no strategy and random or undefined strategy

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

@dataclass(frozen=True)
class LexicalItem:
    item: str
    pos: str
    freq: int
    id: int

    def to_json(self):
        return {
            'item': self.item,
            'pos': self.pos,
            'freq': self.freq,
            'id': self.id
        }
    
@dataclass(frozen=True)
class Resource():
    resource_id: int
    resource: str
    target_words: set[LexicalItem]

class UserScore(TypedDict):
    score: Score
    timestamp: datetime
    