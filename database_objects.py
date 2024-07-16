from datetime import datetime
from typing import List
from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    UniqueConstraint,
    Enum,
    func,
    Integer,
    JSON,
    TIMESTAMP,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)
from data_structures import (
    Language,
    TaskType,
)

class Base(DeclarativeBase):
    """
    Base class for all ORM models, making use of the automated mapper in SQLAlchemy.
    """
    pass


class UserDBObj(Base):
    """
    Represents a user in the system with a unique username.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_name: Mapped[str] = mapped_column(unique=True)
    # create_date: Mapped[datetime] = mapped_column(insert_default=func.now())


class WordDBObj(Base):
    """
    Represents words stored in the system, and including information
    about part of speech and word frequency in the corpus.
    Relates to resources that use this word.
    """
    __tablename__ = "words"

    id: Mapped[int] = mapped_column(primary_key=True)
    word: Mapped[str]
    pos: Mapped[str]
    freq: Mapped[int]
    resources = relationship("ResourceWordDBObj", back_populates="word")
    __table_args__ = (UniqueConstraint("word", "pos"),)


class LearningDataDBObj(Base):
    """
    Stores user-specific scores for words.
    """
    __tablename__ = "learning_data"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id = mapped_column(ForeignKey("users.id"))
    word_id = mapped_column(ForeignKey("words.id"))
    score: Mapped[int] = mapped_column(
        Integer, CheckConstraint("score >= 0 AND score <= 10"), unique=False
    )
    lesson_id = mapped_column(ForeignKey("user_lessons.id"))
    lesson = relationship("UserLessonDBObj", back_populates="scores")

    __table_args__ = (
        Index('idx_user_word_lesson_id', 'user_id', 'word_id', 'lesson_id'),
        UniqueConstraint("word_id", "lesson_id"),
    )


class TemplateDBObj(Base):
    """
    Stores templates for tasks, including language settings and a list of parameters.
    """
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    # NOTE sqlalchemy enums use enam names not values
    task_type: Mapped[str] = mapped_column(Enum(TaskType, validate_strings=True))
    template: Mapped[str] = mapped_column(unique=True)
    description: Mapped[str]
    examples: Mapped[str] = mapped_column(JSON)
    starting_language: Mapped[str] = mapped_column(
        Enum(Language, validate_strings=True)
    )
    target_language: Mapped[str] = mapped_column(Enum(Language, validate_strings=True))
    parameters = relationship("TemplateParameterDBObj", back_populates="template")


class TemplateParameterDBObj(Base):
    """
    Stores parameters and their descirptions associated with templates, linked by template_id.
    For example, template "translate this sentence $sentence", $sentence
    is a parameter.
    """
    __tablename__ = "template_parameters"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=False)
    description: Mapped[str]
    template_id = mapped_column(ForeignKey("templates.id"))
    template = relationship("TemplateDBObj", back_populates="parameters")
    __table_args__ = (UniqueConstraint("template_id", "name"),)


class ResourceDBObj(Base):
    """
    Represents resources which are textual materials that can be linked to words
    and used to fill in parameters in templates for tasks.
    """
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    resource_text: Mapped[str]
    words = relationship(
        "ResourceWordDBObj",
        back_populates="resources",
        passive_deletes=True,
        cascade="all, delete",
    )


class ResourceWordDBObj(Base):
    """
    Links words to their resources, allowing for many-to-many relationships.
    """
    __tablename__ = "resource_words"

    id: Mapped[int] = mapped_column(primary_key=True)
    resource_id = mapped_column(Integer, ForeignKey("resources.id", ondelete="CASCADE"))
    word_id = mapped_column(Integer, ForeignKey("words.id"))
    resources = relationship("ResourceDBObj", back_populates="words")
    word = relationship("WordDBObj", back_populates="resources")
    # each word appears in a resource once only
    __table_args__ = (UniqueConstraint("resource_id", "word_id"),)


class TaskDBObj(Base):
    """
    Represents tasks linked to templates and resources that fill the templates.
    """
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id = mapped_column(ForeignKey("templates.id"))
    answer: Mapped[str]
    target_words: Mapped[List["TaskTargetWordDBObj"]] = relationship(
        "TaskTargetWordDBObj", passive_deletes=True, cascade="all, delete"
    )
    resources: Mapped[List["TaskResourceDBObj"]] = relationship(
        "TaskResourceDBObj", passive_deletes=True, cascade="all, delete"
    )
    template: Mapped["TemplateDBObj"] = relationship("TemplateDBObj")


class TaskTargetWordDBObj(Base):
    """
    Stores words targeted in specific tasks.
    """
    __tablename__ = "task_target_words"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id = mapped_column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"))
    word_id = mapped_column(Integer, ForeignKey("words.id"))
    word: Mapped["WordDBObj"] = relationship("WordDBObj")


class TaskResourceDBObj(Base):
    """
    Links template parameters for a tasks to their resources.
    """
    __tablename__ = "task_resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id = mapped_column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"))
    resource_id = mapped_column(Integer, ForeignKey("resources.id"))
    parameter_id = mapped_column(Integer, ForeignKey("template_parameters.id"))
    resource: Mapped["ResourceDBObj"] = relationship("ResourceDBObj")
    parameter: Mapped["TemplateParameterDBObj"] = relationship("TemplateParameterDBObj")
    # TODO add constraint not to include parameters that are not parameters for that template
    __table_args__ = (UniqueConstraint("parameter_id", "task_id"),)


class UserLessonDBObj(Base):
    """
    Records lessons undertaken by users, storing when each lesson was taken.
    """
    __tablename__ = "user_lessons"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"))
    timestamp: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now(), type_=TIMESTAMP
    )
    evaluations: Mapped[List["EvaluationDBObj"]] = relationship("EvaluationDBObj")
    scores = relationship("LearningDataDBObj", back_populates="lesson", cascade="all, delete")

    __table_args__ = (Index("idx_timestamp_desc", timestamp.desc()),) # access most recent lessons

class EvaluationDBObj(Base):
    """
     Stores evaluations of user performances in lessons, conserving the sequence
     of tasks and attempts.
    """
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    lesson_id = mapped_column(Integer, ForeignKey("user_lessons.id"))
    sequence_number: Mapped[int] = (
        mapped_column()
    )  # Ensures sequence numbers are unique within each lesson
    history_entries: Mapped[List["HistoryEntrieDBObj"]] = relationship(
        "HistoryEntrieDBObj"
    )
    __table_args__ = (UniqueConstraint("lesson_id", "sequence_number"),)


class HistoryEntrieDBObj(Base):
    """
    Keeps track of user responses and associated scores within evaluations.
    """
    __tablename__ = "history_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_id = mapped_column(Integer, ForeignKey("evaluations.id"))
    sequence_number: Mapped[int] = mapped_column()
    task_id = mapped_column(Integer, ForeignKey("tasks.id"))
    response: Mapped[str]
    scores: Mapped[List["EntryScoreDBObj"]] = relationship("EntryScoreDBObj")
    __table_args__ = (UniqueConstraint("evaluation_id", "sequence_number"),)


class EntryScoreDBObj(Base):
    """
    Details the scores received by users for specific words within history entries.
    """
    __tablename__ = "entry_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    history_entry_id = mapped_column(Integer, ForeignKey("history_entries.id"))
    word_id = mapped_column(Integer, ForeignKey("words.id"))
    score: Mapped[int] = mapped_column(
        Integer, CheckConstraint("score >= 0 AND score <= 10")
    )
    # Ensuring one score per word per history entry
    __table_args__ = (UniqueConstraint("history_entry_id", "word_id"),)