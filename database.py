"""
This script creates the database and tables for
the vocabulary learning application.
"""
import json
import sqlite3
from sqlite3 import IntegrityError, Connection
import pandas as pd
from typing import Dict, List, Optional, Tuple, Set
from data_structures import MAX_SCORE, MAX_USER_NAME_LENGTH, MIN_SCORE, Language, LexicalItem, Resource, Score, TaskType
from evaluation import Evaluation
from task import OneWayTranslaitonTask, Task
from task_template import TaskTemplate

DATABASE_PATH = "vocabulary_app.db"
SCHEMA_PATH = "schema.sql"


class ValueDoesNotExistInDB(LookupError):
    """
    Error is thrown when a value queries in the database
    does not exist (eg. user_name or word_id)
    """
    pass

class DatabaseManager:
    def __init__(self, db_path: str):
        """
        Initialize the database manager and establish a connection to the database.
        """
        self.connection = self.connect_to_db(db_path)

    def connect_to_db(self, db_path: str) -> Connection:
        """
        Connect to database specified by path and enable
        foreign key checks.

        Args:
            db_path: str - path to database
        """
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON") # add checks on foreign keys
        return conn

    def create_db(self) -> None:
        # Create a cursor object to execute SQL commands
        cur = self.connection.cursor()

        # Read the SQL file
        with open(SCHEMA_PATH, 'r') as file:
            sql_script = file.read()

        # Execute the SQL script
        cur.executescript(sql_script)

        # Commit the transaction (save changes)
        self.connection.commit()

        # Close the cursor and connection
        cur.close()

    def add_words_to_db(self, word_list: List[Tuple[str, str, int]]) -> None:
        """
        Insert tuples of (word, part-of-speech, frequency) into words table.
        If a combination of (word, pos) already exists in the database,
        only the freq count is updated.

        Args:
            word_list (List[Tuple[str, str, int]]): list of tuples of (word, pos, freq),
                eg. [("Schule", "NOUN", 234), ...]
        """
        cur = self.connection.cursor()
        sql_insert = "INSERT INTO words (word, pos, freq) VALUES (?, ?, ?) ON CONFLICT(word, pos) DO UPDATE SET freq = excluded.freq"
        cur.executemany(sql_insert, word_list)
        self.connection.commit()
        cur.close()
    
    def get_word_by_id(self, word_id: int) -> Optional[LexicalItem]:
        """
        Gets the word from the database by word_id.
        Returns none if the word does not exist.
        """
        cur = self.connection.cursor()
        cur.execute("SELECT word, pos, freq FROM words WHERE id=?", (word_id,))
        word_data = cur.fetchone()

        if word_data:
            item, pos, freq = word_data
            word = LexicalItem(item, pos, freq, word_id)
            return word
        else:
            return None

    def query_first_ten_entries(self, table_name: str) -> None:
        """
        Print first ten entries of table with table_name if table exists.
        If table does not exist, print "table does not exist".

        Args:
            table_name (str): Name of the table to query.
        """
        cur = self.connection.cursor()
        try:
            cur.execute(f"SELECT * FROM {table_name} LIMIT 10")
            rows = cur.fetchall()
            for row in rows:
                print(row)
        except sqlite3.OperationalError:
            print(f"Table '{table_name}' does not exist.")
        finally:
            cur.close()

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
        
        cur = self.connection.cursor()
        try:
            cur.execute("INSERT INTO users (user_name) VALUES (?)", (user_name,))
            self.connection.commit()
            user_id = cur.lastrowid  # Get the ID of the newly inserted row
            return user_id
        except IntegrityError:
            raise ValueError(f"User '{user_name}' already exists in the database.")
        finally:
            cur.close()

    def remove_user(self, user_id: int) -> None:
        """
        # TODO also delete data from the lesson data table
        Remove user with user_id from users table
        and remove all associated rows in learning_data.

        Args:
            user_id (int): ID of the user to remove.
        
        Raises:
            ValueDoesNotExistInDB if the user with user_id does not exist
        """
        cur = self.connection.cursor()
        try:
            cur.execute("DELETE FROM users WHERE id=?", (user_id,))
            if cur.rowcount == 0:
                raise ValueDoesNotExistInDB(f"User with ID {user_id} does not exist.")
            else:
                cur.execute("DELETE FROM learning_data WHERE user_id=?", (user_id,))
                self.connection.commit()
                print(f"User with ID {user_id} removed successfully.")
        finally:
            cur.close()

    def add_word_score(self, user_id: int, score: Score) -> None:
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

        cur = self.connection.cursor()
        # Check for existing user and word entries
        cur.execute("SELECT 1 FROM users WHERE id=?", (user_id,))
        if not cur.fetchone():
            cur.close()
            raise ValueDoesNotExistInDB(f"User with ID {user_id} does not exist.")

        cur.execute("SELECT 1 FROM words WHERE id=?", (score.word_id,))
        if not cur.fetchone():
            cur.close()
            raise ValueDoesNotExistInDB(f"Word with ID {score.word_id} does not exist.")

        # Insert or update the score
        try:
            cur.execute("""
                INSERT INTO learning_data (user_id, word_id, score)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, word_id)
                DO UPDATE SET score = excluded.score
            """, (user_id, score.word_id, score.score))
            self.connection.commit()
            print("Word score added or updated successfully.")
        except IntegrityError as e:
            # Handle any integrity errors
            raise Exception(f"Integrity error occurred: {e}")
        finally:
            cur.close()

    def update_user_scores(self, user_id: int, lesson_scores: Set[Score]) -> None:
        # TODO add timestamp to user scores (either from lesson histor or smt).
        """
        Update user scores for the lesson scores which is a list of scores
        for each word_id. If the word with a score for the user is already in db,
        udpate it, add it otherwise.
        If non existent user - raise ValueDoesNotExistInDB
        If ther eis a word or words that are not in db - raise ValueDoesNotExistInDB
        """
        cur = self.connection.cursor()
        # Verify the user exists
        cur.execute("SELECT id FROM users WHERE id=?", (user_id,))
        if cur.fetchone() is None:
            raise ValueDoesNotExistInDB(f"User with ID {user_id} does not exist.")

        for score in lesson_scores:
            # Verify each word exists
            cur.execute("SELECT id FROM words WHERE id=?", (score.word_id,))
            if cur.fetchone() is None:
                raise ValueDoesNotExistInDB(f"Word with ID {score.word_id} does not exist.")

            # Update or insert the score
            cur.execute("""
                INSERT INTO learning_data (user_id, word_id, score)
                VALUES (?, ?, ?) ON CONFLICT(user_id, word_id)
                DO UPDATE SET score=excluded.score
            """, (user_id, score.word_id, score.score))
        self.connection.commit()

    def retrieve_user_scores(self, user_id: int) -> Set[Score]:
        """
        Retrieves word score data of a user from the learning_data table
        and returnes them as a list of Score.
        Raise ValueDoesNotExistInDB error if non-existent user is requested.
        """
        cur = self.connection.cursor()
        # Verify the user exists
        cur.execute("SELECT id FROM users WHERE id=?", (user_id,))
        if cur.fetchone() is None:
            raise ValueDoesNotExistInDB(f"User with ID {user_id} does not exist.")

        cur.execute("SELECT word_id, score FROM learning_data WHERE user_id=?", (user_id,))
        scores = set([Score(word_id=row[0], score=row[1]) for row in cur.fetchall()])
        return scores

    def save_user_lesson_data(self, user_id: int, lesson_data: List[Evaluation]) -> None:
        """
        Saves user lesson data into the database by saving into user_lessons table,
        adding the evaluations list in order into evaluations table, and saving each history entry
        into the history entries in order, with received scores going to entry_scores table
        """
        cursor = self.connection.cursor()
        try:
            # Insert a new user lesson
            cursor.execute("INSERT INTO user_lessons (user_id) VALUES (?)", (user_id,))
            lesson_id = cursor.lastrowid

            for i, evaluation in enumerate(lesson_data):
                # Insert each evaluation, preserving the order
                cursor.execute("INSERT INTO evaluations (lesson_id, sequence_number) VALUES (?, ?)", (lesson_id, i + 1))
                evaluation_id = cursor.lastrowid

                for j, history in enumerate(evaluation.history):
                    # Insert each history entry
                    cursor.execute("INSERT INTO history_entries (evaluation_id, sequence_number, task_id, response) VALUES (?, ?, ?, ?)",
                                   (evaluation_id, j + 1, history.task.id, history.response))
                    history_entry_id = cursor.lastrowid

                    # Insert scores for each history entry
                    for score in history.evaluation_result:
                        cursor.execute("INSERT INTO entry_scores (history_entry_id, word_id, score) VALUES (?, ?, ?)",
                                       (history_entry_id, score.word_id, score.score))

            # Commit changes
            self.connection.commit()
        except Exception as e:
            # Roll back in case of error
            self.connection.rollback()
            raise e
        finally:
            # Close the cursor
            cursor.close()

    def retrieve_words_for_lesson(self, user_id: int, word_num: int) -> Set[LexicalItem]:
        """
        Retrieves word_num words with highest frequency for which the user
        with user_id does not have scores yet. The words should have pos of either
        NOUN, ADJ or VERB.
        """
        # TODO add mechanism to choose pos
        query = """
            SELECT words.id, words.word, words.pos, words.freq
            FROM words
            LEFT JOIN learning_data ON words.id = learning_data.word_id AND learning_data.user_id = ?
            WHERE learning_data.id IS NULL
            AND words.pos IN ('NOUN', 'ADJ', 'VERB')
            ORDER BY words.freq DESC
            LIMIT ?
        """
        cursor = self.connection.cursor()
        cursor.execute(query, (user_id, word_num))

        # Fetch the results and create a set of LexicalItem objects
        words = set()
        for row in cursor.fetchall():
            index, word, pos, freq = row
            words.add(LexicalItem(item=word, pos=pos, freq=freq, id=index))
        
        return words
    
    """
    METHODS FOR WORKING WITH TEMPLATES
    """
    def get_template_by_id(self, template_id: int) -> Optional[TaskTemplate]:
        """
        Retrieve a template from the database based on its ID.

        Args:
            template_id (int): The ID of the template to retrieve.

        Returns:
            Optional[TaskTemplate]: The retrieved template, or None if not found.
        """
        query = """
            SELECT * 
            FROM templates 
            WHERE id = ?
        """
        cur = self.connection.cursor()
        cur.execute(query, (template_id,))
        template_row = cur.fetchone()

        if template_row:
            # Extract template information from the row
            template = TaskTemplate(
                template_id=template_row[0],
                template_string=template_row[2],
                template_description=template_row[3],
                template_examples=json.loads(template_row[4]),
                parameter_description=self.get_template_parameters(template_id),
                starting_language=getattr(Language, template_row[5]),
                target_language=getattr(Language, template_row[6]),
                task_type=getattr(TaskType, template_row[1])
            )
            return template
        else:
            return None

    def get_template_parameters(self, template_id: int) -> dict:
        """
        Retrieve parameter descriptions for a template from the database.

        Args:
            template_id (int): The ID of the template.

        Returns:
            dict: A dictionary mapping parameter names to descriptions.
        """
        query = """
            SELECT name, description
            FROM template_parameters
            WHERE template_id = ?
        """
        cur = self.connection.cursor()
        cur.execute(query, (template_id,))
        parameter_rows = cur.fetchall()

        parameters = {}
        for row in parameter_rows:
            parameters[row[0]] = row[1]

        return parameters

    def get_templates_by_task_type(self, task_type: TaskType) -> List[TaskTemplate]:
        """
        Retrieve a list of templates from the database based on the task type.

        Args:
            task_type (TaskType): The task type to filter templates.

        Returns:
            List[TaskTemplate]: A list of templates matching the task type, or an empty list if none found.
        """
        query = """
            SELECT * 
            FROM templates 
            WHERE task_type = ?
        """
        cur = self.connection.cursor()
        cur.execute(query, (task_type.name,))  # Pass task_type as a string using its name attribute
        rows = cur.fetchall()

        templates = []
        if rows:
            for template_row in rows:
                # Extract template information from each row and construct TaskTemplate objects
                template = TaskTemplate(
                    template_id=template_row[0],
                    task_type=getattr(TaskType, template_row[1]),
                    template_string=template_row[2],
                    template_description=template_row[3],
                    template_examples=json.loads(template_row[4]),
                    parameter_description=self.get_template_parameters(template_row[0]),
                    starting_language=getattr(Language, template_row[5]),
                    target_language=getattr(Language, template_row[6])
                )
                templates.append(template)

        return templates

    def add_template(
            self,
            template_string: str,
            template_description: str,
            template_examples: List[str],
            parameter_description: Dict[str, str],
            task_type: TaskType,
            starting_language: Language,
            target_language: Language
        ) -> TaskTemplate:
        """
        Adds template to database and returns the new template id.
        If a template with the same name exist, return value error.
        """
        cur = self.connection.cursor()
        try:
            # Insert template into templates table
            cur.execute("""
                INSERT INTO templates (task_type, template, description, examples, starting_language, target_language)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (task_type.name, template_string, template_description, json.dumps(template_examples), starting_language.name, target_language.name))
            template_id = cur.lastrowid

            # Insert template parameters into template_parameters table
            for param_name, param_desc in parameter_description.items():
                cur.execute("""
                    INSERT INTO template_parameters (name, description, template_id)
                    VALUES (?, ?, ?)
                """, (param_name, param_desc, template_id))

            self.connection.commit()
            print("Template added successfully.")
            template = TaskTemplate(
                template_id, 
                target_language,
                starting_language,
                template_string, 
                template_description, 
                template_examples, 
                parameter_description, 
                task_type
            )
            return template
        except Exception as e:
            # Handle any errors
            print(f"Error occurred: {e}")
            self.connection.rollback()
            raise
        finally:
            cur.close()


    def remove_template(template_name: str) -> None:
        """
        Removes template with template_name from the database and ALL
        associated tasks that use this template.
        """

    """
    METHODS FOR WORKING WITH RESOURCES
    """

    def add_resource_manual(self, resource_str: str, target_words: Set[LexicalItem]) -> Resource:
        """
        To be used only when it is known for sure the resource contains
        target words.

        Args:
            resource_str (str): The resource string to add to the database.
            target_words (Set[LexicalItem]): Set of target words contained in the resource.

        Returns:
            Resource: The added resource object.
        """
        cur = self.connection.cursor()
        try:
            # Add resource to the resources table
            cur.execute("INSERT INTO resources (resource_text) VALUES (?)", (resource_str,))
            resource_id = cur.lastrowid

            # Connect resources to words in target_words in resource_words table
            for word in target_words:
                cur.execute("INSERT INTO resource_words (resource_id, word_id) VALUES (?, ?)", (resource_id, word.id))

            self.connection.commit()
            print("Resource added successfully.")

            return Resource(resource_id=resource_id, resource=resource_str, target_words=target_words)
        except IntegrityError as e:
            # Handle any integrity errors
            raise Exception(f"Integrity error occurred: {e}")
        finally:
            cur.close()


    def add_resource_auto(resource_str: str) -> Resource:
        """
        Add resource string as a task and try to match it to
        lemmatized words
        """
        # add to resources table
        # lemmatize using spacy, retrieve lemmas in words table
        # add to resource_words table
        pass

    def remove_resource(self) -> None:
        """
        Removes resource and all associated tasks associated with the resource
        """
        pass

    def get_resource_by_id(self, resource_id: int) -> Resource:
        cur = self.connection.cursor()
        cur.execute("""
                SELECT r.resource_text, w.word, w.pos, w.freq, w.id
                FROM resources r
                INNER JOIN resource_words rw ON r.id = rw.resource_id
                INNER JOIN words w ON rw.word_id = w.id
                WHERE r.id=?
            """, (resource_id,))
        # Fetch the result
        result = cur.fetchall()
        try:
            if result:
                resource_string = result[0][0]
                target_words = {LexicalItem(item=row[1], pos=row[2], freq=row[3], id=row[4]) for row in result}
                resource = Resource(resource_id, resource_string, target_words)
                return resource
            else:
                # If resource is not found, raise an exception or return None
                raise ValueError(f"No resource found with ID {resource_id}")
        finally:
            cur.close()

    def get_resources_by_target_words() -> List[Resource]:
        pass

    """
    METHODS FOR WORKING WITH TASKS
    """
    def add_task(
        self,
        template_id: int,
        resources: Dict[str, Resource],
        target_words: Set[LexicalItem],
        answer: str
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
        cur = self.connection.cursor()
        try:
            # Add task to tasks table
            cur.execute("INSERT INTO tasks (template_id, answer) VALUES (?, ?)", (template_id, answer))
            task_id = cur.lastrowid

            # Find parameters associated with the template
            cur.execute("SELECT id, name FROM template_parameters WHERE template_id = ?", (template_id,))
            template_parameters = {param_name: param_id for param_id, param_name in cur.fetchall()}

            # Connect resources to task and parameters in task_resources table
            for param_name, resource in resources.items():
                if param_name not in template_parameters:
                    raise ValueError(f"No parameter found for '{param_name}' in the template.")

                parameter_id = template_parameters[param_name]
                cur.execute("INSERT INTO task_resources (task_id, resource_id, parameter_id) VALUES (?, ?, ?)",
                            (task_id, resource.resource_id, parameter_id))

            # Connect task to target words in task_target_words table
            for word in target_words:
                cur.execute("INSERT INTO task_target_words (task_id, word_id) VALUES (?, ?)", (task_id, word.id))

            self.connection.commit()
            print("Task added successfully.")

            # Initialize the Task object
            template = self.get_template_by_id(template_id)

            if template.task_type == TaskType.ONE_WAY_TRANSLATION:
                task = OneWayTranslaitonTask(template=template, resources=resources, learning_items=target_words, answer=answer, task_id=task_id)
            else:
                raise Exception("Unknown task type.")
            return task
        except IntegrityError as e:
            # Handle any integrity errors
            raise Exception(f"Integrity error occurred: {e}")
        finally:
            cur.close()

    def get_task_by_id(self, task_id: int) -> Task:
        """
        gets task by id by: 1) getting the template (use get_template_by_id),
        2) retrieve resources from resources, task_resources and template_parameters
        3) combine it all. 
        """
        cur = self.connection.cursor()
        try:
            # Fetch task information from tasks table
            cur.execute("SELECT template_id, answer FROM tasks WHERE id=?", (task_id,))
            task_info = cur.fetchone()
            if not task_info:
                raise ValueError(f"No task found with ID {task_id}")

            template_id, answer = task_info

            # Get the template using template_id
            template = self.get_template_by_id(template_id)
            if not template:
                raise ValueError(f"No template found with ID {template_id}")

            # Retrieve resources associated with the task
            cur.execute("""
                SELECT tr.parameter_id, tr.resource_id
                FROM task_resources tr
                WHERE tr.task_id = ?
            """, (task_id,))
            resource_data = cur.fetchall()

            resources: Dict[str, Resource] = {}
            for parameter_id, resource_id in resource_data:
                parameter_name = self.get_parameter_name_by_id(parameter_id)
                resource = self.get_resource_by_id(resource_id)
                resources[parameter_name] = resource

            # Get target words associated with the task
            cur.execute("""
                SELECT w.word, w.pos, w.freq, w.id
                FROM task_target_words tt
                JOIN words w ON tt.word_id = w.id
                WHERE tt.task_id = ?
            """, (task_id,))
            word_data = cur.fetchall()

            target_words: Set[LexicalItem] = {LexicalItem(*row) for row in word_data}

            # Create the Task object
            if template.task_type == TaskType.ONE_WAY_TRANSLATION:
                task = OneWayTranslaitonTask(template, resources, target_words, answer, task_id)
            else:
                raise Exception("Unknown task type.")
            return task

        finally:
            cur.close()

    def get_parameter_name_by_id(self, parameter_id: int) -> str:
        cur = self.connection.cursor()
        try:
            cur.execute("SELECT name FROM template_parameters WHERE id=?", (parameter_id,))
            result = cur.fetchone()
            if result:
                return result[0]  # Return the parameter name
            else:
                raise ValueError(f"No parameter found with ID {parameter_id}")
        finally:
            cur.close()
    
    def remove_task(task_id: int) -> None:
        """
        Removes task from tasks and task_resources tables.
        """
        pass

    def get_tasks_by_type():
        pass

    def get_tasks_by_template():
        pass

    def get_tasks_for_words(self, target_words: Set[LexicalItem]) -> List[Task]:
        pass

    def fetch_tasks(self, criteria: List) -> List[Task]:
        query = self.compose_query_from_criteria(criteria)
        # Execute the query against the database
        raise NotImplementedError()

    def compose_query_from_criteria(self, criteria: List) -> str:
        # This method should translate the criteria objects into a database query.
        raise NotImplementedError()
    
    def close(self):
        """
        Closes the database connection.
        """
        if self.connection:
            self.connection.close()

DB = DatabaseManager(DATABASE_PATH)