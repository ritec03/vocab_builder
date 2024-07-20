import json
from typing import Dict, List, Optional, Set, Tuple, Union
import pandas as pd
from sqlalchemy import (
    and_,
    func,
    create_engine,
    over,
    select,
    event,
)
from sqlalchemy.orm import sessionmaker, scoped_session, selectinload, joinedload
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from data_structures import (
    MAX_USER_NAME_LENGTH,
    CorrectionStrategy,
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
from task import Task, get_task_type_class
from task_template import TaskTemplate
from flask import Flask
import logging

logger = logging.getLogger(__name__)

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
        logger.warning("Could not load tasks.json file.")
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
            resources = dict()
            for key in serialized_resources.keys():
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

class DatabaseManager:
    def __init__(self, app: Optional[Flask]):
        if app: 
            self.init_app(app)
        else:
            engine = create_engine('sqlite:///database.db', echo=False)
            Base.metadata.create_all(engine)
            self.Session = scoped_session(sessionmaker(bind=engine))

            word_freq_output_file_path = "word_freq.txt"
            word_freq_df_loaded = pd.read_csv(word_freq_output_file_path, sep="\t")
            filtered_dataframe = word_freq_df_loaded[word_freq_df_loaded["count"] > 2]
            list_of_tuples: List[Tuple[str, str, int]] = list(filtered_dataframe.to_records(index=False))
            # convert numpy.int64 to Python integer
            list_of_tuples = [(word, pos, int(freq)) for (word, pos, freq) in list_of_tuples][:100]
            
            indices = self.add_words_to_db(list_of_tuples)

            self.prepopulate_db()
            
            logger.info(indices)
            self.shutdown_session()

    def prepopulate_db(self):
        # add template and create template dict
        templates = read_templates_from_json("templates.json")
        template_dict = dict()
        for template in templates:
            added_template_id = self.add_template(template)
            template_dict[template.get_template_string()] = added_template_id
        tasks = read_tasks_from_json("tasks.json")
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
        # TODO change the return type to dict
        Insert tuples of (word, part-of-speech, frequency) into words table.
        If a combination of (word, pos) already exists in the database,
        only the freq count is updated.

        Args:
            word_list (List[Tuple[str, str, int]]): list of tuples of (word, pos, freq),
                eg. [("Schule", "NOUN", 234), ...]

        Returns:
            List[int]: a list of inserted word_ids
        """
        session = self.Session()
        try:
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
                    else:
                        # UPDATE word freq
                        retrieved_word_obj.freq = freq
                        session.flush()
                    word_ids.append(retrieved_word_obj.id)
            session.commit()
            return word_ids
        
        except Exception as e:
            session.rollback()
            logger.error(e)
            raise Exception(f"Failed to insert words to db: {str(e)}")

    def get_word_obj_by_word_and_pos(self, word: str, pos: str) -> Optional[WordDBObj]:
        """
        WordDBObj with word and pos that is in DB or None.
        Raise:
            ValueError if more than one word-pos entry is found.
        """
        session = self.Session()
        try:
            stmt = select(WordDBObj).where(
                and_(WordDBObj.word == word, WordDBObj.pos == pos)
            )
            word_obj = session.execute(stmt).scalar_one_or_none()
            if word_obj:
                return word_obj
            else:
                raise ValueError(f"None or more than one word-pos {word}-{pos} entry found.")
        except Exception as e:
            session.rollback()
            logger.error(e)
            raise Exception(f"Failed to get word pos: {str(e)}")

    def get_word_by_id(self, word_id: int) -> Optional[LexicalItem]:
        """
        Gets the word from the database by word_id.
        Returns none if the word does not exist.
        """
        session = self.Session()
        try:
            statement = select(WordDBObj).where(WordDBObj.id == word_id)
            rows = session.scalars(statement).all()
            if len(rows) == 0:
                raise KeyError(f"No such word_id {word_id} is found.")
            elif len(rows) == 1:
                word = rows[0]
                return LexicalItem(word.word, word.pos, word.freq, word.id)
            else:
                return None
        except Exception as e:
            session.rollback()
            logger.error(e)
            raise


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
        session = self.Session()
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
        # with self.Session.begin() as session:
        session = self.Session()
        try:
            user = session.get(UserDBObj, user_id)
            if not user:
                raise ValueDoesNotExistInDB(f"User with ID {user_id} does not exist.")
            else:
                session.delete(user)
                session.flush()
                session.commit()
                logger.info(f"User with ID {user_id} removed successfully.")
        except:
            session.rollback()
            raise

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
        session = self.Session()
        try:
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
                raise ValueDoesNotExistInDB("User or word or lesson id invalid.")
        except Exception as e:
            session.rollback()
            logger.error(e)
            raise e

    def get_score(self, user_id: int, word_id: int, lesson_id: int):
            session = self.Session()
            try:
                entry = session.execute(
                    select(LearningDataDBObj).where(
                        LearningDataDBObj.user_id == user_id,
                        LearningDataDBObj.word_id == word_id,
                        LearningDataDBObj.lesson_id == lesson_id,
                    )
                ).scalar()
                return entry.score if entry else None
            except Exception as e:
                session.rollback()
                logger.error(e)
                raise e

    def update_user_scores(self, user_id: int, lesson_scores: Set[Score], lesson_id: int) -> None:
        """
        Update user scores for the lesson scores which is a list of scores
        for each word_id. If the word with a score for the user is already in db,
        udpate it, add it otherwise.
        If non existent user - raise ValueDoesNotExistInDB
        If ther eis a word or words that are not in db - raise ValueDoesNotExistInDB
        """
        session = self.Session()
        try:
            # Verify user exists
            user = session.get(UserDBObj, user_id)
            if not user:
                raise ValueDoesNotExistInDB("User does not exist")

            # Process each score
            for score in lesson_scores:
                self.add_word_score(user_id, score, lesson_id)
        except Exception as e:
            session.rollback()
            logger.error(e)
            raise e

    def get_latest_word_score_for_user(self, user_id: int) -> Dict[int, Dict]:
        """
        Retrieves word score data of a user from the learning_data table
        and returns them as a dictionary with keys of word ids and values as dictionaries of scores and timestamps.
        For each word, the most recent score along with the corresponding lesson timestamp is returned.
        Raises ValueDoesNotExistInDB error if non-existent user is requested.
        
        Returns:
            Dict[int word_id, {"score": Score, "timestamp": timestamp}]
        """
        # TODO check for efficiency
        # TODO add more tests to check returning words
        session = self.Session()
        try:
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
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to to get latest scores for user: {str(e)}")
            raise e


    """
    METHODS FOR WORKING WITH TEMPLATES
    """

    def convert_template_obj(self, template_obj: TemplateDBObj) -> TaskTemplate:
        # TODO check that db functions return objects with id.
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
            template_id=template_obj.id
        )
        return template

    def add_template(self, template: TaskTemplate) -> int:
        """
        Adds template to database and returns the new template id.
        If a template with the same template_string exist, return value error.
        """
        session = self.Session()
        try:
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
                    logger.error(e)
                    session.rollback()
                    raise ValueError("the following error occured: ", e)
                except Exception as e:  # TODO change error handling
                    logger.error(e)
                    session.rollback()
                    raise ValueError("the following error occured: ", e)
            session.commit()
            template_id = template_obj.id
            return template_id
        except Exception as e:
            session.rollback()
            logger.error(e)
            raise e

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
        session = self.Session()
        try:
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
        except Exception as e:
            session.rollback()
            logger.error(e)
            raise e

    def get_template_parameters(self, template_id: int) -> Optional[Dict[str, str]]:
        """
        Retrieve parameter descriptions for a template from the database.

        Args:
            template_id (int): The ID of the template.

        Returns:
            dict: A dictionary mapping parameter names to descriptions.
            None if no parameters found
        """
        session = self.Session()
        try:
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
        except Exception as e:
            session.rollback()
            logger.error(e)
            raise e

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
        session = self.Session()
        try:
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
            session.commit()

            # create resource object
            resource = Resource(
                resource_obj.id, resource_obj.resource_text, target_words
            )
            return resource
        except Exception as e:
            session.rollback()
            logger.error(e)
            raise e

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
        session = self.Session()
        try:
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
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(e)
            raise e


    def get_resource_by_id(self, resource_id: int) -> Optional[Resource]:
        session = self.Session()
        try:
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
        except Exception as e:
            session.rollback()
            logger.error(e)
            raise e

    def get_resources_by_target_word(self, target_word: LexicalItem) -> List[Resource]:
        """
        Gets the list resources that contain the target word.
        Raises:
            ValueDoesNotExistInDB error if target word is not in DB.
        """
        session = self.Session()
        try:
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
        except Exception as e:
            session.rollback()
            logger.error(e)
            raise e

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
        session = self.Session()
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
        except Exception as e:
            session.rollback()
            logger.error(e)
            raise

    def get_task_by_id(self, task_id: int) -> Task:
        """
        Retrieves a task by id along with its associated template, resources,
        and template parameters, then constructs a Task object.
        """
        session = self.Session()
        try:
            # Load the task along with its associated template, resources, and target words
            task_obj = session.scalars(
                select(TaskDBObj).where(TaskDBObj.id == task_id)
            ).first()

            if not task_obj:
                raise ValueDoesNotExistInDB(f"Task with ID {task_id} does not exist.")

            # Map the TaskDBObj to the corresponding Task class (OneWayTranslaitonTask or FourChoiceTask)
            task = self.convert_task_obj_to_task(task_obj)
            return task
        except Exception as e:
            session.rollback()
            logger.error(e)
            raise e

    def get_tasks_by_type(self, task_type: TaskType, number: int = 100) -> List[Task]:
        """
        Return task of the task_type. Returns at most 100 tasks unless otherwise specified.
        Raise ValueError if invalid task type.
        """
        session = self.Session()
        try:
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
        except Exception as e:
            session.rollback()
            logger.error(e)
            raise e

    def get_tasks_by_template(self, template_id: int, number: int = 100) -> List[Task]:
        """
        Return tasks that are based on the specified template ID.
        Returns at most 'number' tasks unless otherwise specified.
        """
        session = self.Session()
        try:
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
        except Exception as e:
            session.rollback()
            logger.error(e)
            raise e

    def get_tasks_for_words(
        self, target_words: Set[LexicalItem], number: int = 100
    ) -> List[Task]:
        """
        Return tasks whose task.target_words is a superset of the target_words.
        Returns at most 100 tasks unless otherwise specified.
        """
        session = self.Session()
        try:
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

            # BUG SAWarning: Coercing Subquery object into a select() for use in IN(); please pass a select() construct explicitly
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
                task = self.convert_task_obj_to_task(task_obj)
                result_tasks.append(task)

            return result_tasks
        except Exception as e:
            session.rollback()
            logger.error(e)
            raise e

    def remove_task(self, task_id: int) -> None:
        """
        Removes task from tasks and task_resources tables.
        Raises error if there are any lessons associated with that task.
        """
        session = self.Session()
        try:
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
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(e)
            raise e


    """
    METHODS FOR WORKING WITH LESSONS
    """

    def retrieve_lesson(self, user_id: int) -> Optional[Dict[str, Union[int, Dict[str, Union[Tuple[int, int], Task]]]]]:
        """
        Retrieves lesson_id and first task for a lesson if there is
        a new uncompleted lesson for the user. Otherwise, returns None.
        There is a new uncompleted lesson for the user if there is a lesson
        that has completed as false and none of which tasks are marked as
        completed.

        Assumes the user exists.

        Returns:
            {
                "lesson_id": int
                "task": {
                    "order": (1,1)
                    "first_task": Task
                }
            }
        """
        session = self.Session()
        try:
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

            first_task_id = None
            # Check if all tasks in the lesson are uncompleted
            for task in latest_lesson.lesson_plan.tasks:
                if task.completed:
                    raise Exception("Found a completed task in an uncompleted lesson.")
                if task.sequence_num == 0 and task.attempt_num == 0:
                    first_task_id = task.task_id

            # Retrieve the first uncompleted task in the lesson plan
            if not first_task_id:
                raise Exception("New lesson contains zero tasks or sequence numbering is wrong.")
            
            task = self.get_task_by_id(first_task_id)

            # Construct the response dictionary
            return {
                "lesson_id": latest_lesson.id,
                "task": {
                    "order": (0,0),
                    "first_task": task
                }
            }
        except Exception as e:
            session.rollback()
            logger.error(e)
            raise e

    def save_lesson_plan(
            self,
            user_id: int, 
            lesson_plan: List[Tuple[Task, List[Union[CorrectionStrategy, Task]]]]
        ) -> Dict[str, Union[int, Dict[str, Union[Tuple[int,int], Task]]]]:
        """
        Initializes a lesson and saves lesson plan for the lesson.
        Checks if a new lesson already exists for the user.
        Raises:
            ValueDoesNotExistInDB if user is not found
        Params:
            lesson_plan: a list of (Task, Tuple[values from CorrectionStrategyEnum, or Task])
            user_id : int
        Returns:
            {
                "lesson_id": int
                "task": {
                    "order": (0,0)
                    "first_task": Task
                }
            }
        """
        session = self.Session()
        try:
            # Check if user exists
            user = session.get(UserDBObj, user_id)
            if not user:
                raise ValueDoesNotExistInDB("User does not exist")

            # Check for existing uncompleted lessons
            lesson_head = self.retrieve_lesson(user_id)
            if lesson_head:
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
                "task": {
                    "order": (0,0),
                    "first_task": lesson_plan[0][0]
                }
            }
        except Exception as e:
            session.rollback()
            logger.error(e)
            raise
        
    def save_evaluation_for_task(
        self, 
        user_id: int, 
        lesson_id: int, 
        order: Tuple[int,int],
        history_entry: HistoryEntry
    ):
        """
        Saves the evaluation for a task in the database.

        Args:
            user_id (int): The ID of the user.
            lesson_id (int): The ID of the lesson.
            order (Tuple[int,int]): The order of the task in the lesson plan (sequence number, attempt number).
            history_entry (HistoryEntry): The history entry containing the evaluation data.

        Raises:
            ValueDoesNotExistInDB: If the lesson or user does not exist in the database.
            Exception: If the retrieved task and submitted task have different IDs.

        Returns:
            None
        """
        session = self.Session()
        try:
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
                    LessonPlanTaskDBObj.sequence_num == order[0],
                    LessonPlanTaskDBObj.attempt_num == order[1],
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
                sequence_number=lesson_task_obj.attempt_num,
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

        except Exception as e:
            session.rollback()
            logger.error(e)
            raise Exception(f"Failed to save evaluation for task: {str(e)}")

    def get_evaluation_for_task(
            self,
            user_id: int,
            lesson_id: int,
            order: Tuple[int, int]
    ) -> Optional[Evaluation]:
        """
        Returns evaluation object for the task at sequence number order[0].
        Return None if there is no such evaluation yet.
        """
        session = self.Session()
        try:
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
                    EvaluationDBObj.sequence_number == order[0]
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
        except Exception as e:
            session.rollback()
            logger.error(e)
            raise Exception(f"Failed to retrieve evaluation for task: {str(e)}")


    def get_next_task_for_lesson(
            self,
            user_id: int, 
            lesson_id: int
        ) -> Optional[Dict[str, Union[None, CorrectionStrategy, Task, Evaluation, Tuple[int,int]]]]:
        """
        Get the next task in the lesson for the user, if the task is defined. If
        the next task is not defined in the the lesson plan (the case for a retry according
        to the correction strategy), then return Evaluation object for the task which
        can be used for task generation downstream.

        If there are no more tasks, marks the lesson as completed.

        Returns a dictionary of form:
            {
                "order" : (int,int)
                "task" : Task or None
                "eval" : Evaluation or None
                "error_correction": CorrectionStrategy | None - strategy according 
                    to which this task is chosen
            }
            None if there are no more tasks in the lesson to be completed.
        """
        # NOTE ERROR:database_orm:Couldn't get next task for lesson: The unique() method must be invoked on this Result, as it contains results that include joined eager loads against collections

        session = self.Session()
        try:
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
                    if task_obj.error_correction and task_obj.error_correction != CorrectionStrategy.NoStrategy:
                        evaluation = self.get_evaluation_for_task(user_id, lesson_id, (task_obj.sequence_num, task_obj.attempt_num))
                        return {
                            "order": (task_obj.sequence_num, task_obj.attempt_num),
                            "task": None,
                            "eval": evaluation,
                            "error_correction": task_obj.error_correction
                        }
                    
                    # Retrieve the Task associated with this lesson plan task
                    task = self.get_task_by_id(task_obj.task_id)
                    return {
                        "order": (task_obj.sequence_num, task_obj.attempt_num),
                        "task": task,
                        "eval": None,
                        "error_correction": None
                    }

            # If no uncompleted tasks are found, mark the lesson as completed
            lesson.completed = True
            session.commit()
            return None  # Indicate that there are no more tasks

        except Exception as e:
            session.rollback()
            logger.error(f"Couldn't get next task for lesson: {str(e)}")
            raise Exception(f"Failed to get next task for lesson: {str(e)}")
    
    def update_lesson_plan_with_task(
            self,
            user_id: int, 
            lesson_id: int, 
            task: Task,
            order: Tuple[int, int]
        ):
        """
        Updates the lesson plan with the task at the sequence num and attempt num.
        If the lesson plan task at the order is not None, raise an exception.
        If the lesson plan task at the order is not a non-generated error correction task
        (its task value is none and its error correction is set to a strategy which is
        not NoStrategy), raise and exception.
        """
        session = self.Session()
        try:
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
                if t.sequence_num == order[0] and t.attempt_num == order[1]:
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

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update the lesson plan: {str(e)}")
            raise Exception(f"Failed to update the lesson plan: {str(e)}")
    
    def save_user_lesson_data(
        self, user_id: int, lesson_data: List[Evaluation]
    ) -> int:
        """
        Saves user lesson data into the database by saving into user_lessons table,
        adding the evaluations list in order into evaluations table, and saving each history entry
        into the history entries in order, with received scores going to entry_scores table
        Raises ValueDoesNotExistInDB if user does not exist.
        TODO Returns lesson id.
        """
        session = self.Session()
        try:
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
            session.commit()
            lesson_id = new_lesson.id
            return lesson_id
        except Exception as e:
            session.rollback()
            logger.error(e)
            raise e

    def get_most_recent_lesson_data(self, user_id: int) -> Optional[List[Evaluation]]:
        """
        Gets the lesson data for the most recent lesson.
        Returns None if the user has not completed any lessons.
        Raises ValueDoesNotExistInDB if user does not exist.
        """
        session = self.Session()
        try:
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
        except Exception as e:
            session.rollback()
            logger.error(e)
            raise e
        
    def finish_lesson(self, user_id: int, lesson_id: int) -> List[Dict[str, Union[LexicalItem, int]]]:
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
            List[Dict[str, Union[LexicalItem, int]]]: A list of dictionaries containing lexical item and score.
        """
        session = self.Session()
        try:
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

            # Calculate final scores for the lesson
            final_scores: Set[Score] = set()
            # NOTE for now use default by saving the latest score for each evaluation
            for evaluation in evaluations:
                final_scores.update(evaluation.get_final_scores_latest())

            self.update_user_scores(user_id, final_scores, lesson_id)

            # Create a list of dictionaries containing lexical item and score
            result = self.convert_scores(final_scores)

            return result

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to finish lesson: {str(e)}")
            raise Exception(f"Failed to finish lesson: {str(e)}")
        
    def convert_scores(self, scores: Set[Score]) -> List[Dict[str, Union[LexicalItem, int]]]:
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
        session = self.Session()
        try:
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
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to retrieve words for lesson: {str(e)}")
            raise e
