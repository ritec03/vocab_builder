import unittest
from data_structures import Score
from task import Evaluation, HistoryEntry, Task
from task_template import TaskTemplate

class TestTaskTemplate(unittest.TestCase):
    def test_template_id_int(self):
        template = TaskTemplate(1, "template $param1", "description", ["example"], {"param1": "description"})
        self.assertIsInstance(template.id, int)

    def test_template_id_not_int(self):
        with self.assertRaises(ValueError):
            template = TaskTemplate("abc", "template $param1", "description", ["example"], {"param1": "description"})

    def test_template_string_is_empty(self):
        with self.assertRaises(ValueError):
            template = TaskTemplate(1, "", "description", ["example"], {"param1": "description"})

    def test_template_description_empty(self):
        with self.assertRaises(ValueError):
            template = TaskTemplate(1, "template $param1", "", ["example"], {"param1": "description"})

    def test_template_examples_empty_list_with_string(self):
        with self.assertRaises(ValueError):
            template = TaskTemplate(1, "template_template $param1string", "description", [], {"param1": "description"})

    def test_parameter_description_incorrect_number_of_parameters(self):
        with self.assertRaises(ValueError):
            template = TaskTemplate(1, "template $param1 $param2", "description", ["example"], {"param1": "description"})


class TestGetFinalScoresHighest(unittest.TestCase):
    def setUp(self):
        # Initialize an evaluation object
        self.evaluation = Evaluation()

    def test_get_highest_scores(self):
        scores1 = {Score(word_id=1, score=5), Score(word_id=2, score=7)}
        self.evaluation.add_entry(task=None, response='', evaluation_result=scores1)
        scores2 = {Score(word_id=1, score=9), Score(word_id=2, score=3)}
        self.evaluation.add_entry(task=None, response='', evaluation_result=scores2)

        highest_scores = self.evaluation.get_final_scores_highest()
        expected_highest_scores = {Score(word_id=1, score=9), Score(word_id=2, score=7)}
        self.assertEqual(highest_scores, expected_highest_scores)

    def test_get_highest_scores_repeat(self):
        # a score contains two scores for the same word_id
        scores1 = {Score(word_id=1, score=5), Score(word_id=1, score=7)}
        self.evaluation.add_entry(task=None, response='', evaluation_result=scores1)
        scores2 = {Score(word_id=1, score=1), Score(word_id=2, score=3)}
        self.evaluation.add_entry(task=None, response='', evaluation_result=scores2)

        highest_scores = self.evaluation.get_final_scores_highest()
        expected_highest_scores = {Score(word_id=1, score=7), Score(word_id=2, score=3)}
        self.assertEqual(highest_scores, expected_highest_scores)

    def test_get_highest_scores_same_score(self):
        # a score contains two scores for the same word_id
        scores1 = {Score(word_id=1, score=3), Score(word_id=1, score=1)}
        self.evaluation.add_entry(task=None, response='', evaluation_result=scores1)
        scores2 = {Score(word_id=1, score=3), Score(word_id=2, score=3)}
        self.evaluation.add_entry(task=None, response='', evaluation_result=scores2)

        highest_scores = self.evaluation.get_final_scores_highest()
        expected_highest_scores = {Score(word_id=1, score=3), Score(word_id=2, score=3)}
        self.assertEqual(highest_scores, expected_highest_scores)

    def test_case_no_evaluations_performed(self):
        # Case 3: No evaluations performed
        highest_scores = self.evaluation.get_final_scores_highest()
        expected_highest_scores = set()
        self.assertEqual(highest_scores, expected_highest_scores)

    def test_scores_latest(self):
        scores1 = {Score(word_id=1, score=5), Score(word_id=2, score=7)}
        self.evaluation.add_entry(task=None, response='', evaluation_result=scores1)
        scores2 = {Score(word_id=1, score=9), Score(word_id=2, score=3)} # this is latest entry
        self.evaluation.add_entry(task=None, response='', evaluation_result=scores2)

        highest_scores = self.evaluation.get_final_scores_latest()
        expected_highest_scores = {Score(word_id=1, score=9), Score(word_id=2, score=3)}
        self.assertEqual(highest_scores, expected_highest_scores)
        pass

    def test_scores_latest_repeat(self):
        scores1 = {Score(word_id=1, score=5), Score(word_id=2, score=7)}
        self.evaluation.add_entry(task=None, response='', evaluation_result=scores1)
        scores2 = { Score(word_id=2, score=3)} # this is latest entry
        self.evaluation.add_entry(task=None, response='', evaluation_result=scores2)

        highest_scores = self.evaluation.get_final_scores_latest()
        expected_highest_scores = {Score(word_id=1, score=5), Score(word_id=2, score=3)}
        self.assertEqual(highest_scores, expected_highest_scores)
        pass



if __name__ == "__main__":
    unittest.main()
