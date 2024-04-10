import unittest
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

if __name__ == "__main__":
    unittest.main()
