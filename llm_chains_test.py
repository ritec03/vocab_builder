
from data_structures import LexicalItem, TaskType
from task import AITaskGenerator

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
ai_task_generator = AITaskGenerator()
# resource_dict, answer = ai_task_generator.fetch_or_generate_resources(
#     task_template,
#     target_words
# )
# # print results
# print(resource_dict)
# print(answer)


task = ai_task_generator.create_task(target_words, TaskType.ONE_WAY_TRANSLATION)
print(task.produce_task())