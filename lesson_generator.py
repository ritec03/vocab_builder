from dataclasses import dataclass
import logging
from data_structures import (
    EXERCISE_THRESHOLD,
    NUM_WORDS_PER_LESSON,
    CorrectionStrategy,
    LexicalItem,
    Score,
    UserScore,
)
from database_orm import DatabaseManager, LessonPlan, ValueDoesNotExistInDB
from feedback_strategy import get_strategy_object
from query_builder import QueryCriteria
from task import Task
from task_retriever import TaskFactory
from datetime import datetime
from math import floor

logger = logging.getLogger(__name__)

"""
Strategoes for lesson generator.
Suppose that I have code that does spaced repetition.
Where would the definition of such code be and what responsibilities
would it have and what data would it need?

There is a need to choose:
1. what words to study in a session
2. waht tasks to choose for words
3. what correction strategies to employ
4. how to evaluate user input

Spaced repetition would choose the words that have
higher scores further in advance and those that have lower scores
sooner!
It does not say anything about tasks or correction strategies or evaluation.

However, it seems seems more or less clear that such logic should be 
configured at teh lesson generator level and not anywhere downstream.
* thus configuration should be determiend by the generator, but can
    be provided by an additional module.

"""

@dataclass(frozen=True)
class LessonTargetWord():
    target_word: LexicalItem
    is_review: bool

class SpacedRepetitionLessonGenerator:
    # TODO define the scope of learning algorithm module more vigorously
    # and define which parts are configurable by it (task generation, correction, etc.)
    """
    Generator lesson plan for the user.  Lesson plan is generator as follows:
    * the user learning data is retrieved
    * the user's previous lesson data is retrieved.
    Based on this information a lesson plan is created with tasks,
    error correction strategies and target words.

    Very simple space repetition-esque module to generate the next lesson
    given the user.

    Take the word scores
    Take the time the word was last practiced
    priority is given:
    * words with low scores practiced longest time ago
    * words with low scores practiced not so long ago
    * words with high scores practiced long ago
    * words with high scores practiced not so long ago

    Arrange the words by time practiced
    Go from the beginning (oldest practiced) and pick words with low scores.
    Then if there is space pick high scored words from the beginning.
        * OR add new words.

    Parameters:
    * determining low-high score
    * how many new words to learn
        * learn new words if after picking low scores, plus some high
        scores there is space.

    Question: how to choose tasks in this case? Do i choose old or new tasks?
        * task choice will also be a separate component that can be composed with
            a particular learning strategy.

    """
    score_threshold = EXERCISE_THRESHOLD
    words_per_lesson = NUM_WORDS_PER_LESSON
    num_words_per_lesson = NUM_WORDS_PER_LESSON

    def __init__(self, user_id: int, db_manager: DatabaseManager):
        self.user_id = user_id
        self.db_manager = db_manager

    def generate_lesson(self) -> LessonPlan:
        """
        Returns the first tuple of the lesson plan.
        """
        logger.info("Generating lesson plan.")
        user_word_scores = self.db_manager.get_latest_word_score_for_user(self.user_id)
        logger.info(f"The latest word scores for the user are {user_word_scores}")
        # choose target words
        target_words = self.choose_target_words(user_word_scores)
        # generate lesson plan
        # TODO cannot generate lesson plan with 0 words
        lesson_plan = self.generate_lesson_plan(target_words)
        # return the first tuple in the lesson plan
        return lesson_plan

    def process_scores(
        self, scores: dict[int, UserScore]
    ) -> tuple[dict[datetime, set], dict[datetime, set]]:

        timestamp_low_scores: dict[datetime, set] = {}
        timestamp_high_scores: dict[datetime, set] = {}

        for o in scores.values():
            score = o["score"]
            timestamp = o["timestamp"]
            score_set = (
                timestamp_high_scores
                if score.score >= self.score_threshold
                else timestamp_low_scores
            )
            if timestamp not in score_set:
                score_set[timestamp] = {score}
            else:
                score_set[timestamp].add(score)

        return timestamp_low_scores, timestamp_high_scores

    def get_scores_for_lesson(
        self, timestamp_scores: dict[datetime, set]
    ) -> tuple[list[Score], int, int]:
        len_scores = (
            len(set().union(*timestamp_scores.values())) if timestamp_scores else 0
        )
        scores_for_lesson: list[Score] = []
        if len_scores <= 0:
            return [], len_scores, self.num_words_per_lesson
        timestamps = sorted(timestamp_scores.keys())
        for timestamp in timestamps:
            for score in timestamp_scores[timestamp]:
                if len(scores_for_lesson) < self.num_words_per_lesson:
                    scores_for_lesson.append(score)
                else:
                    break

        leftover_count = self.num_words_per_lesson - len(scores_for_lesson)
        return scores_for_lesson, len_scores, leftover_count

    def choose_target_words(
        self, user_scores: dict[int, UserScore]
    ) -> set[LessonTargetWord]:
        """
        Retrieves the latest score for each practiced word by the user.
        Arrange it by time practiced, then from the oldest words:
        * start choosing words that are below the score_threshold.
            * if the cutoff happens to happen at a timestamp under which multiple
                words fall, choose the appropriate number of words randomly from that set.
        * if there are words left in words_per_lesson count, from the end, start
            choosing words that are equal or above the threshold
            * if the cutoff happens to happen at a timestamp under which multiple
                words fall, choose the appropriate number of words randomly from that set.
        * calculate the amount of new words to learn using method and add appropriate number
            of new words.
        """
        timestamp_low_scores, timestamp_high_scores = self.process_scores(user_scores)
        scores_of_words_to_include_in_lesson: list[Score] = []
        low_scored_to_review, _, leftover_count = self.get_scores_for_lesson(
            timestamp_low_scores
        )
        high_scores_to_select, num_of_all_high_scores, _ = self.get_scores_for_lesson(
            timestamp_high_scores
        )

        num_new_words_to_learn = self.determine_num_of_new_words(
            leftover_count, num_of_all_high_scores
        )
        logger.info(f"The number of new words is {num_new_words_to_learn}")

        scores_of_words_to_include_in_lesson = (
            low_scored_to_review
            + high_scores_to_select[
                : (
                    self.words_per_lesson
                    - len(low_scored_to_review)
                    - num_new_words_to_learn
                )
            ]
        )

        words = [self.db_manager.get_word_by_id(score.word_id) for score in scores_of_words_to_include_in_lesson]
        if any(word is None for word in words):
            raise ValueDoesNotExistInDB(
                "A word object was not found in the database in words for review."
            )

        words_for_review = {
            LessonTargetWord(target_word=word, is_review=True)
            for word in words
        }
        logger.info(
            "Words for review are %s", ", ".join(map(str, list(words_for_review)))
        )

        # Retrieve new words if needed
        if num_new_words_to_learn > 0:
            retrieved_words = self.db_manager.retrieve_words_for_lesson(
                self.user_id, num_new_words_to_learn
            )
            new_words = {LessonTargetWord(target_word=word, is_review=False) for word in retrieved_words}
        else:
            new_words: set[LessonTargetWord] = set()

        logger.info("New words to learn are %s", ", ".join(map(str, list(new_words))))
        words_for_review = words_for_review.union(new_words)
        logger.info(words_for_review)

        # NOTE none of the elements of words_for_review are None since we check it with any()
        return words_for_review

    def determine_num_of_new_words(
        self, leftover_count: int, high_scores_count: int
    ) -> int:
        # BUG bug when the number of learned words is 0 overall.
        """
        This function can be modified
        invariant: should return equal or less than leftover_count
        args:
            leftover_count: num of words remaining to be picked
                after all low score words were picked.
        """
        logger.info(f"Leftover count is {leftover_count} ")
        new_words_num = 0
        if leftover_count <= 1:
            new_words_num = 0

        # if less than quarter, choose half of leftover
        if leftover_count < floor(self.num_words_per_lesson / 4):
            new_words_num = floor(leftover_count / 2)
        # if less than half, choose third of leftover:
        elif leftover_count >= floor(
            self.num_words_per_lesson / 4
        ) and leftover_count < floor(self.num_words_per_lesson / 2):
            new_words_num = floor(leftover_count / 3)
        # else choose quarter
        else:
            new_words_num = floor(leftover_count / 4)

        logger.info(f"The number of new words is {new_words_num}")
        return (
            new_words_num
            if high_scores_count >= leftover_count - new_words_num
            else leftover_count - high_scores_count
        )

    def generate_lesson_plan(
        self, words: set[LessonTargetWord]
    ) -> LessonPlan:
        """
        Generates lesson plan for the user based on the targetwords.
        Returns the lesson plan which is a list of tuples, where each tuple
        has the task and a list of correction tasks or strategies if tasks are not available.
        """
        # TODO do not allow empty word sets as input
        # NOTE create a dummy plan by using one-word items only for now
        # NOTE for now create lesson task which partitions target words without overlaps, i.e.
        # a target word is targeted by one task only
        # TODO think about how to do it.
        task_factory = TaskFactory(self.db_manager, self.user_id)
        lesson_plan: LessonPlan = []
        # TODO devise a strategy of choosing correction strategy.
        # TODO test api with correction strategies too.
        strategy_sequence = [
            # CorrectionStrategy.EquivalentTaskStrategy,
            # CorrectionStrategy.EquivalentTaskStrategy,
            # CorrectionStrategy.EquivalentTaskStrategy
        ]
        for word in list(words):
            lesson_task_ids = self._get_task_ids_for_lesson_plan(lesson_plan)
            if word.is_review:
                task = task_factory.get_task_for_word(
                    QueryCriteria(
                        doneByUser=True, 
                        target_words={word.target_word}, 
                        excluded_task_ids=lesson_task_ids
                    )
                )
            else:
                task = task_factory.get_task_for_word(
                    QueryCriteria(
                        doneByUser=False, 
                        target_words={word.target_word}, 
                        excluded_task_ids=lesson_task_ids
                    )
                )
            logger.info(f"Added task with id {task.id} for word {word.target_word.item}")
            task_sequence: list[Task | CorrectionStrategy] = [task]
            # generate strategy sequence tasks
            for strategy in strategy_sequence:
                strategy_class = get_strategy_object(strategy)
                strategy_obj = strategy_class(self.db_manager, self.user_id)
                task_or_strategy = strategy_obj.try_generate_task_in_advance(
                    task_sequence
                )
                task_sequence.append(task_or_strategy)

            lesson_plan.append((task, task_sequence[1:]))
        if not lesson_plan[0][0]:  # NOTE maybe emits error
            logger.warning("Lesson plan is empty.")
        return lesson_plan
    
    def _get_task_ids_for_lesson_plan(self, lesson_plan: LessonPlan) -> set[int]:
        """
        Retrieves the task IDs for a given lesson plan.

        Args:
            lesson_plan (LessonPlan): The lesson plan to retrieve task IDs from.

        Returns:
            set[int]: A set of task IDs.

        """
        lesson_task_ids = {task.id for _, tasks in lesson_plan for task in tasks if isinstance(task, Task)}
        lesson_task_ids.union({task.id for task, _ in lesson_plan})
        return lesson_task_ids
