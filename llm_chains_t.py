
from typing import List, Tuple
from data_structures import LexicalItem
from exercise import LessonGenerator
import pandas as pd
from database_orm import DB, DatabaseManager

# # create template
# template_string = (
#     "Translate the following into English:\n" +
#     "   '$sentence'"
# )
# task_template = TaskTemplate(
#     template_id=1,
#     template_string=template_string,
#     template_description="description",
#     template_examples=["example one", "example two"],
#     parameter_description={
#         "sentence": "sentence in target language to be translated into english."
#     }
# )       

# choose words
target_words = {LexicalItem(item="erzählen", pos="VERB", freq=100, id=1)}
            
# get generation going
# ai_task_generator = AITaskGenerator()
# resource_dict, answer = ai_task_generator.fetch_or_generate_resources(
#     task_template,
#     target_words
# )
# # print results
# print(resource_dict)
# print(answer)


# task = ai_task_generator.create_task(target_words, TaskType.ONE_WAY_TRANSLATION)
# print(task.produce_task())

# task = TaskFactory().get_task_for_word(target_words)
# print(task.produce_task())

word_freq_output_file_path = "word_freq.txt"
word_freq_df_loaded = pd.read_csv(word_freq_output_file_path, sep="\t")
filtered_dataframe = word_freq_df_loaded[word_freq_df_loaded["count"] > 2]
list_of_tuples: List[Tuple[str, str, int]] = list(filtered_dataframe.to_records(index=False))
# convert numpy.int64 to Python integer
list_of_tuples = [(word, pos, int(freq)) for (word, pos, freq) in list_of_tuples]
DB.add_words_to_db(list_of_tuples)

# create user 
user_id = DB.insert_user("test_user")
print(user_id)
user_id = 1
# generate lesson plan
lesson_generator = LessonGenerator(user_id ,DB)
lesson = lesson_generator.generate_lesson()
# create a test for lesson iteration
lesson.perform_lesson()

