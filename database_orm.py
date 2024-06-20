
from datetime import datetime
from typing import List, Optional, Tuple
import pandas as pd
from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy import Enum
from sqlalchemy import func
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import JSON
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine
from data_structures import LexicalItem, TaskType
from sqlalchemy.orm import Session
from sqlalchemy import select

class Base(DeclarativeBase):
    pass

class UserDBObj(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_name: Mapped[str] = mapped_column(unique=True)
    # create_date: Mapped[datetime] = mapped_column(insert_default=func.now())

class WordDBObj(Base):
    __tablename__ = "words"

    id: Mapped[int] = mapped_column(primary_key=True)
    word: Mapped[str]
    pos: Mapped[str]
    freq: Mapped[int]
    __table_args__ = (UniqueConstraint('word', 'pos'),)

class LearningDataDBObj(Base):
    __tablename__ = "learning_data"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id = mapped_column(ForeignKey("users.id"))
    word_id = mapped_column(ForeignKey("words.id"))
    score: Mapped[int] = mapped_column(Integer, CheckConstraint("score >= 0 AND score <= 10"), unique=False)

class TemplateDBObj(Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    # NOTE sqlalchemy enums use enam names not values
    task_type: Mapped[str] = mapped_column(Enum(TaskType, validate_strings=True))
    template: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str]
    examples: Mapped[str] = mapped_column(JSON) 
    starting_language: Mapped[str]
    target_language: Mapped[str]

class TemplateParameterDBObj(Base):
    __tablename__ = "template_parameters"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=False)
    description: Mapped[str]
    template_id = mapped_column(ForeignKey("templates.id"))
    __table_args__ = (UniqueConstraint("template_id", "name"),)

class TaskDBObj(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id = mapped_column(ForeignKey("templates.id"))
    answer: Mapped[str]

class TaskTargetWordDBObj(Base):
    __tablename__ = "task_target_words"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id = mapped_column(Integer, ForeignKey("tasks.id"))
    word_id = mapped_column(Integer, ForeignKey("words.id"))

class ResourceDBObj(Base):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    resource_text: Mapped[str]

class TaskResourceDBObj(Base):
    __tablename__ = "task_resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id = mapped_column(Integer, ForeignKey("tasks.id"))
    resource_id = mapped_column(Integer, ForeignKey("resources.id"))
    parameter_id = mapped_column(Integer, ForeignKey("template_parameters.id"))
    # TODO add constraint not to include parameters that are not parameters for that template
    __table_args__ = (UniqueConstraint("parameter_id", "task_id"),)

class ResourceWordDBObj(Base):
    __tablename__ = "resource_words"

    resource_id = mapped_column(Integer, ForeignKey("resources.id"), primary_key=True)
    word_id = mapped_column(Integer, ForeignKey("words.id"), primary_key=True)
    # each word appears in a resource once only
    __table_args__ = (UniqueConstraint('resource_id', 'word_id'),)

from sqlalchemy import TIMESTAMP

class UserLessonDBObj(Base):
    __tablename__ = "user_lessons"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"))
    timestamp: Mapped[datetime] = mapped_column(default=func.now(), server_default=func.now(), type_=TIMESTAMP)

class EvaluationDBObj(Base):
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id = mapped_column(Integer, ForeignKey("user_lessons.id"))
    sequence_number: Mapped[int] = mapped_column()
    # Ensures sequence numbers are unique within each lesson
    __table_args__ = (UniqueConstraint('lesson_id', 'sequence_number'),)

class HistoryEntrieDBObj(Base):
    __tablename__ = "history_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_id = mapped_column(Integer, ForeignKey("evaluations.id"))
    sequence_number: Mapped[int] = mapped_column()
    task_id = mapped_column(Integer, ForeignKey("tasks.id"))
    response: Mapped[str]
    __table_args__ = (UniqueConstraint('evaluation_id', 'sequence_number'),)

class EntryScoreDBObj(Base):
    __tablename__ = "entry_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    history_entry_id = mapped_column(Integer, ForeignKey("history_entries.id"))
    word_id = mapped_column(Integer, ForeignKey("words.id"))
    score: Mapped[int] = mapped_column(Integer, CheckConstraint("score >= 0 AND score <= 10"))
    # Ensuring one score per word per history entry
    __table_args__ = (UniqueConstraint('history_entry_id', 'word_id'),)

class DatabaseManager():
    def __init__(self):
        engine = create_engine("sqlite:///vocabulary_db.db", echo=True)
        Base.metadata.create_all(engine)
        self.session = Session(engine)

    def add_words_to_db(self, word_list: List[Tuple[str, str, int]]) -> None:
        """
        Insert tuples of (word, part-of-speech, frequency) into words table.
        If a combination of (word, pos) already exists in the database,
        only the freq count is updated.

        Args:
            word_list (List[Tuple[str, str, int]]): list of tuples of (word, pos, freq),
                eg. [("Schule", "NOUN", 234), ...]
        """
        for word_tuple in word_list:
            word, pos, freq = word_tuple
            word_object = WordDBObj(word=word, pos=pos, freq=freq)
            self.session.add(word_object)
        self.session.flush()
        self.session.commit()

    def get_word_by_id(self, word_id: int) -> Optional[LexicalItem]:
        """
        Gets the word from the database by word_id.
        Returns none if the word does not exist.
        """
        statement = select(WordDBObj).where(WordDBObj.id == word_id)
        rows = self.session.scalars(statement).all()
        if len(rows) == 0:
            raise KeyError(f"No such word_id {word_id} is found.")
        elif len(rows) == 1:
            word = rows[0]
            return LexicalItem(word.word, word.pos, word.freq, word.id)
        else:
            return None

if __name__ == "__main__":
    word_freq_output_file_path = "word_freq.txt"
    word_freq_df_loaded = pd.read_csv(word_freq_output_file_path, sep="\t")
    filtered_dataframe = word_freq_df_loaded[word_freq_df_loaded["count"] > 2]
    list_of_tuples: List[Tuple[str, str, int]] = list(filtered_dataframe.to_records(index=False))
    # convert numpy.int64 to Python integer
    list_of_tuples = [(word, pos, int(freq)) for (word, pos, freq) in list_of_tuples]
    db = DatabaseManager()

    db.add_words_to_db(list_of_tuples)
    word = db.get_word_by_id(1)
    print(word)

    db.session.close()