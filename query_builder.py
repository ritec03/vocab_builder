from sqlalchemy import Select, and_, func, select
from sqlalchemy import select
from data_structures import LexicalItem, TaskType
from database_objects import (
    EntryScoreDBObj,
    EvaluationDBObj,
    HistoryEntrieDBObj,
    LessonPlanDBObj,
    LessonPlanTaskDBObj,
    TaskDBObj,
    TaskTargetWordDBObj,
    TemplateDBObj,
    UserLessonDBObj,
)


class QueryCriteria:
    def __init__(
        self,
        doneByUser: bool | None = None,
        minScore: int | None = None,
        maxScore: int | None = None,
        taskType: TaskType | None = None,
        target_words: set[LexicalItem] | None = None,
    ):
        """
        max/min scores apply to all target words and only taken into account
        if there are target words.

        If there is max score, then only tasks with score <= max score and 
        tasks not scored yet are returned.

        If there is min score, then only tasks with score >= min score are returned.
        """
        self.doneByUser = doneByUser
        self.minScore = minScore
        self.maxScore = maxScore
        self.taskType = taskType
        self.target_words = target_words


class QueryBuilder:
    def _apply_done_by_user(
        self, stmt: Select, user_id: int, done_by_user: bool
    ) -> Select:
        if done_by_user:
            stmt = stmt.where(
                TaskDBObj.lesson_plan_tasks.any(
                    and_(
                        LessonPlanTaskDBObj.completed == True,
                        LessonPlanTaskDBObj.lesson_plan.has(
                            UserLessonDBObj.user_id == user_id
                        ),
                    )
                )
            )
        else:
            stmt = stmt.where(
                ~TaskDBObj.lesson_plan_tasks.any(LessonPlanTaskDBObj.completed == True)
            )

        return stmt

    def _apply_score_criteria(
        self, stmt: Select, minScore: int | None, maxScore: int | None, user_id: int
    ) -> Select:
        if minScore is not None and maxScore is not None:
            condition = and_(EntryScoreDBObj.score >= minScore, EntryScoreDBObj.score <= maxScore)
        elif maxScore is not None:
            condition = (EntryScoreDBObj.score <= maxScore)
        else:
            condition = (EntryScoreDBObj.score >= minScore)

        # (HistoryEntrie.task_id - where EntryScore.score > minScore and/or EntryScore.score < maxScore)
        # inner joined on HistoryEntrie.evaluation_id -- Evaluation.lesson_id -- UserLesson.user_id
        # BUG what if tasks have multiple target words and thus scores? How should i define min/max score
        stmt = select(TaskDBObj).where(
            TaskDBObj.lesson_plan_tasks.any(
                LessonPlanTaskDBObj.lesson_plan.has(
                    LessonPlanDBObj.lesson.has(
                        and_(
                            UserLessonDBObj.evaluations.any(
                                EvaluationDBObj.history_entries.any(
                                    and_(
                                        HistoryEntrieDBObj.scores.any(
                                            condition
                                        ),
                                        HistoryEntrieDBObj.task_id == TaskDBObj.id
                                    )
                                ),
                            ),
                            # UserLessonDBObj.user_id == user_id
                        )
                    )
                )
            )
        )

        return stmt

    def _apply_target_words_criteria(
        self, stmt: Select, target_words: set[LexicalItem]
    ) -> Select:
        target_word_ids = [word.id for word in target_words]
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
        stmt = stmt.where(TaskDBObj.id.in_(select(task_ids_subquery)))

        return stmt

    def build_query(
        self, user_id: int, criteria: QueryCriteria
    ) -> Select[tuple[TaskDBObj]]:
        """
        If only non-user specific criteria used, then query starting on taskdbobj
        """
        stmt = select(TaskDBObj)
        if criteria.taskType is not None:
            stmt = stmt.where(
                TaskDBObj.template.has(TemplateDBObj.task_type == criteria.taskType.name)
            )

        if criteria.target_words is not None:
            stmt = self._apply_target_words_criteria(stmt, criteria.target_words)

        if criteria.doneByUser is not None:
            stmt = self._apply_done_by_user(stmt, user_id, criteria.doneByUser)

        if criteria.minScore is not None or criteria.maxScore is not None:
            stmt = self._apply_score_criteria(
                stmt, criteria.minScore, criteria.maxScore, user_id
            )

        return stmt
