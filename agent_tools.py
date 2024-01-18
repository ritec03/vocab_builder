import json
from typing import Callable, Dict, List
from langchain.tools import tool
from chains import word_list_gen_chain, sentence_creation_chain, evaluation_chain


# tool - create vocabulary list
@tool
def generate_vocabulary_list(target_language: str) -> str:
    """This generates a list of ten words (vocabulary list) to be learned by the user
    in a lesson if hte user did not provide their list."""
    return word_list_gen_chain.invoke({"target_language": target_language})

"""
Ideas for exercises:
* multiple choice question.
* a ashort text -> say what the word means.
* createa a sentence with multipel words from the list.

Corrections: if a word is translated incorrectly
* provide a simpler sentence
* provide a definition of a word in the target language

Unified structure for language learning tasks:
* input is a word or a list of words, target language
* output is an evaluation of each of the words
"""

def sentence_translation_practice(word: str, target_langauge: str) -> int:
    # chain for sentence generation
    sentence = sentence_creation_chain.invoke({"input": target_langauge, "word": word})
    # get human input
    print(sentence)
    user_translation = input("Translate this sentence\n")
    # chain for translation evaluation
    # provides json string with these keys:
    # correct_translation, sentence_evaluation, sentence_eval_explanation, word_evaluation, word_eval_explanation
    evaluation = evaluation_chain.invoke(
        {
            "language": target_langauge,
            "target_sentence": sentence["sentence"],
            "translation": sentence["translation"],
            "target_word": word,
        }
    )
    print(json.loads(evaluation)["word_evaluation"])
    # return evaluation of each of the words 
    return json.loads(evaluation)["word_evaluation"]

def inverse_word_translation_practice(word: str, target_langauge: str) -> int:
    """Given a word translation and an example sentence"""
    pass

def single_word_iterator(words: List[str], target_langauge, learning_task: Callable[[str, str], Dict[str, int]]) -> int:
    evaluation = []
    for word in words:
        print("current word ", word)
        word_eval = learning_task(word, target_langauge)
        evaluation.append(word_eval)
    return evaluation


@tool
def perform_vocabulary_practice(user_input: str):
    """Provided a list of words, performs a vocabulary practice session
    on these words.
    
    Example user_input type is a JSON string with schema {words: list[str], target_langauge: str}
    """
    print("Lesson user_input ", user_input)
    user_input: {"words": list[str], "target_language": str} = json.loads(user_input) 
    evaluation = single_word_iterator(user_input["words"], user_input["target_language"], sentence_translation_practice)
    return json.dumps(evaluation)


tools = [generate_vocabulary_list, perform_vocabulary_practice]

# hi, german, generate list, start practice