import unittest
from sqlalchemy import select
from data_structures import MAX_SCORE, NUM_WORDS_PER_LESSON, Score, TaskType
from database_objects import TaskDBObj
from database_orm import DatabaseManager, ExpandedScore, Order
from app_factory import create_app
from database_orm_test import session_manager
from evaluation import HistoryEntry
from lesson_generator import SpacedRepetitionLessonGenerator
from lesson_task import LessonTask
from query_builder import QueryCriteria
from task import Task
from unittest.mock import patch

"""
Set up database manager.
Create three users.
For each user, create example lesson data and incorporate it into the database.

Test query_builder function
"""

class QueryBuilderTest(unittest.TestCase):
    def setUp(self):
        # Set up database manager
        DatabaseManager(None)
        # Create app
        self.app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
        self.db_manager: DatabaseManager = self.app.db_manager # type: ignore
        with session_manager(self.db_manager):
            self.db_manager._prepopulate_db()

        with self.db_manager.Session() as session:
            self.all_tasks = session.execute(
                select(TaskDBObj)
            ).all()

    # closure for patching the evaluate_task method of LessonTask
    def make_evaluate_task_patch(self, user_id: int, lesson_id: int, task: Task, scores: set[Score]):
        def evaluate_task_patch(answer: str, task_id: int, order: Order) -> HistoryEntry:
            history_entry = HistoryEntry(task, answer, set(scores))
            self.db_manager.save_evaluation_for_task(
                user_id, lesson_id, order, history_entry
            )
            return history_entry
        return evaluate_task_patch

    def create_example_lesson(
            self, user_id: int, 
            partial_scores: list[int] | int
        ) -> tuple[list[Task], list[ExpandedScore]]:
        if isinstance(partial_scores, int):
            partial_scores = [partial_scores] * NUM_WORDS_PER_LESSON

        lesson_generator = SpacedRepetitionLessonGenerator(user_id, self.db_manager)
        lesson = lesson_generator.generate_lesson()
        lesson_head = self.db_manager.save_lesson_plan(user_id, lesson)
        lesson_task_ids = [task.id for task, _ in lesson]
        lesson_id = lesson_head['lesson_id']

        completed_tasks: list[Task] = []

        # NOTE for now ignore correction tasks
        for i, [task, correction_list] in enumerate(lesson):
            lesson_task = LessonTask(user_id, self.db_manager, lesson_id)
            # Patch the evaluate_task method of LessonTask with a closure
            # TODO repatch at Task level.
            scores = {Score(word.id, partial_scores[i]) for word in task.learning_items}
            with patch.object(
                LessonTask, 
                'evaluate_task', 
                side_effect=self.make_evaluate_task_patch(user_id, lesson_id, task, scores)
            ):
                history_entry = lesson_task.evaluate_task("answer", task.id, Order(i,0))
                completed_tasks.append(task)

        # connect final scores with tasks
        final_scores = self.db_manager.finish_lesson(user_id, lesson_id)
        return completed_tasks, final_scores

    def test_query_builder_done_by_user(self):
        user_1_id = self.db_manager.insert_user("User 1")
        # do a perfect lesson
        completed_tasks, _ = self.create_example_lesson(user_1_id, MAX_SCORE)
        # create another lesson
        criteria = QueryCriteria(doneByUser=True)
        chosen_tasks = self.db_manager.get_tasks_by_criteria(user_1_id, criteria, 100)

        result = all(task_id in [t.id for t in completed_tasks] for task_id in [t.id for t in chosen_tasks])
        # check that all tasks are done by user.
        self.assertTrue(result)

    def test_query_builder_not_done_by_user(self):
        user_1_id = self.db_manager.insert_user("User 1")
        # do a perfect lesson
        completed_tasks, _ = self.create_example_lesson(user_1_id, MAX_SCORE)
        # create another lesson
        criteria = QueryCriteria(doneByUser=False)
        chosen_tasks = self.db_manager.get_tasks_by_criteria(user_1_id, criteria, 100)

        completed_tasks_ids = {t.id for t in completed_tasks}
        chosen_tasks_ids = {t.id for t in chosen_tasks}

        self.assertTrue(completed_tasks_ids.isdisjoint(chosen_tasks_ids))

    def test_query_builder_min_score_no_tasks(self):
        user_1_id = self.db_manager.insert_user("User 1")
        # do a perfect lesson
        score = 1
        completed_tasks, _ = self.create_example_lesson(user_1_id, score)
        # have some target words
        target_words = set().union(*[t.learning_items for t in completed_tasks])
        criteria = QueryCriteria(minScore=score+1, target_words=target_words)
        chosen_tasks = self.db_manager.get_tasks_by_criteria(user_1_id, criteria, 100)

        self.assertTrue(not chosen_tasks)

    def test_query_builder_min_score_some_tasks(self):
        user_1_id = self.db_manager.insert_user("User 1")
        # do a perfect lesson
        score = 5
        completed_tasks, final_scores = self.create_example_lesson(user_1_id, score)
        # have some target words
        target_words = set().union(*[t.learning_items for t in completed_tasks])
        criteria = QueryCriteria(minScore=score, target_words=target_words)
        chosen_tasks = self.db_manager.get_tasks_by_criteria(user_1_id, criteria, 100)

        completed_tasks_ids = [t.id for t in completed_tasks]
        chosen_tasks_ids = [t.id for t in chosen_tasks]
        # check that all tasks are done by user.
        self.assertTrue(sorted(completed_tasks_ids) == sorted(chosen_tasks_ids))

    def test_query_builder_max_score_no_tasks(self):
        user_1_id = self.db_manager.insert_user("User 1")
        # do a perfect lesson
        score = MAX_SCORE
        completed_tasks, _ = self.create_example_lesson(user_1_id, score)

        # remove non-completed tasks so that they don't get included into max score set
        # with self.db_manager.Session() as session:
        #     non_completed_tasks = session.scalars(
        #         select(TaskDBObj).where(~TaskDBObj.lesson_plan_tasks.any())
        #     ).all()
        #     non_completed_task_ids = [t.id for t in non_completed_tasks]
        #     [self.db_manager.remove_task(task_id) for task_id in non_completed_task_ids]
        
        # have some target words
        target_words = set().union(*[t.learning_items for t in completed_tasks])
        criteria = QueryCriteria(maxScore=score-1, target_words=target_words)
        chosen_tasks = self.db_manager.get_tasks_by_criteria(user_1_id, criteria, 100)

        self.assertTrue(not chosen_tasks)

    def test_query_builder_max_score_some_tasks(self):
        user_1_id = self.db_manager.insert_user("User 1")
        max_score = MAX_SCORE
        lower_score = MAX_SCORE - 1
        # do a perfect lesson
        scores = [max_score, lower_score, lower_score, lower_score, max_score]
        completed_tasks, final_scores = self.create_example_lesson(user_1_id, scores)
        
        # have some target words
        target_words = set().union(*[t.learning_items for t in completed_tasks])
        criteria = QueryCriteria(maxScore=lower_score, target_words=target_words)
        chosen_tasks = self.db_manager.get_tasks_by_criteria(user_1_id, criteria, 100)

        self.assertEqual(len(chosen_tasks), 3)
        self.assertEqual(
            set().union(*[t.learning_items for t in chosen_tasks]),
            {score["word"] for score in final_scores if score["score"] == lower_score }
        )

    def test_query_builder_task_type(self):
        user_1_id = self.db_manager.insert_user("User 1")
        # do a perfect lesson
        criteria = QueryCriteria(taskType=TaskType.ONE_WAY_TRANSLATION)
        chosen_tasks = self.db_manager.get_tasks_by_criteria(user_1_id, criteria, 100)

        self.assertTrue(all(t.template.task_type == TaskType.ONE_WAY_TRANSLATION for t in chosen_tasks))

    def test_query_builder_target_words(self):
        user_1_id = self.db_manager.insert_user("User 1")
        # do a perfect lesson
        score = 5
        completed_tasks, final_scores = self.create_example_lesson(user_1_id, score)
        # have some target words
        target_words = set().union(*[t.learning_items for t in completed_tasks])
        chosen_tasks: list[Task] = []
        for word in target_words:
            criteria = QueryCriteria(target_words={word})
            chosen_tasks.extend(self.db_manager.get_tasks_by_criteria(user_1_id, criteria, 100))
        target_words_chosen = set().union(*[t.learning_items for t in chosen_tasks])

        self.assertEqual(
            set().union(*[t.learning_items for t in chosen_tasks]),
            target_words
        )
    
    def test_query_builder_excluded_tasks_no_tasks(self):
        # test that if excluded task id criteria is used, the task with that id is not returned
        user_1_id = self.db_manager.insert_user("User 1")
        # get three random tasks
        random_tasks = self.db_manager.get_tasks_by_criteria(user_1_id, QueryCriteria(), len(self.all_tasks))
        random_tasks_ids = {task.id for task in random_tasks}

        chosen_tasks = self.db_manager.get_tasks_by_criteria(user_1_id, QueryCriteria(excluded_task_ids=random_tasks_ids), 100)
        chosen_tasks_ids = {task.id for task in chosen_tasks}
        # check that none of the tasks are in the chosen tasks
        self.assertTrue(not chosen_tasks_ids)

    def test_query_builder_excluded_tasks_some_tasks(self):
        # test that if excluded task id criteria is used, the task with that id is not returned
        user_1_id = self.db_manager.insert_user("User 1")
        # get three random tasks
        random_tasks = self.db_manager.get_tasks_by_criteria(user_1_id, QueryCriteria(), 3)
        random_tasks_ids = {task.id for task in random_tasks}

        chosen_tasks = self.db_manager.get_tasks_by_criteria(user_1_id, QueryCriteria(excluded_task_ids=random_tasks_ids), 100)
        chosen_tasks_ids = {task.id for task in chosen_tasks}
        # check that none of the tasks are in the chosen tasks
        self.assertTrue(random_tasks_ids.isdisjoint(chosen_tasks_ids))
        

if __name__ == '__main__':
    unittest.main()