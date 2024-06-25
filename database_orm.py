
from datetime import datetime
from typing import List, Optional, Tuple
import pandas as pd
from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint, and_, update
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
from data_structures import MAX_USER_NAME_LENGTH, LexicalItem, Score, TaskType, MAX_SCORE, MAX_USER_NAME_LENGTH, MIN_SCORE
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from database import ValueDoesNotExistInDB

from sqlalchemy.engine import Engine
from sqlalchemy import event

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

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
    def __init__(self, db_path: str):
        engine = create_engine("sqlite:///" + db_path, echo=True)
        Base.metadata.create_all(engine)
        self.session = Session(engine)
        
    def close(self):
        self.session.close()

    def add_words_to_db(self, word_list: List[Tuple[str, str, int]]) -> List[int]:
        """
        Insert tuples of (word, part-of-speech, frequency) into words table.
        If a combination of (word, pos) already exists in the database,
        only the freq count is updated.

        Args:
            word_list (List[Tuple[str, str, int]]): list of tuples of (word, pos, freq),
                eg. [("Schule", "NOUN", 234), ...]

        Returns:
            List[int]: a list of inserted word_ids
        """
        word_ids = []
        for word_tuple in word_list:
            word, pos, freq = word_tuple
            word_object = WordDBObj(word=word, pos=pos, freq=freq)
            # check if combination of word-pos exist
            try:
                self.session.add(word_object)
                print("Error happens here")
                self.session.flush()
                word_ids.append(word_object.id)
            except IntegrityError:
                self.session.rollback()
                word = self.get_word_pos(word_object.word, word_object.pos)
                if not word:
                    raise
                else:
                    # UPDATE word freq
                    word.freq = freq
                    self.session.flush()
                    word_ids.append(word.id)
            
        self.session.commit()
        return word_ids
    
    def get_word_pos(self, word: str, pos: str) -> Optional[WordDBObj]:
        """
        WordDBObj with word and pos that is in DB or None.
        Raise:
            ValueError if more than one word-pos entry is found.
        """
        stmt = select(WordDBObj).where(and_(WordDBObj.word == word, WordDBObj.pos == pos))
        rows = self.session.scalars(stmt).all()
        if len(rows) == 0:
            return None
        elif len(rows) == 1:
            word = rows[0]
            return word
        else:
            raise ValueError(f"More than one word-pos {word}-{pos} entry found.")


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
        
    def insert_user(self, user_name: str) -> int:
        """
        Insert a new user into the users table and return the user ID.

        Args:
            user_name (str): Username of the user to insert.

        Raises:
            ValueError: If the user already exists in the database.
            ValueError: If the user name is not a string or is longer than MAX_USER_NAME_LENGTH.

        Returns:
            int: The user ID of the newly inserted user.
        """
        if not isinstance(user_name, str) or len(user_name) > MAX_USER_NAME_LENGTH:
            raise ValueError("Username is not a string or too long.")
        
        try:
            user = UserDBObj(user_name=user_name)
            self.session.add(user)
            self.session.flush()
            self.session.commit()
            return user.id
        except IntegrityError:
            raise ValueError(f"User '{user_name}' already exists in the database.")

    def get_user_by_id(self, user_id: int) -> Optional[UserDBObj]:
        """
        Return UserDBObj with user_id.

        Args:
            user_id: int - user id
        Raises?

        Returns:
            UserDBObj: user database object 
            None if no user is found
        """
        statement = select(UserDBObj).where(UserDBObj.id == user_id)
        rows = self.session.scalars(statement).all()
        if len(rows) == 0:
            return None
        elif len(rows) == 1:
            word = rows[0]
            return word
        else:
            raise KeyError(f"User id {user_id} is not unique.")
    
    def remove_user(self, user_id: int) -> None:
        """
        # TODO also delete data from the lesson data table ???
        Remove user with user_id from users table
        and remove all associated rows in learning_data.

        Args:
            user_id (int): ID of the user to remove.
        
        Raises:
            ValueDoesNotExistInDB if the user with user_id does not exist
        """
        user = self.session.get(UserDBObj, user_id)
        if not user:
            raise ValueDoesNotExistInDB(f"User with ID {user_id} does not exist.")
        else:
            self.session.delete(user)
            self.session.flush()
            print(f"User with ID {user_id} removed successfully.")
        self.session.commit()

    def add_word_score(self, user_id: int, score: Score):
        """
            Adds or updates a row in learning_data for the user with user_id
            for word_id with the given score. Score should be between MIN_SCORE and MAX_SCORE.
            If a score for the word already exists for the user, it is updated.

            Args:
                user_id (int): ID of the user.
                word_id (int): ID of the word.
                score (int): Score to add (MIN_SCORE and MAX_SCORE).
        """
        if not MIN_SCORE <= score.score <= MAX_SCORE:
            raise ValueError(f"Score should be between {MIN_SCORE} and {MAX_SCORE}.")

        # Check if score exists, update if yes, else create new
        entry = self.session.execute(
            select(LearningDataDBObj).where(and_(LearningDataDBObj.user_id == user_id, LearningDataDBObj.word_id == score.word_id))
        ).scalar()
        if entry:
            entry.score = score.score
        else:
            try:
                new_entry = LearningDataDBObj(user_id=user_id, word_id=score.word_id, score=score.score)
                self.session.add(new_entry)
                self.session.flush()
            except IntegrityError:
                raise ValueDoesNotExistInDB("User or word id invalid.")
        self.session.commit()

    def get_score(self, user_id, word_id):
        entry = self.session.execute(
            select(LearningDataDBObj).where(LearningDataDBObj.user_id == user_id, LearningDataDBObj.word_id == word_id)
        ).scalar()
        return entry.score if entry else None
        

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