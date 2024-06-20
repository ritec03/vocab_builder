
from datetime import datetime
from typing import List, Optional
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
from data_structures import TaskType

engine = create_engine("sqlite://", echo=True)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_name: Mapped[str] = mapped_column(unique=True)
    # create_date: Mapped[datetime] = mapped_column(insert_default=func.now())

class Words(Base):
    __tablename__ = "words"

    id: Mapped[int] = mapped_column(primary_key=True)
    word: Mapped[str]
    pos: Mapped[str]
    freq: Mapped[int]
    __table_args__ = (UniqueConstraint('word', 'pos'),)

class LearningData(Base):
    __tablename__ = "learning_data"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id = mapped_column(ForeignKey("users.id"))
    word_id = mapped_column(ForeignKey("words.id"))
    score: Mapped[int] = mapped_column(Integer, CheckConstraint("score >= 0 AND score <= 10"), unique=False)

class Templates(Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    # NOTE sqlalchemy enums use enam names not values
    task_type: Mapped[str] = mapped_column(Enum(TaskType, validate_strings=True))
    template: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str]
    examples: Mapped[str] = mapped_column(JSON) 
    starting_language: Mapped[str]
    target_language: Mapped[str]

class TemplateParameters(Base):
    __tablename__ = "template_parameters"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=False)
    description: Mapped[str]
    template_id = mapped_column(ForeignKey("templates.id"))
    __table_args__ = (UniqueConstraint("template_id", "name"),)

class Tasks(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id = mapped_column(ForeignKey("templates.id"))
    answer: Mapped[str]

class TaskTargetWords(Base):
    __tablename__ = "task_target_words"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id = mapped_column(Integer, ForeignKey("tasks.id"))
    word_id = mapped_column(Integer, ForeignKey("words.id"))

class Resources(Base):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    resource_text: Mapped[str]

class TaskResources(Base):
    __tablename__ = "task_resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id = mapped_column(Integer, ForeignKey("tasks.id"))
    resource_id = mapped_column(Integer, ForeignKey("resources.id"))
    parameter_id = mapped_column(Integer, ForeignKey("template_parameters.id"))
    # TODO add constraint not to include parameters that are not parameters for that template
    __table_args__ = (
        UniqueConstraint("parameter_id", "task_id")
    )

class ResourceWords(Base):
    __tablename__ = "resource_words"

    resource_id = mapped_column(Integer, ForeignKey("resources.id"), primary_key=True)
    word_id = mapped_column(Integer, ForeignKey("words.id"), primary_key=True)
    # each word appears in a resource once only
    __table_args__ = (UniqueConstraint('resource_id', 'word_id'),)

from sqlalchemy import TIMESTAMP

class UserLessons(Base):
    __tablename__ = "user_lessons"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"))
    timestamp: Mapped[datetime] = mapped_column(default=func.now(), server_default=func.now(), type_=TIMESTAMP)

class Evaluations(Base):
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id = mapped_column(Integer, ForeignKey("user_lessons.id"))
    sequence_number: Mapped[int] = mapped_column()
    # Ensures sequence numbers are unique within each lesson
    __table_args__ = (UniqueConstraint('lesson_id', 'sequence_number'),)

class HistoryEntries(Base):
    __tablename__ = "history_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_id = mapped_column(Integer, ForeignKey("evaluations.id"))
    sequence_number: Mapped[int] = mapped_column()
    task_id = mapped_column(Integer, ForeignKey("tasks.id"))
    response: Mapped[str]
    __table_args__ = (UniqueConstraint('evaluation_id', 'sequence_number'),)

class EntryScores(Base):
    __tablename__ = "entry_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    history_entry_id = mapped_column(Integer, ForeignKey("history_entries.id"))
    word_id = mapped_column(Integer, ForeignKey("words.id"))
    score: Mapped[int] = mapped_column(Integer, CheckConstraint("score >= 0 AND score <= 10"))
    # Ensuring one score per word per history entry
    __table_args__ = (UniqueConstraint('history_entry_id', 'word_id'),)
