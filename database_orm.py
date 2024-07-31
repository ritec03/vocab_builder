from contextlib import contextmanager
from dataclasses import asdict, dataclass
import json
import os
from typing import Any, Dict, List, Optional, Set, Tuple, TypedDict, Union
import pandas as pd
from sqlalchemy import (
    and_,
    func,
    create_engine,
    select,
    event,
)
from sqlalchemy.orm import sessionmaker, scoped_session, selectinload, joinedload, Session
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from data_structures import (
    FULL_DATABASE_PATH,
    MAX_USER_NAME_LENGTH,
    TASKS_FILE_DIRECTORY,
    TEMPLATED_FILE_DIRECTORY,
    CorrectionStrategy,
    Language,
    LexicalItem,
    Resource,
    Score,
    TaskType,
    MAX_SCORE,
    MIN_SCORE,
    User,
    UserScore,
)

from database_objects import (
    Base,
    EntryScoreDBObj,
    EvaluationDBObj,
    HistoryEntrieDBObj,
    LearningDataDBObj,
    LessonPlanDBObj,
    LessonPlanTaskDBObj,
    ResourceDBObj,
    ResourceWordDBObj,
    TaskDBObj,
    TaskResourceDBObj,
    TaskTargetWordDBObj,
    TemplateDBObj,
    TemplateParameterDBObj,
    UserDBObj,
    UserLessonDBObj,
    WordDBObj,
)

from evaluation import Evaluation, HistoryEntry
from query_builder import QueryBuilder, QueryCriteria
from task import Task, get_task_type_class
from task_template import TaskTemplate
from flask import Flask
import logging

logger = logging.getLogger(__name__)

@dataclass
class Order:
    sequence_num: int
    attempt: int

class OrderedTask(TypedDict):
    order: Order
    task: Task

class NextTask(OrderedTask):
    eval: None
    error_correction: Optional[CorrectionStrategy]

class NongeneratedNextTask(OrderedTask):
    order: Order
    task: None
    eval: Evaluation
    error_correction: CorrectionStrategy 

class LessonHead(TypedDict):
    lesson_id: int
    first_task: OrderedTask

class ExpandedScore(TypedDict):
    word: LexicalItem
    score: int

LessonPlan = List[Tuple[Task, List[Union[CorrectionStrategy, Task]]]]

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

def read_templates_from_json(file_path: str) -> List[TaskTemplate]:
    """
    Reads a JSON file and converts it into a list of TaskTemplate objects.
    
    Args:
        file_path (str): The path to the JSON file containing the templates.
        
    Returns:
        List[TaskTemplate]: A list of TaskTemplate objects.
    """
    with open(file_path, 'r') as file:
        data = json.load(file)
    
    templates = []
    for item in data:
        try:
            template = TaskTemplate(
                template_string=item["template_string"],
                template_description=item["template_description"],
                template_examples=item["template_examples"],
                parameter_description=item["parameter_description"],
                task_type=TaskType[item["task_type"]],
                starting_language=Language[item["starting_language"]],
                target_language=Language[item["target_language"]]
            )
            templates.append(template)
        except ValueError as e:
            logger.warning(f"Error processing item {item}: {e}")
    
    return templates

def read_tasks_from_json(file_path: str) -> List[Task]:
    """
    Reads a JSON file and converts it into a list of Task objects.
    
    Args:
        file_path (str): The path to the JSON file containing the tasks.
        
    Returns:
        List[Task]: A list of Task objects.
    """
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
    except:
        logger.warning(f"Could not load {TASKS_FILE_DIRECTORY} file.")
        return []

    tasks: List[Task] = []
    for item in data:
        try:
            serizlied_template = item["template"]
            template = TaskTemplate(
                template_string=serizlied_template["template"],
                template_description=serizlied_template["description"],
                template_examples=serizlied_template["examples"],
                parameter_description=serizlied_template["parameter_description"],
                task_type=TaskType[serizlied_template["task_type"]],
                starting_language=Language[serizlied_template["starting_language"]],
                target_language=Language[serizlied_template["target_language"]]
            )
            serialized_resources: Dict[str, Dict] = item["resources"]
            resources = {}
            for key in serialized_resources:
                target_words = [LexicalItem(s_word["item"], s_word["pos"], s_word["freq"], s_word["id"]) for s_word in serialized_resources[key]["target_words"]]
                resource = Resource(serialized_resources[key]["id"], serialized_resources[key]["resource"], set(target_words))
                resources[key] = resource

            target_words = [LexicalItem(s_word["item"], s_word["pos"], s_word["freq"], s_word["id"]) for s_word in item["learning_items"]]
            TaskClass = get_task_type_class(template.task_type)
            task = TaskClass(task_id=item["id"], template=template, resources=resources, learning_items=set(target_words), answer=item["correctAnswer"])
            tasks.append(task)
        except ValueError as e:
            logger.warning(f"Error processing item {item}: {e}")

    return tasks

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

@contextmanager
def managed_session(session_factory: scoped_session[Session]):
    """Context manager for managing SQLAlchemy sessions."""
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Session rolled back due to error: {e}")
        raise


class DatabaseManager:
    def __init__(self, app: Optional[Flask]):
        if app: 
            self.init_app(app)
        elif not os.path.exists(FULL_DATABASE_PATH):
            engine = create_engine(f'sqlite:///{(FULL_DATABASE_PATH)}', echo=False)
            Base.metadata.create_all(engine)
            self.Session = scoped_session(sessionmaker(bind=engine))
            self._prepopulate_db()
            self.shutdown_session()
            
    def _prepopulate_db(self):
        """
        Prepopulates the database with initial data, including words, templates, resources, and tasks.

        Note: This method assumes that the necessary files and directories exist.

        Returns:
            None
        """
        word_freq_output_file_path = "word_freq.txt"
        word_freq_df_loaded = pd.read_csv(word_freq_output_file_path, sep="\t")
        filtered_dataframe = word_freq_df_loaded[word_freq_df_loaded["count"] > 2]
        list_of_tuples: List[Tuple[str, str, int]] = list(filtered_dataframe.to_records(index=False))
        # convert numpy.int64 to Python integer
        list_of_tuples = [(word, pos, int(freq)) for (word, pos, freq) in list_of_tuples][:100]

        indices = self.add_words_to_db(list_of_tuples)
        logger.info(indices)

        # add template and create template dict
        templates = read_templates_from_json(TEMPLATED_FILE_DIRECTORY)
        template_dict = {}
        for template in templates:
            added_template_id = self.add_template(template)
            template_dict[template.get_template_string()] = added_template_id
        tasks = read_tasks_from_json(TASKS_FILE_DIRECTORY)
        for task in tasks:
            task.template.id = template_dict[task.template.get_template_string()]
            for key in task.resources.keys():
                self.add_resource_manual(task.resources[key].resource, task.resources[key].target_words)
            self.add_task(task.template.id, task.resources, task.learning_items, task.correctAnswer)

    def init_app(self, app: Flask):
        engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'], echo=False)
        Base.metadata.create_all(engine)
        self.Session = scoped_session(sessionmaker(bind=engine))
        app.teardown_appcontext(self.shutdown_session)

    def shutdown_session(self, exception=None):
        self.Session.remove()

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
        with managed_session(self.Session) as session:
            word_ids = []
            for word_tuple in word_list:
                word, pos, freq = word_tuple
                word_object = WordDBObj(word=word, pos=pos, freq=freq)
                # check if combination of word-pos exist
                try:
                    session.add(word_object)
                    session.flush()
                    word_ids.append(word_object.id)
                except IntegrityError:
                    session.rollback()
                    retrieved_word_obj = self.get_word_obj_by_word_and_pos(word_object.word, word_object.pos)
                    session.add(retrieved_word_obj)
                    if not retrieved_word_obj:
                        raise
                    # UPDATE word freq
                    retrieved_word_obj.freq = freq
                    session.flush()
                    word_ids.append(retrieved_word_obj.id)
        return word_ids

    def get_word_obj_by_word_and_pos(self, word: str, pos: str) -> Optional[WordDBObj]:
        """
        WordDBObj with word and pos that is in DB or None.
        Raise:
            ValueError if more than one word-pos entry is found.
        """
        with managed_session(self.Session) as session:
            stmt = select(WordDBObj).where(
                and_(WordDBObj.word == word, WordDBObj.pos == pos)
            )
            if word_obj := session.execute(stmt).scalar_one_or_none():
                return word_obj
            else:
                raise ValueError(f"None or more than one word-pos {word}-{pos} entry found.")


    def get_word_by_id(self, word_id: int) -> Optional[LexicalItem]:
        """
        Gets the word from the database by word_id.
        Returns none if the word does not exist.
        """
        with managed_session(self.Session) as session:
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
        session = self.Session()
        if not isinstance(user_name, str) or len(user_name) > MAX_USER_NAME_LENGTH:
            raise ValueError("Username is not a string or too long.")

        try:
            user = UserDBObj(user_name=user_name)
            session.add(user)
            session.flush()
            session.commit()
            return user.id
        except IntegrityError as e:
            session.rollback()
            raise ValueError(f"User '{user_name}' already exists in the database.") from e

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
        session = self.Session()
        statement = select(UserDBObj).where(UserDBObj.id == user_id)
        rows = session.scalars(statement).all()
        if len(rows) == 0:
            return None
        elif len(rows) == 1:
            user_obj = rows[0]
            return User(user_obj.id, user_obj.user_name)
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
        with managed_session(self.Session) as session:
            if user := session.get(UserDBObj, user_id):
                session.delete(user)
                session.flush()
                session.commit()
                logger.info(f"User with ID {user_id} removed successfully.")
            else:
                raise ValueDoesNotExistInDB(f"User with ID {user_id} does not exist.")

    def add_word_score(self, user_id: int, score: Score, lesson_id: int):
        """
        Adds the score for the word for a particular lesson.
        Score should be between MIN_SCORE and MAX_SCORE.

        Constraint: Should add only one score per lesson.

        Assumes:
            that that lesson was added to DB first

        Args:
            user_id (int): ID of the user.
            word_id (int): ID of the word.
            score (int): Score to add (MIN_SCORE and MAX_SCORE).
            lesson_id (int): The lesson id the added score is associated with.
        """
        with managed_session(self.Session) as session:
            if not MIN_SCORE <= score.score <= MAX_SCORE:
                raise ValueError(
                    f"Score should be between {MIN_SCORE} and {MAX_SCORE}."
                )
            try:
                new_entry = LearningDataDBObj(
                    user_id=user_id, word_id=score.word_id, score=score.score, lesson_id=lesson_id
                )
                session.add(new_entry)
                session.flush()
                session.commit()
            except IntegrityError as e:
                session.rollback()
                logger.error(e)
                raise ValueDoesNotExistInDB("User or word or lesson id invalid.") from e

    def get_score(self, user_id: int, word_id: int, lesson_id: int):
        with managed_session(self.Session) as session:
                entry = session.execute(
                    select(LearningDataDBObj).where(
                        LearningDataDBObj.user_id == user_id,
                        LearningDataDBObj.word_id == word_id,
                        LearningDataDBObj.lesson_id == lesson_id,
                    )
                ).scalar()
                return entry.score if entry else None

    def update_user_scores(self, user_id: int, lesson_scores: Set[Score], lesson_id: int) -> None:
        """
        Update user scores for the lesson scores which is a list of scores
        for each word_id. If the word with a score for the user is already in db,
        udpate it, add it otherwise.
        If non existent user - raise ValueDoesNotExistInDB
        If ther eis a word or words that are not in db - raise ValueDoesNotExistInDB
        """
        with managed_session(self.Session) as session:
            # Verify user exists
            user = session.get(UserDBObj, user_id)
            if not user:
                raise ValueDoesNotExistInDB("User does not exist")

            # Process each score
            for score in lesson_scores:
                self.add_word_score(user_id, score, lesson_id)

    def get_latest_word_score_for_user(self, user_id: int) -> Dict[int, UserScore]:
        """
        Retrieves word score data of a user from the learning_data table
        and returns them as a dictionary with keys of word ids and values as dictionaries of scores and timestamps.
        For each word, the most recent score along with the corresponding lesson timestamp is returned.
        Raises ValueDoesNotExistInDB error if non-existent user is requested.
        
        Returns:
            Dict[int word_id, UserScore]
        """
        # TODO check for efficiency
        # TODO add more tests to check returning words
        with managed_session(self.Session) as session:
            # Check if user exists
            user_exists = session.get(UserDBObj, user_id)
            if not user_exists:
                raise ValueDoesNotExistInDB("User does not exist.")

            # Define a subquery to get the latest lesson_id for each word_id for the given user
            subquery = session.query(
                LearningDataDBObj.word_id,
                func.max(LearningDataDBObj.lesson_id).label('latest_lesson_id')
            ).filter(
                LearningDataDBObj.user_id == user_id
            ).group_by(
                LearningDataDBObj.word_id
            ).subquery()

            # Join the LearningDataDBObj with the UserLessonDBObj to get the timestamps
            latest_scores = session.query(
                LearningDataDBObj.word_id,
                LearningDataDBObj.score,
                UserLessonDBObj.timestamp
            ).join(
                UserLessonDBObj,
                LearningDataDBObj.lesson_id == UserLessonDBObj.id
            ).join(
                subquery,
                and_(
                    LearningDataDBObj.word_id == subquery.c.word_id,
                    LearningDataDBObj.lesson_id == subquery.c.latest_lesson_id
                )
            ).all()

            # Convert to dictionary with scores and timestamps
            return {
                word_id: {"score": Score(word_id, score), "timestamp": timestamp}
                for word_id, score, timestamp in latest_scores
            }

    """
    METHODS FOR WORKING WITH TEMPLATES
    """

    def convert_template_obj(self, template_obj: TemplateDBObj) -> TaskTemplate:
        parameters = {
            param.name: param.description for param in template_obj.parameters
        }
        template = TaskTemplate(
            target_language=template_obj.target_language,
            starting_language=template_obj.starting_language,
            template_string=template_obj.template,
            template_description=template_obj.description,
            template_examples=json.loads(template_obj.examples),
            parameter_description=parameters,
            task_type=template_obj.task_type,
            template_id=template_obj.id
        )
        return template

    def add_template(self, template: TaskTemplate) -> int:
        """
        Adds template to database and returns the new template id.
        If a template with the same template_string exist, return value error.
        """
        with managed_session(self.Session) as session:
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
                except (IntegrityError, Exception) as e:
                    logger.error(e)
                    session.rollback()
                    raise ValueError("the following error occured: ", e) from e
            session.commit()
            return template_obj.id

    def remove_template(self, template_name: str) -> None:
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
        with managed_session(self.Session) as session:
            stmt = select(TemplateDBObj).where(TemplateDBObj.id == template_id)
            rows = session.scalars(stmt).all()
            if len(rows) == 0:
                return None
            elif len(rows) == 1:
                template_obj = rows[0]
                return self.convert_template_obj(template_obj)
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
        with managed_session(self.Session) as session:
            stmt = select(TemplateParameterDBObj).where(
                TemplateParameterDBObj.template_id == template_id
            )
            rows = session.scalars(stmt).all()
            return None if len(rows) == 0 else {row.name: row.description for row in rows}

    def get_templates_by_task_type(self, task_type: TaskType) -> List[TaskTemplate]:
        """
        Retrieve a list of templates from the database based on the task type.

        Args:
            task_type (TaskType): The task type to filter templates.

        Returns:
            List[TaskTemplate]: A list of templates matching the task type, or an empty list if none found.
        """
        session = self.Session()
        try:
            stmt = select(TemplateDBObj).where(TemplateDBObj.task_type == task_type)
            rows = session.scalars(stmt).all()
            return [self.convert_template_obj(row) for row in rows]
        except Exception as e:
            session.rollback()
            logger.error(e)
            raise ValueError("The following error occured ", e) from e

    """
    METHODS FOR WORKING WITH RESOURCES
    """

    def add_resource_manual(
        self, resource_str: str, target_words: Set[LexicalItem]
    ) -> Resource:
        # sourcery skip: extract-method, inline-immediately-returned-variable
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
        with managed_session(self.Session) as session:
            resource_obj = ResourceDBObj(resource_text=resource_str)

            for target_word in target_words:
                try:
                    word_obj = session.scalars(
                        select(WordDBObj).where(WordDBObj.id == target_word.id)
                    ).all()
                except IntegrityError as e:
                    raise ValueDoesNotExistInDB(e) from e
                resource_word = ResourceWordDBObj()
                resource_word.word = word_obj[0]
                resource_obj.words.append(resource_word)
            session.add(resource_obj)
            session.flush()
            session.commit()

            # create resource object
            resource = Resource(
                resource_obj.id, resource_obj.resource_text, target_words
            )
            return resource
        
    def add_resource_auto(self, resource_str: str) -> Resource:
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
        with managed_session(self.Session) as session:
            # Retrieve the resource to be deleted
            resource_to_remove = session.get(ResourceDBObj, resource_id)
            if not resource_to_remove:
                raise ValueDoesNotExistInDB(
                    f"Resource with ID {resource_id} does not exist."
                )

            if tasks := session.scalars(
                select(TaskResourceDBObj).where(
                    TaskResourceDBObj.resource_id == resource_id
                )
            ).first():
                raise InvalidDelete("There are tasks associated with this resource.")

            # Delete the resource itself
            session.delete(resource_to_remove)
            session.commit()


    def get_resource_by_id(self, resource_id: int) -> Optional[Resource]:
        with managed_session(self.Session) as session:
            stmt = select(ResourceDBObj).where(ResourceDBObj.id == resource_id)
            rows = session.scalars(stmt).all()
            if len(rows) == 0:
                return None
            resources = []
            for row in rows:
                lexical_items = set()
                for resource_word in row.words:
                    word = resource_word.word
                    lexical_items.add(
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
        with managed_session(self.Session) as session:
            stmt = select(ResourceDBObj).where(
                ResourceDBObj.words.any(ResourceWordDBObj.word_id == target_word.id)
            )
            rows = session.scalars(stmt).all()
            resources = []
            for row in rows:
                lexical_items = set()
                for resource_word in row.words:
                    word = resource_word.word
                    lexical_items.add(
                        LexicalItem(word.word, word.pos, word.freq, word.id)
                    )
                resources.append(Resource(row.id, row.resource_text, lexical_items))
            return resources
        
    """
    METHODS FOR WORKING WITH TASKS
    """

    def convert_task_obj_to_task(self, task_obj: TaskDBObj) -> Task:
        """
        Assumes all parts of task_obj are fully loaded.
        """
        template = self.convert_template_obj(task_obj.template)
        resources = {
            res.parameter.name: Resource(
                resource_id=res.resource.id,
                resource=res.resource.resource_text,
                target_words=set(LexicalItem(word.word.word, word.word.pos, word.word.freq, word.word.id) for word in res.resource.words),
            )
            for res in task_obj.resources
        }
        target_words = {
            LexicalItem(
                item=word.word.word,
                pos=word.word.pos,
                freq=word.word.freq,
                id=word.word.id,
            )
            for word in task_obj.target_words
        }

        Task_type_class = get_task_type_class(template.task_type)
        return Task_type_class(
            template=template,
            resources=resources,
            learning_items=target_words,
            answer=task_obj.answer,
            task_id=task_obj.id,
        )

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
        with managed_session(self.Session) as session:
        # TODO check that resources contain target words ???
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
                parameter = session.execute(stmt).scalar_one()
                task_resource_obj.parameter = parameter
                task_obj.resources.append(task_resource_obj)
            session.flush()
            session.commit()
 
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
        with managed_session(self.Session) as session:
            if task_obj := session.scalars(
                select(TaskDBObj).where(TaskDBObj.id == task_id)
            ).first():
                return self.convert_task_obj_to_task(task_obj)
            else:
                raise ValueDoesNotExistInDB(f"Task with ID {task_id} does not exist.")


    def get_tasks_by_type(self, task_type: TaskType, number: int = 100) -> List[Task]:
        """
        Return task of the task_type. Returns at most 100 tasks unless otherwise specified.
        Raise ValueError if invalid task type.
        """
        with managed_session(self.Session) as session:
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
                task = self.convert_task_obj_to_task(task_obj)
                result_tasks.append(task)

            return result_tasks

    def get_tasks_by_template(self, template_id: int, number: int = 100) -> List[Task]:
        """
        Return tasks that are based on the specified template ID.
        Returns at most 'number' tasks unless otherwise specified.
        """
        with managed_session(self.Session) as session:
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
                task = self.convert_task_obj_to_task(task_obj)
                result_tasks.append(task)

            return result_tasks

    def get_tasks_for_words(
        self, target_words: Set[LexicalItem], number: int = 100
    ) -> List[Task]:
        """
        Return tasks whose task.target_words is a superset of the target_words.
        Returns at most 100 tasks unless otherwise specified.
        """
        with managed_session(self.Session) as session:
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

            # NOTE SAWarning: Coercing Subquery object into a select() for use in IN(); please pass a select() construct explicitly
            # Now query for tasks where task IDs are in the above subquery results
            tasks_query = (
                select(TaskDBObj)
                .where(TaskDBObj.id.in_(select(task_ids_subquery)))
                .limit(number)
            )

            # To execute the query, assuming `session` is your SQLAlchemy Session object:
            tasks = session.execute(tasks_query).scalars().all()

            # Convert TaskDBObj to Task instances
            result_tasks = []
            for task_obj in tasks:
                task = self.convert_task_obj_to_task(task_obj)
                result_tasks.append(task)

            return result_tasks
        
    def get_tasks_by_criteria(self, user_id: int, criteria: QueryCriteria, limit: int = 50) -> list[Task]:
        with managed_session(self.Session) as session:
            task_query = QueryBuilder().build_query(user_id, criteria)
            task_query = task_query.limit(limit)
            tasks = session.execute(task_query).scalars().all()

            # Convert TaskDBObj to Task instances
            result_tasks = []
            for task_obj in tasks:
                task = self.convert_task_obj_to_task(task_obj)
                result_tasks.append(task)

            return result_tasks


    def remove_task(self, task_id: int) -> None:
        """
        Removes task from tasks and task_resources tables.
        Raises error if there are any lessons associated with that task.
        """
        with managed_session(self.Session) as session:
            # Retrieve the task to be deleted
            task_to_remove = session.get(TaskDBObj, task_id)
            if not task_to_remove:
                raise ValueDoesNotExistInDB(f"Task with ID {task_id} does not exist.")

            if history_entires := session.scalars(
                select(HistoryEntrieDBObj).where(
                    HistoryEntrieDBObj.task_id == task_id
                )
            ).first():
                raise InvalidDelete(
                    "There are history entries associated with this task."
                )

            # Delete the task itself
            session.delete(task_to_remove)
            session.commit()


    """
    METHODS FOR WORKING WITH LESSONS
    """

    def serialize_lesson_head(self, lesson_head: LessonHead) -> Optional[Dict[str, Any]]:
        """
        Serializes a LessonHead object into a dictionary.

        Args:
            lesson_head (LessonHead): The LessonHead object to be serialized.

        Returns:
            Optional[Dict[str, Any]]: The serialized LessonHead object as a dictionary.

        Raises:
            Exception: If the task is empty after converting to a dictionary.
        """
        task = lesson_head["first_task"]["task"].to_json()
        if not task:
            message = "Task is empty after converting to dict."
            logger.warning(message)
            raise Exception(message)
        return {
            "lesson_id": lesson_head["lesson_id"],
            "first_task": {
                "order": asdict(lesson_head["first_task"]["order"]),
                "task": task
            }
        }


    def retrieve_lesson(self, user_id: int) -> Optional[LessonHead]:
        """
        Retrieves the lesson ID and the first uncompleted task for a lesson.
        If lesson is new this is going to be the first task. And if it is not,
        then the first task that is marked as uncompleted. Otherwise, it returns None.
        
        Args:
            user_id (int): The ID of the user.

        Raises:
            Exception: If multiple uncompleted lessons are found for the user.
            Exception: If the new lesson contains zero tasks or the sequence numbering is incorrect.

        Returns:
            LessonHead or None: The lesson head object or None if there is no new uncompleted lesson.
        """
        with managed_session(self.Session) as session:
            # Retrieve the uncompleted lessons for the user
            stmt = (
                select(UserLessonDBObj)
                .options(selectinload(UserLessonDBObj.lesson_plan))
                .where(
                    UserLessonDBObj.user_id == user_id,
                    UserLessonDBObj.completed == False
                )
                .order_by(UserLessonDBObj.id.desc())
            )
            lessons = session.execute(stmt).scalars().all()

            if len(lessons) > 1:
                raise Exception("Multiple uncompleted lessons found for the user.")

            if len(lessons) == 0:
                return None

            latest_lesson = lessons[0]
            logger.info(f"The latest uncompleted lesson with ID {latest_lesson.id} was found.")

            first_non_completed_task = None
            # Retrieve the first uncompleted task in the lesson plan
            # use sorted tasks by (sequence_num, attempt) increasing
            # to get first uncompleted task
            sorted_tasks = sorted(latest_lesson.lesson_plan.tasks, key=lambda task: (task.sequence_num, task.attempt_num))
            for task in sorted_tasks:
                if not task.completed:
                    first_non_completed_task = task
                    break

            if not first_non_completed_task:
                raise Exception("New lesson contains zero tasks or sequence numbering is incorrect.")
            
            task = self.get_task_by_id(first_non_completed_task.task_id)

            # Construct the response dictionary
            return {
                "lesson_id": latest_lesson.id,
                "first_task": {
                    "order": Order(first_non_completed_task.sequence_num, first_non_completed_task.attempt_num),
                    "task": task
                }
            }
        
    def retrieve_lesson_serializeable(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieves lesson_id and first task for a lesson if there is
        a new or uncompleted lesson for the user. Otherwise, returns None.
    
        Assumes the user exists.

        Raises Exception if the task conversion to dict fails.

        Args:
            user_id (int): The ID of the user.

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing the lesson_id and
            the first uncompleted task for the lesson, or None if there is no
            new or uncompleted lesson for the user.
        """
        if (lesson_head := self.retrieve_lesson(user_id)):
            return self.serialize_lesson_head(lesson_head)
        return None

    def save_lesson_plan(
            self,
            user_id: int, 
            lesson_plan: LessonPlan
        ) -> LessonHead:
        """
        Initializes a lesson and saves lesson plan for the lesson.
        Checks if a new lesson already exists for the user.
        Raises:
            ValueDoesNotExistInDB if user is not found
        Params:
            lesson_plan: a list of (Task, Tuple[values from CorrectionStrategyEnum, or Task])
            user_id : int
        Returns: LessonHead
        """
        with managed_session(self.Session) as session:
            # Check if user exists
            user = session.get(UserDBObj, user_id)
            if not user:
                raise ValueDoesNotExistInDB("User does not exist")

            if lesson_head := self.retrieve_lesson(user_id):
                return lesson_head

            # Create a new lesson
            new_lesson = UserLessonDBObj(user_id=user_id, completed=False)
            session.add(new_lesson)
            session.flush()  # To obtain the lesson_id
            new_lesson.lesson_plan = LessonPlanDBObj(lesson_id=new_lesson.id)
            session.flush()
            # TODO where to check that the plan is empty?
            # Process each task and its correction strategies
            for index, (task, corrections) in enumerate(lesson_plan):
                lesson_plan_task = LessonPlanTaskDBObj(
                        lesson_plan_id=new_lesson.lesson_plan.id,
                        sequence_num=index,
                        attempt_num=0,
                        task_id=task.id,
                        completed=False,
                        error_correction=CorrectionStrategy.NoStrategy
                    )
                session.add(lesson_plan_task)
                new_lesson.lesson_plan.tasks.append(lesson_plan_task)
                for attempt, correction in enumerate(corrections, start=1):
                    if isinstance(correction, Task):
                        lesson_plan_task = LessonPlanTaskDBObj(
                                lesson_plan_id=new_lesson.lesson_plan.id,
                                sequence_num=index,
                                attempt_num=attempt,
                                task_id=correction.id,
                                completed=False,
                                error_correction=None
                            )
                    elif isinstance(correction, CorrectionStrategy):
                        lesson_plan_task = LessonPlanTaskDBObj(
                                lesson_plan_id=new_lesson.lesson_plan.id,
                                sequence_num=index,
                                attempt_num=attempt,
                                task_id=None,
                                completed=False,
                                error_correction=correction
                            )
                    else:
                        raise Exception("Unknown type for correction object.")
                    session.add(lesson_plan_task)
                    new_lesson.lesson_plan.tasks.append(lesson_plan_task)
                    session.flush()
            session.commit()

            # Return the first task and lesson_id
            return {
                "lesson_id": new_lesson.id,
                "first_task": {
                    "order": Order(0, 0),
                    "task": lesson_plan[0][0]
                }
            }
        
    def save_lesson_plan_serializable(
            self,
            user_id: int, 
            lesson_plan: LessonPlan
        ) -> Optional[Dict[str, Any]]:
        """
        Saves a lesson plan and returns a serializable representation of LessonHead

        Args:
        - self: The instance of the class.
        - user_id (int): The ID of the user.
        - lesson_plan (LessonPlan): The lesson plan to save.

        Returns:
        - Optional[Dict[str, Any]]: A dictionary representing the saved lesson plan in a serializable format.

        Raises:
        - Exception: If the task is empty after converting to a dictionary.
        """
        if (lesson_head := self.save_lesson_plan(user_id, lesson_plan)):
            return self.serialize_lesson_head(lesson_head)
        return None
        
    def save_evaluation_for_task(
        self, 
        user_id: int, 
        lesson_id: int, 
        order: Order,
        history_entry: HistoryEntry
    ):
        """
        Saves the evaluation for a task in the database.

        Args:
            user_id (int): The ID of the user.
            lesson_id (int): The ID of the lesson.
            order (Order): The order of the task in the lesson plan (sequence number, attempt number).
            history_entry (HistoryEntry): The history entry containing the evaluation data.

        Raises:
            ValueDoesNotExistInDB: If the lesson or user does not exist in the database.
            Exception: If the retrieved task and submitted task have different IDs.

        Returns:
            None
        """
        with managed_session(self.Session) as session:
            # Retrieve the lesson using select statement
            stmt = select(UserLessonDBObj).options(selectinload(UserLessonDBObj.lesson_plan)).where(
                UserLessonDBObj.id == lesson_id,
                UserLessonDBObj.user_id == user_id
            )
            lesson = session.execute(stmt).scalar_one_or_none()

            if not lesson:
                raise ValueDoesNotExistInDB("Lesson or User does not exist.")

            # Retrieve the specific task from the lesson plan
            lesson_task_stmt = (
                select(LessonPlanTaskDBObj)
                .options(joinedload(LessonPlanTaskDBObj.task))
                .where(
                    LessonPlanTaskDBObj.lesson_plan_id == lesson.lesson_plan.id,
                    LessonPlanTaskDBObj.sequence_num == order.sequence_num,
                    LessonPlanTaskDBObj.attempt_num == order.attempt,
                    LessonPlanTaskDBObj.task_id == TaskDBObj.id
                )
            )
            lesson_task_obj = session.execute(lesson_task_stmt).scalar_one_or_none()
            if not lesson_task_obj:
                raise ValueDoesNotExistInDB("Lesson Task does not exist in the lesson plan.")
            
            task_obj = lesson_task_obj.task
            if not task_obj:
                raise ValueDoesNotExistInDB("Task of Lesson Task does not exist.")

            if history_entry.task.id != task_obj.id:
                raise Exception("Retrieved task and submitted task have different ids. Maybe wrong order tuple.")

            # Retrieve or create the evaluation
            eval_stmt = select(EvaluationDBObj).where(
                EvaluationDBObj.lesson_id == lesson_id,
                EvaluationDBObj.sequence_number == lesson_task_obj.sequence_num
            )
            evaluation = session.execute(eval_stmt).scalar_one_or_none()

            if not evaluation:
                evaluation = EvaluationDBObj(
                    lesson_id=lesson_id,
                    sequence_number=lesson_task_obj.sequence_num
                )
                session.add(evaluation)

            # Create and add the new history entry
            new_history_entry = HistoryEntrieDBObj(
                attempt=lesson_task_obj.attempt_num,
                task_id=task_obj.id,
                response=history_entry.response
            )
            evaluation.history_entries.append(new_history_entry)

            # Add scores to the new history entry
            for score in history_entry.evaluation_result:
                new_score = EntryScoreDBObj(
                    word_id=score.word_id,
                    score=score.score
                )
                new_history_entry.scores.append(new_score)
            
            session.flush()
            # Mark the task as completed
            lesson_task_obj.completed = True
            session.commit()

    def get_evaluation_for_task(
            self,
            user_id: int,
            lesson_id: int,
            order: Order
    ) -> Optional[Evaluation]:
        """
        Returns evaluation object for the task at sequence number order[0].
        Return None if there is no such evaluation yet.
        """
        with managed_session(self.Session) as session:
            # Check if the lesson exists
            lesson_exists = session.execute(
                select(UserLessonDBObj.id).where(
                    UserLessonDBObj.id == lesson_id,
                    UserLessonDBObj.user_id == user_id
                )
            ).scalar_one_or_none() is not None

            if not lesson_exists:
                raise ValueError("Lesson or user does not exist.")

            # Directly retrieve the specific evaluation
            evaluation_obj = session.execute(
                select(EvaluationDBObj).options(selectinload(EvaluationDBObj.history_entries))
                .where(
                    EvaluationDBObj.lesson_id == lesson_id,
                    EvaluationDBObj.sequence_number == order.sequence_num
                )
            ).scalar_one_or_none()

            if evaluation_obj is None:
                return None  # No evaluation yet for the task

            # Convert to the Evaluation domain model
            evaluation = Evaluation()
            for h_entry_obj in evaluation_obj.history_entries:
                task = self.get_task_by_id(h_entry_obj.task_id)
                scores = {Score(score_obj.word_id, score_obj.score) for score_obj in h_entry_obj.scores}
                evaluation.add_entry(task, h_entry_obj.response, scores)
            return evaluation

    def get_next_task_for_lesson(
            self,
            user_id: int, 
            lesson_id: int
        ) -> Union[None, NextTask, NongeneratedNextTask]:
        """
        Get the next task in the lesson for the user, if the task is defined. If
        the next task is not defined in the the lesson plan (the case for a retry according
        to the correction strategy), then return Evaluation object for the task which
        can be used for task generation downstream.

        If there are no more tasks, marks the lesson as completed.

        Returns
            NextTask
            NongeneratedNextTask
            None if there are no more tasks in the lesson to be completed.
        """
        # NOTE ERROR:database_orm:Couldn't get next task for lesson: The unique() method must be invoked on this Result, as it contains results that include joined eager loads against collections
        with managed_session(self.Session) as session:
            # Fetch lesson plan and its tasks
            # NOTE using options in order to specify which kind of load we want
            # using joinedload as the particular lesson with tasks is small enough dataset.
            stmt = select(UserLessonDBObj).options(
                joinedload(UserLessonDBObj.lesson_plan).joinedload(LessonPlanDBObj.tasks)
            ).where(
                UserLessonDBObj.id == lesson_id,
                UserLessonDBObj.user_id == user_id
            )
            lesson = session.execute(stmt).unique().scalar_one_or_none()

            if not lesson:
                raise ValueError("Lesson not found for the given user and lesson ID.")

            # Filter to find the first uncompleted task
            for task_obj in sorted(lesson.lesson_plan.tasks, key=lambda x: (x.sequence_num, x.attempt_num)):
                if not task_obj.completed:
                    # Check if it needs correction handling
                    # TODO make it clearer when error correction is defined in the table and not
                    # NOTE only error correction task is not defined in the database, so it must have an eval
                    if task_obj.error_correction and task_obj.error_correction != CorrectionStrategy.NoStrategy:
                        if evaluation := self.get_evaluation_for_task(
                            user_id,
                            lesson_id,
                            Order(task_obj.sequence_num, task_obj.attempt_num),
                        ):
                            return {
                                "order": Order(task_obj.sequence_num, task_obj.attempt_num),
                                "task": None,
                                "eval": evaluation,
                                "error_correction": task_obj.error_correction
                            }

                        else:
                            raise ValueDoesNotExistInDB("Evaluation for nongenerated error correction task is missing.")
                    # Retrieve the Task associated with this lesson plan task
                    task = self.get_task_by_id(task_obj.task_id)
                    return {
                        "order": Order(task_obj.sequence_num, task_obj.attempt_num),
                        "task": task,
                        "eval": None,
                        "error_correction": None
                    }

            # If no uncompleted tasks are found, mark the lesson as completed
            lesson.completed = True
            session.commit()
            return None  # Indicate that there are no more tasks

    def update_lesson_plan_with_task(
            self,
            user_id: int, 
            lesson_id: int, 
            task: Task,
            order: Order
        ):
        """
        Updates the lesson plan with the task at the sequence num and attempt num.
        If the lesson plan task at the order is not None, raise an exception.
        If the lesson plan task at the order is not a non-generated error correction task
        (its task value is none and its error correction is set to a strategy which is
        not NoStrategy), raise and exception.
        """
        with managed_session(self.Session) as session:
            # Ensure the user and lesson exist and retrieve the lesson plan
            lesson = session.execute(
                select(UserLessonDBObj)
                .options(joinedload(UserLessonDBObj.lesson_plan).joinedload(LessonPlanDBObj.tasks))
                .where(UserLessonDBObj.id == lesson_id, UserLessonDBObj.user_id == user_id)
            ).scalar_one_or_none()

            if not lesson:
                raise ValueError("Lesson or user does not exist.")

            # Locate the task within the lesson plan
            task_obj = None
            for t in lesson.lesson_plan.tasks:
                if t.sequence_num == order.sequence_num and t.attempt_num == order.attempt:
                    task_obj = t
                    break
            
            if not task_obj:
                raise Exception("Specified task order not found in the lesson plan.")

            # Check if the task slot is eligible for updating
            if (
                task_obj.task_id is not None 
                or task_obj.error_correction == CorrectionStrategy.NoStrategy
            ):
                raise Exception("The task slot is not eligible for updating.")

            # Update the task in the lesson plan
            task_obj.task_id = task.id
            task_obj.completed = False
            session.commit()
    
    def save_user_lesson_data(
        self, user_id: int, lesson_data: List[Evaluation]
    ) -> int:
        """
        Saves user lesson data into the database by saving into user_lessons table,
        adding the evaluations list in order into evaluations table, and saving each history entry
        into the history entries in order, with received scores going to entry_scores table
        Raises ValueDoesNotExistInDB if user does not exist.
        Returns lesson id.
        """
        with managed_session(self.Session) as session:
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
                        attempt=history_index,
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
            session.commit()
            lesson_id = new_lesson.id
            return lesson_id

    def get_most_recent_lesson_data(self, user_id: int) -> Optional[List[Evaluation]]:
        """
        Gets the lesson data for the most recent lesson.
        Returns None if the user has not completed any lessons.
        Raises ValueDoesNotExistInDB if user does not exist.
        """
        with managed_session(self.Session) as session:
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
                    scores = {
                        Score(word_id=score.word_id, score=score.score)
                        for score in entry.scores
                    }
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
        
    def finish_lesson(self, user_id: int, lesson_id: int) -> List[ExpandedScore]:
        """
        Checks that the lesson belongs to the right user, has no uncompleted tasks, 
        then marks the lesson as completed
        in the database, then retrieves all the evaluations
        and calculates final scores for the lesson
        and returns these scores.

        Parameters:
            user_id (int): The ID of the user.
            lesson_id (int): The ID of the lesson to be marked as finished.

        Returns:
            List[ExpandedScore]: A list of dictionaries containing lexical item and score.
        """
        with managed_session(self.Session) as session:
            # Retrieve the lesson
            lesson = session.get(UserLessonDBObj, lesson_id)

            if not lesson:
                raise ValueDoesNotExistInDB(f"Lesson with ID {lesson_id} does not exist.")

            # Check if the lesson belongs to the right user
            if lesson.user_id != user_id:
                raise Exception(f"Lesson with ID {lesson_id} does not belong to user with ID {user_id}.")

            # Check if there are any uncompleted tasks in the lesson
            if any(task.completed == False for task in lesson.lesson_plan.tasks):
                raise Exception("Lesson has uncompleted tasks.")

            # Mark the lesson as completed
            lesson.completed = True
            session.commit()

            # Retrieve all evaluations for the lesson
            evaluations = self.get_most_recent_lesson_data(user_id)
            if not evaluations:
                raise ValueDoesNotExistInDB("No completed lesson was found for the user.")

            # Calculate final scores for the lesson
            final_scores: Set[Score] = set()
            # NOTE for now use default by saving the latest score for each evaluation
            for evaluation in evaluations:
                final_scores.update(evaluation.get_final_scores_latest())

            self.update_user_scores(user_id, final_scores, lesson_id)

            # Create a list of dictionaries containing lexical item and score
            result = self.convert_scores(final_scores)

            return result
        
    def convert_scores(self, scores: Set[Score]) -> List[ExpandedScore]:
        """
        Converts a set of scores into a list of dictionaries containing the corresponding lexical item and score.

        Args:
            scores (Set[Score]): A set of Score objects representing the scores.

        Returns:
            List[Dict[str, Union[LexicalItem, int]]]: A list of dictionaries, where 
            each dictionary contains the lexical item and score.

        """
        result = []
        for score in scores:
            lexicalitem = self.get_word_by_id(score.word_id)  # Retrieve lexical item by ID
            result.append({
                "word": lexicalitem,
                "score": score.score
            })
        return result

    def retrieve_words_for_lesson(
        self, user_id: int, word_num: int
    ) -> Set[LexicalItem]:
        """
        Retrieves word_num words with highest frequency for which the user
        with user_id does not have scores yet. The words should have pos of either
        NOUN, ADJ or VERB.
        Raises ValueDoesNotExistInDB if user does not exist.
        """
        with managed_session(self.Session) as session:
            # Check if the user exists
            if not session.get(UserDBObj, user_id):
                raise ValueDoesNotExistInDB(f"User with ID {user_id} does not exist.")

            # Get IDs of words that the user has already scored
            user_scores = self.get_latest_word_score_for_user(user_id)

            # Retrieve words that are not scored by the user and match the POS criteria
            eligible_words_query = select(WordDBObj).where(
                and_(
                    WordDBObj.id.notin_(list(user_scores.keys())),
                    WordDBObj.pos.in_(['NOUN', 'ADJ', 'VERB'])
                )
            ).order_by(WordDBObj.freq.desc()).limit(word_num)

            # Execute the query
            eligible_words = session.scalars(eligible_words_query).all()

            # Convert WordDBObj to LexicalItem and return
            return {
                LexicalItem(item=word_obj.word, pos=word_obj.pos, freq=word_obj.freq, id=word_obj.id)
                for word_obj in eligible_words
            }
