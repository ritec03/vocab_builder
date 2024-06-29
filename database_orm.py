from datetime import datetime
import json
from typing import Dict, List, Optional, Set, Tuple
import pandas as pd
from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    UniqueConstraint,
    and_,
    Enum,
    func,
    Integer,
    JSON,
    create_engine,
    select,
    TIMESTAMP,
    event,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from data_structures import (
    MAX_USER_NAME_LENGTH,
    Language,
    LexicalItem,
    Resource,
    Score,
    TaskType,
    MAX_SCORE,
    MAX_USER_NAME_LENGTH,
    MIN_SCORE,
    User,
)

from evaluation import Evaluation, HistoryEntry
from task import Task, get_task_type_class
from task_template import TaskTemplate


class ValueDoesNotExistInDB(LookupError):
    """
    Error is thrown when a value queries in the database
    does not exist (eg. user_name or word_id)
    """

    pass


class InvalidDelete(Exception):
    """
    Error is thrown when deletion of an object from the DB
    fails due to associations with other existing objects.
    """

    pass


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
    resources = relationship("ResourceWordDBObj", back_populates="word")
    __table_args__ = (UniqueConstraint("word", "pos"),)


class LearningDataDBObj(Base):
    __tablename__ = "learning_data"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id = mapped_column(ForeignKey("users.id"))
    word_id = mapped_column(ForeignKey("words.id"))
    score: Mapped[int] = mapped_column(
        Integer, CheckConstraint("score >= 0 AND score <= 10"), unique=False
    )


class TemplateDBObj(Base):
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
    __tablename__ = "template_parameters"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=False)
    description: Mapped[str]
    template_id = mapped_column(ForeignKey("templates.id"))
    template = relationship("TemplateDBObj", back_populates="parameters")
    __table_args__ = (UniqueConstraint("template_id", "name"),)


class ResourceDBObj(Base):
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
    __tablename__ = "resource_words"

    id: Mapped[int] = mapped_column(primary_key=True)
    resource_id = mapped_column(Integer, ForeignKey("resources.id", ondelete="CASCADE"))
    word_id = mapped_column(Integer, ForeignKey("words.id"))
    resources = relationship("ResourceDBObj", back_populates="words")
    word = relationship("WordDBObj", back_populates="resources")
    # each word appears in a resource once only
    __table_args__ = (UniqueConstraint("resource_id", "word_id"),)


class TaskDBObj(Base):
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
    __tablename__ = "task_target_words"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id = mapped_column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"))
    word_id = mapped_column(Integer, ForeignKey("words.id"))
    word: Mapped["WordDBObj"] = relationship("WordDBObj")


class TaskResourceDBObj(Base):
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
    __tablename__ = "user_lessons"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id = mapped_column(Integer, ForeignKey("users.id"))
    timestamp: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now(), type_=TIMESTAMP
    )
    evaluations: Mapped[List["EvaluationDBObj"]] = relationship("EvaluationDBObj")


class EvaluationDBObj(Base):
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
    __tablename__ = "history_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_id = mapped_column(Integer, ForeignKey("evaluations.id"))
    sequence_number: Mapped[int] = mapped_column()
    task_id = mapped_column(Integer, ForeignKey("tasks.id"))
    response: Mapped[str]
    scores: Mapped[List["EntryScoreDBObj"]] = relationship("EntryScoreDBObj")
    __table_args__ = (UniqueConstraint("evaluation_id", "sequence_number"),)


class EntryScoreDBObj(Base):
    __tablename__ = "entry_scores"

    id: Mapped[int] = mapped_column(primary_key=True)
    history_entry_id = mapped_column(Integer, ForeignKey("history_entries.id"))
    word_id = mapped_column(Integer, ForeignKey("words.id"))
    score: Mapped[int] = mapped_column(
        Integer, CheckConstraint("score >= 0 AND score <= 10")
    )
    # Ensuring one score per word per history entry
    __table_args__ = (UniqueConstraint("history_entry_id", "word_id"),)


class DatabaseManager:
    def __init__(self, db_path: str):
        engine = create_engine("sqlite:///" + db_path, echo=True)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(engine)

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
        with self.Session.begin() as session:
            word_ids = []
            for word_tuple in word_list:
                word, pos, freq = word_tuple
                word_object = WordDBObj(word=word, pos=pos, freq=freq)
                # check if combination of word-pos exist
                try:
                    session.add(word_object)
                    print("Error happens here")
                    session.flush()
                    word_ids.append(word_object.id)
                except IntegrityError:
                    with self.Session.begin() as session:
                        word = self.get_word_pos(word_object.word, word_object.pos)
                        session.add(word)
                        if not word:
                            raise
                        else:
                            # UPDATE word freq
                            word.freq = freq
                            session.flush()
                            word_ids.append(word.id)
            return word_ids

    def get_word_pos(self, word: str, pos: str) -> Optional[WordDBObj]:
        """
        WordDBObj with word and pos that is in DB or None.
        Raise:
            ValueError if more than one word-pos entry is found.
        """
        with self.Session.begin() as session:
            stmt = select(WordDBObj).where(
                and_(WordDBObj.word == word, WordDBObj.pos == pos)
            )
            rows = session.scalars(stmt).all()
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
        with self.Session.begin() as session:
            statement = select(WordDBObj).where(WordDBObj.id == word_id)
            rows = session.scalars(statement).all()
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
        with self.Session.begin() as session:
            if not isinstance(user_name, str) or len(user_name) > MAX_USER_NAME_LENGTH:
                raise ValueError("Username is not a string or too long.")
            try:
                user = UserDBObj(user_name=user_name)
                session.add(user)
                session.flush()
                return user.id
            except IntegrityError as e:
                raise ValueError(f"User '{user_name}' already exists in the database.")

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        Return UserDBObj with user_id.

        Args:
            user_id: int - user id
        Raises?

        Returns:
            UserDBObj: user database object
            None if no user is found
        """
        with self.Session.begin() as session:
            statement = select(UserDBObj).where(UserDBObj.id == user_id)
            rows = session.scalars(statement).all()
            if len(rows) == 0:
                return None
            elif len(rows) == 1:
                user_obj = rows[0]
                user = User(user_obj.id, user_obj.user_name)
                return user
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
        with self.Session.begin() as session:
            user = session.get(UserDBObj, user_id)
            if not user:
                raise ValueDoesNotExistInDB(f"User with ID {user_id} does not exist.")
            else:
                session.delete(user)
                session.flush()
                print(f"User with ID {user_id} removed successfully.")

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
        with self.Session.begin() as session:
            if not MIN_SCORE <= score.score <= MAX_SCORE:
                raise ValueError(
                    f"Score should be between {MIN_SCORE} and {MAX_SCORE}."
                )

            # Check if score exists, update if yes, else create new
            entry = session.execute(
                select(LearningDataDBObj).where(
                    and_(
                        LearningDataDBObj.user_id == user_id,
                        LearningDataDBObj.word_id == score.word_id,
                    )
                )
            ).scalar()
            if entry:
                entry.score = score.score
            else:
                try:
                    new_entry = LearningDataDBObj(
                        user_id=user_id, word_id=score.word_id, score=score.score
                    )
                    session.add(new_entry)
                    session.flush()
                except IntegrityError:
                    raise ValueDoesNotExistInDB("User or word id invalid.")

    def get_score(self, user_id, word_id):
        with self.Session.begin() as session:
            entry = session.execute(
                select(LearningDataDBObj).where(
                    LearningDataDBObj.user_id == user_id,
                    LearningDataDBObj.word_id == word_id,
                )
            ).scalar()
            return entry.score if entry else None

    def update_user_scores(self, user_id: int, lesson_scores: Set[Score]) -> None:
        """
        Update user scores for the lesson scores which is a list of scores
        for each word_id. If the word with a score for the user is already in db,
        udpate it, add it otherwise.
        If non existent user - raise ValueDoesNotExistInDB
        If ther eis a word or words that are not in db - raise ValueDoesNotExistInDB
        """
        with self.Session.begin() as session:
            # Verify user exists
            user = session.get(UserDBObj, user_id)
            if not user:
                raise ValueDoesNotExistInDB("User does not exist")

            # Process each score
            for score in lesson_scores:
                # Verify word exists
                word = session.get(WordDBObj, score.word_id)
                if not word:
                    raise ValueDoesNotExistInDB("Word does not exist")

                # Add or update the score
                existing_score = session.execute(
                    select(LearningDataDBObj).where(
                        LearningDataDBObj.user_id == user_id,
                        LearningDataDBObj.word_id == score.word_id,
                    )
                ).scalar()

                if existing_score:
                    existing_score.score = score.score
                else:
                    new_score = LearningDataDBObj(
                        user_id=user_id, word_id=score.word_id, score=score.score
                    )
                    session.add(new_score)

    def retrieve_user_scores(self, user_id: int) -> Dict[int, Score]:
        """
        Retrieves word score data of a user from the learning_data table
        and returns them as a dictionary with keys of word ids and values of scores.
        Raises ValueDoesNotExistInDB error if non-existent user is requested.
        """
        with self.Session.begin() as session:
            # First, check if the user exists in the database
            if not session.get(UserDBObj, user_id):
                raise ValueDoesNotExistInDB(f"User with ID {user_id} does not exist.")

            # Query to fetch all scores for the user
            scores_query = select(LearningDataDBObj).where(
                LearningDataDBObj.user_id == user_id
            )
            scores = session.execute(scores_query).scalars().all()

            # Convert the ORM objects to Score dataclass instances
            result = {
                score.word_id: Score(word_id=score.word_id, score=score.score)
                for score in scores
            }
            return result

    """
    METHODS FOR WORKING WITH TEMPLATES
    """

    def convert_template_obj(self, template_obj: TemplateDBObj) -> TaskTemplate:
        parameters = {}
        for param in template_obj.parameters:
            parameters[param.name] = param.description

        template = TaskTemplate(
            target_language=template_obj.target_language,
            starting_language=template_obj.starting_language,
            template_string=template_obj.template,
            template_description=template_obj.description,
            template_examples=json.loads(template_obj.examples),
            parameter_description=parameters,
            task_type=template_obj.task_type,
        )
        return template

    def add_template(self, template: TaskTemplate) -> int:
        """
        Adds template to database and returns the new template id.
        If a template with the same template_string exist, return value error.
        """
        with self.Session.begin() as session:
            template_obj = TemplateDBObj(
                task_type=template.task_type,
                template=template.get_template_string(),
                description=template.description,
                examples=json.dumps(template.examples),
                starting_language=template.starting_language,
                target_language=template.target_language,
            )
            session.add(template_obj)
            for param_key in template.parameter_description:
                param_obj = TemplateParameterDBObj(
                    name=param_key,
                    description=template.parameter_description[param_key],
                )
                template_obj.parameters.append(param_obj)
                try:
                    session.flush()
                except IntegrityError as e:
                    session.rollback()
                    raise ValueError("the following error occured: ", e)
                except Exception as e:  # TODO change error handling
                    session.rollback()
                    raise ValueError("the following error occured: ", e)
            template_id = template_obj.id
            return template_id

    def remove_template(template_name: str) -> None:
        """
        Removes template with template_string from the database and ALL
        associated tasks that use this template.
        """
        raise NotImplementedError()

    def get_template_by_id(self, template_id: int) -> Optional[TaskTemplate]:
        """
        Retrieve a template from the database based on its ID.

        Args:
            template_id (int): The ID of the template to retrieve.

        Returns:
            Optional[TaskTemplate]: The retrieved template, or None if not found.
        """
        with self.Session.begin() as session:
            stmt = select(TemplateDBObj).where(TemplateDBObj.id == template_id)
            rows = session.scalars(stmt).all()
            if len(rows) == 0:
                return None
            elif len(rows) == 1:
                template_obj = rows[0]
                template = self.convert_template_obj(template_obj)
                return template
            else:
                raise KeyError(f"User id {template_id} is not unique.")

    def get_template_parameters(self, template_id: int) -> Optional[Dict[str, str]]:
        """
        Retrieve parameter descriptions for a template from the database.

        Args:
            template_id (int): The ID of the template.

        Returns:
            dict: A dictionary mapping parameter names to descriptions.
            None if no parameters found
        """
        with self.Session.begin() as session:
            stmt = select(TemplateParameterDBObj).where(
                TemplateParameterDBObj.template_id == template_id
            )
            rows = session.scalars(stmt).all()
            if len(rows) == 0:
                return None
            parameters = {}
            for row in rows:
                parameters[row.name] = row.description
            return parameters

    def get_templates_by_task_type(self, task_type: TaskType) -> List[TaskTemplate]:
        """
        Retrieve a list of templates from the database based on the task type.

        Args:
            task_type (TaskType): The task type to filter templates.

        Returns:
            List[TaskTemplate]: A list of templates matching the task type, or an empty list if none found.
        """
        with self.Session.begin() as session:
            stmt = select(TemplateDBObj).where(TemplateDBObj.task_type == task_type)
            try:
                rows = session.scalars(stmt).all()
                return [self.convert_template_obj(row) for row in rows]
            except Exception as e:
                raise ValueError("The following error occured ", e)

    """
    METHODS FOR WORKING WITH RESOURCES
    """

    def add_resource_manual(
        self, resource_str: str, target_words: Set[LexicalItem]
    ) -> Resource:
        # TODO raise error if exact same resource was already added
        """
        To be used only when it is known for sure the resource contains
        target words.

        Args:
            resource_str (str): The resource string to add to the database.
            target_words (Set[LexicalItem]): Set of target words contained in the resource.

        Returns:
            Resource: The added resource object.
        """
        with self.Session.begin() as session:
            resource_obj = ResourceDBObj(resource_text=resource_str)

            for target_word in target_words:
                try:
                    word_obj = session.scalars(
                        select(WordDBObj).where(WordDBObj.id == target_word.id)
                    ).all()
                except IntegrityError as e:
                    raise ValueDoesNotExistInDB(e)
                resource_word = ResourceWordDBObj()
                resource_word.word = word_obj[0]
                resource_obj.words.append(resource_word)
            session.add(resource_obj)
            session.flush()

            # create resource object
            resource = Resource(
                resource_obj.id, resource_obj.resource_text, list(target_words)
            )
            return resource

    def add_resource_auto(resource_str: str) -> Resource:
        """
        Add resource string as a task and try to match it to
        lemmatized words
        """
        raise NotImplementedError()

    def remove_resource(self, resource_id) -> None:
        """
        Removes resource if there are no associated tasks with it.
        Raise InvalidDelete if there are associated tasks.
        """
        with self.Session.begin() as session:
            # Retrieve the resource to be deleted
            resource_to_remove = session.get(ResourceDBObj, resource_id)
            if not resource_to_remove:
                raise ValueDoesNotExistInDB(
                    f"Resource with ID {resource_id} does not exist."
                )

            # check if there are tasks associated with the resource
            tasks = session.scalars(
                select(TaskResourceDBObj).where(
                    TaskResourceDBObj.resource_id == resource_id
                )
            ).first()
            if tasks:
                raise InvalidDelete("There are tasks associated with this resource.")

            # Delete the resource itself
            session.delete(resource_to_remove)

    def get_resource_by_id(self, resource_id: int) -> Resource:
        with self.Session.begin() as session:
            stmt = select(ResourceDBObj).where(ResourceDBObj.id == resource_id)
            rows = session.scalars(stmt).all()
            if len(rows) == 0:
                return None
            resources = []
            for row in rows:
                lexical_items = []
                for resource_word in row.words:
                    word = resource_word.word
                    lexical_items.append(
                        LexicalItem(word.word, word.pos, word.freq, word.id)
                    )
                resource = Resource(row.id, row.resource_text, lexical_items)
            return resource

    def get_resources_by_target_word(self, target_word: LexicalItem) -> List[Resource]:
        """
        Gets the list resources that contain the target word.
        Raises:
            ValueDoesNotExistInDB error if target word is not in DB.
        """
        with self.Session.begin() as session:
            stmt = select(ResourceDBObj).where(
                ResourceDBObj.words.any(ResourceWordDBObj.word_id == target_word.id)
            )
            rows = session.scalars(stmt).all()
            resources = []
            for row in rows:
                lexical_items = []
                for resource_word in row.words:
                    word = resource_word.word
                    lexical_items.append(
                        LexicalItem(word.word, word.pos, word.freq, word.id)
                    )
                resources.append(Resource(row.id, row.resource_text, lexical_items))
            return resources

    """
    METHODS FOR WORKING WITH TASKS
    """

    def add_task(
        self,
        template_id: int,
        resources: Dict[str, Resource],
        target_words: Set[LexicalItem],
        answer: str,
    ) -> Task:
        """
        Adds a new task to the database.

        Args:
            template_id (int): The ID of the template associated with the task.
            resources (Dict[str, Resource]): A dictionary of resources with identifiers and resources to fill the template.
            target_words (Set[LexicalItem]): A set of target words for the task.
            answer (str): The correct answer for the task.

        Returns:
            Task: The added task object.
        """
        with self.Session.begin() as session:
            # TODO check that resources contain target words ???
            try:
                task_obj = TaskDBObj(template_id=template_id, answer=answer)
                session.add(task_obj)
                # create task target words
                for target_word in target_words:
                    task_target_word_obj = TaskTargetWordDBObj(word_id=target_word.id)
                    task_obj.target_words.append(task_target_word_obj)
                # create task resoruces
                for param_name in resources:
                    task_resource_obj = TaskResourceDBObj(
                        resource_id=resources[param_name].resource_id,
                    )
                    # find parameter
                    stmt = select(TemplateParameterDBObj).where(
                        TemplateParameterDBObj.template_id == template_id,
                        TemplateParameterDBObj.name == param_name,
                    )
                    parameter = session.scalars(stmt).first()
                    task_resource_obj.parameter = parameter
                    task_obj.resources.append(task_resource_obj)
                session.flush()
            except Exception as e:
                session.rollback()
                raise

            template = self.convert_template_obj(task_obj.template)
            # create task object
            # TODO perhaps create the object first without id to validate it?
            Task_type_class = get_task_type_class(template.task_type)

            task = Task_type_class(
                template=template,
                resources=resources,
                learning_items=target_words,
                answer=task_obj.answer,
                task_id=task_obj.id,
            )
            return task

    def get_task_by_id(self, task_id: int) -> Task:
        """
        Retrieves a task by id along with its associated template, resources,
        and template parameters, then constructs a Task object.
        """
        with self.Session.begin() as session:
            # Load the task along with its associated template, resources, and target words
            task_obj = session.scalars(
                select(TaskDBObj).where(TaskDBObj.id == task_id)
            ).first()

            if not task_obj:
                raise ValueDoesNotExistInDB(f"Task with ID {task_id} does not exist.")

            # Map the TaskDBObj to the corresponding Task class (OneWayTranslaitonTask or FourChoiceTask)
            template = self.convert_template_obj(task_obj.template)
            resources = {
                res.parameter.name: Resource(
                    resource_id=res.resource.id,
                    resource=res.resource.resource_text,
                    target_words=set(res.resource.words),
                )
                for res in task_obj.resources
            }
            target_words = set(
                [
                    LexicalItem(
                        item=word.word.word,
                        pos=word.word.pos,
                        freq=word.word.freq,
                        id=word.word.id,
                    )
                    for word in task_obj.target_words
                ]
            )

            Task_type_class = get_task_type_class(template.task_type)

            task = Task_type_class(
                template=template,
                resources=resources,
                learning_items=target_words,
                answer=task_obj.answer,
                task_id=task_obj.id,
            )

            return task

    def get_tasks_by_type(self, task_type: TaskType, number: int = 100) -> List[Task]:
        """
        Return task of the task_type. Returns at most 100 tasks unless otherwise specified.
        Raise ValueError if invalid task type.
        """
        with self.Session.begin() as session:
            if not isinstance(task_type, TaskType):
                raise ValueError(f"Invalid task type provided: {task_type}")

            # Query for tasks with the specified task type using a JOIN with the Template table
            tasks_query = (
                select(TaskDBObj)
                .join(TemplateDBObj, TaskDBObj.template)
                .where(TemplateDBObj.task_type == task_type.name)
                .limit(number)
            )

            # Execute the query
            tasks = session.scalars(tasks_query).all()

            # Convert TaskDBObj to Task instances
            result_tasks = []
            for task_obj in tasks:
                template = self.convert_template_obj(task_obj.template)
                resources = {
                    res.parameter.name: Resource(
                        resource_id=res.resource.id,
                        resource=res.resource.resource_text,
                        target_words=set(res.resource.words),
                    )
                    for res in task_obj.resources
                }
                target_words = set(
                    [
                        LexicalItem(
                            item=word.word.word,
                            pos=word.word.pos,
                            freq=word.word.freq,
                            id=word.word.id,
                        )
                        for word in task_obj.target_words
                    ]
                )

                Task_type_class = get_task_type_class(template.task_type)
                task = Task_type_class(
                    template=template,
                    resources=resources,
                    learning_items=target_words,
                    answer=task_obj.answer,
                    task_id=task_obj.id,
                )

                result_tasks.append(task)

            return result_tasks

    def get_tasks_by_template(self, template_id: int, number: int = 100) -> List[Task]:
        """
        Return tasks that are based on the specified template ID.
        Returns at most 'number' tasks unless otherwise specified.
        """
        with self.Session.begin() as session:
            # Query for tasks associated with the specified template ID
            tasks_query = (
                select(TaskDBObj)
                .where(TaskDBObj.template_id == template_id)
                .limit(number)
            )

            # Execute the query and fetch the results
            tasks = session.scalars(tasks_query).all()

            # Convert TaskDBObj to Task instances
            result_tasks = []
            for task_obj in tasks:
                template = self.convert_template_obj(task_obj.template)
                resources = {
                    res.parameter.name: Resource(
                        resource_id=res.resource.id,
                        resource=res.resource.resource_text,
                        target_words=set(res.resource.words),
                    )
                    for res in task_obj.resources
                }
                target_words = set(
                    [
                        LexicalItem(
                            item=word.word.word,
                            pos=word.word.pos,
                            freq=word.word.freq,
                            id=word.word.id,
                        )
                        for word in task_obj.target_words
                    ]
                )

                Task_type_class = get_task_type_class(template.task_type)
                task = Task_type_class(
                    template=template,
                    resources=resources,
                    learning_items=target_words,
                    answer=task_obj.answer,
                    task_id=task_obj.id,
                )

                result_tasks.append(task)

            return result_tasks

    def get_tasks_for_words(
        self, target_words: Set[LexicalItem], number: int = 100
    ) -> List[Task]:
        """
        Return tasks whose task.target_words is a superset of the target_words.
        Returns at most 100 tasks unless otherwise specified.
        """
        with self.Session.begin() as session:
            # Extract IDs from LexicalItem set for comparison
            target_word_ids = {word.id for word in target_words}

            # Construct a subquery to filter tasks based on word presence
            task_ids_with_all_words = (
                select(TaskDBObj.id)
                .join(TaskTargetWordDBObj, TaskDBObj.target_words)
                .filter(TaskTargetWordDBObj.word_id.in_(target_word_ids))
                .group_by(TaskDBObj.id)
                .having(func.count(TaskDBObj.id) == len(target_word_ids))
            )

            # Create a subquery for use in the main query
            task_ids_subquery = task_ids_with_all_words.subquery()

            # Now query for tasks where task IDs are in the above subquery results
            tasks_query = (
                select(TaskDBObj)
                .where(TaskDBObj.id.in_(task_ids_subquery))
                .limit(number)
            )

            # To execute the query, assuming `session` is your SQLAlchemy Session object:
            tasks = session.execute(tasks_query).scalars().all()

            # Convert TaskDBObj to Task instances
            result_tasks = []
            for task_obj in tasks:
                template = self.convert_template_obj(task_obj.template)
                resources = {
                    res.parameter.name: Resource(
                        resource_id=res.resource.id,
                        resource=res.resource.resource_text,
                        target_words=set(res.resource.words),
                    )
                    for res in task_obj.resources
                }
                target_words = set(
                    [
                        LexicalItem(
                            item=word.word.word,
                            pos=word.word.pos,
                            freq=word.word.freq,
                            id=word.word.id,
                        )
                        for word in task_obj.target_words
                    ]
                )

                Task_type_class = get_task_type_class(template.task_type)
                task = Task_type_class(
                    template=template,
                    resources=resources,
                    learning_items=target_words,
                    answer=task_obj.answer,
                    task_id=task_obj.id,
                )

                result_tasks.append(task)

            return result_tasks

    def remove_task(self, task_id: int) -> None:
        """
        Removes task from tasks and task_resources tables.
        Raises error if there are any lessons associated with that task.
        """
        with self.Session.begin() as session:
            # Retrieve the task to be deleted
            task_to_remove = session.get(TaskDBObj, task_id)
            if not task_to_remove:
                raise ValueDoesNotExistInDB(f"Task with ID {task_id} does not exist.")

            # check if there are lessons
            history_entires = session.scalars(
                select(HistoryEntrieDBObj).where(HistoryEntrieDBObj.task_id == task_id)
            ).first()
            if history_entires:
                raise InvalidDelete(
                    "There are history entries associated with this task."
                )

            # Delete the task itself
            session.delete(task_to_remove)

    def save_user_lesson_data(
        self, user_id: int, lesson_data: List[Evaluation]
    ) -> None:
        """
        Saves user lesson data into the database by saving into user_lessons table,
        adding the evaluations list in order into evaluations table, and saving each history entry
        into the history entries in order, with received scores going to entry_scores table
        Raises ValueDoesNotExistInDB if user does not exist.
        """
        with self.Session.begin() as session:
            if not session.get(UserDBObj, user_id):
                raise ValueDoesNotExistInDB("User does not exist.")

            # Create a new user lesson
            new_lesson = UserLessonDBObj(user_id=user_id)

            for eval_index, evaluation in enumerate(lesson_data, start=1):
                new_evaluation = EvaluationDBObj(sequence_number=eval_index)

                for history_index, history_entry in enumerate(
                    evaluation.history, start=1
                ):
                    new_history_entry = HistoryEntrieDBObj(
                        sequence_number=history_index,
                        task_id=history_entry.task.id,
                        response=history_entry.response,
                    )

                    for score in history_entry.evaluation_result:
                        new_score = EntryScoreDBObj(
                            word_id=score.word_id, score=score.score
                        )
                        new_history_entry.scores.append(new_score)
                    new_evaluation.history_entries.append(new_history_entry)
                new_lesson.evaluations.append(new_evaluation)
            session.add(new_lesson)
            session.flush()
            lesson_id = new_lesson.id
            return lesson_id

    def get_most_recent_lesson_data(self, user_id: int) -> Optional[List[Evaluation]]:
        """
        Gets the lesson data for the most recent lesson.
        Returns None if the user has not completed any lessons.
        Raises ValueDoesNotExistInDB if user does not exist.
        """
        with self.Session.begin() as session:
            # TODO what about correction field?
            if not session.get(UserDBObj, user_id):
                raise ValueDoesNotExistInDB("User does not exist.")

            # Get the most recent lesson
            recent_lesson_query = (
                select(UserLessonDBObj)
                .where(UserLessonDBObj.user_id == user_id)
                .order_by(UserLessonDBObj.timestamp.desc())
                .limit(1)
            )

            # Execute the query and fetch the first result
            recent_lesson = session.scalars(recent_lesson_query).first()

            if not recent_lesson:
                return None

            evaluations = []
            # TODO need to do it in index order
            for evaluation_obj in recent_lesson.evaluations:
                history_entries = []
                for entry in evaluation_obj.history_entries:
                    scores = set(
                        [
                            Score(word_id=score.word_id, score=score.score)
                            for score in entry.scores
                        ]
                    )
                    task = self.get_task_by_id(entry.task_id)
                    history_entries.append(
                        HistoryEntry(
                            task=task, response=entry.response, evaluation_result=scores
                        )
                    )

                evaluation = Evaluation()
                evaluation.history = history_entries
                evaluations.append(evaluation)

            return evaluations

    def retrieve_words_for_lesson(
        self, user_id: int, word_num: int
    ) -> Set[LexicalItem]:
        """
        Retrieves word_num words with highest frequency for which the user
        with user_id does not have scores yet. The words should have pos of either
        NOUN, ADJ or VERB.
        Raises ValueDoesNotExistInDB if user does not exist.
        """
        pass


if __name__ == "__main__":
    word_freq_output_file_path = "word_freq.txt"
    word_freq_df_loaded = pd.read_csv(word_freq_output_file_path, sep="\t")
    filtered_dataframe = word_freq_df_loaded[word_freq_df_loaded["count"] > 2]
    list_of_tuples: List[Tuple[str, str, int]] = list(
        filtered_dataframe.to_records(index=False)
    )
    # convert numpy.int64 to Python integer
    list_of_tuples = [(word, pos, int(freq)) for (word, pos, freq) in list_of_tuples]
    db = DatabaseManager()

    db.add_words_to_db(list_of_tuples)
    word = db.get_word_by_id(1)
    print(word)

    db.session.close()
