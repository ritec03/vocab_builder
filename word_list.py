"""
This script converts sentences from German langauge corpus found
at https://wortschatz.uni-leipzig.de/en/download/German into a lemma frequency
wordlist as well as lemmatized sentences tagged with part-of-speech tags
and saves these resulting dataframes into txt files.
"""
import spacy
import pandas as pd
from collections import defaultdict
from tqdm import tqdm

# Define the file path
file_path = "deu_mixed-typical_2011_100K/deu_mixed-typical_2011_100K-sentences.txt"
# Define the output file path for the frequency DataFrame
word_freq_output_file_path = "word_freq.txt"
# Define the output file path for the lemmatized DataFrame
output_file_path = "german_sentences.txt"

def create_word_list():
    # Load the SpaCy German model
    nlp = spacy.load("de_core_news_md")
    # Create a dictionary to store word frequencies
    word_freq_dict = defaultdict(int)

    # Define a function to lemmatize a sentence and add POS tags
    def lemmatize_sentence(sentence):
        doc = nlp(sentence)
        lemmatized_tokens = [(token.lemma_.lower(),token.pos_) for token in doc]
        for word, pos in lemmatized_tokens:
            if "NUM" not in pos and "SPACE" not in pos and "PUNCT" not in pos and "PROPN" not in pos:
                if f"{word}[{pos}]" in word_freq_dict:
                    word_freq_dict[f"{word}[{pos}]"]["count"] += 1
                else:
                    word_freq_dict[f"{word}[{pos}]"] = {"word": word, "pos": pos, "count": 1}
        lemmatized_sentence = " ".join([f"{word}[{pos}]" for word, pos in lemmatized_tokens])
        return lemmatized_sentence

    tqdm.pandas()
    # Read the tab-separated file into a DataFrame
    df = pd.read_csv(file_path, sep="\t", header=None, names=["Index", "Sentence"])

    # Apply lemmatization to each sentence in the DataFrame
    df["Lemmatized_Sentence"] = df["Sentence"].progress_apply(lemmatize_sentence)

    # Convert the frequency dictionary to a DataFrame
    data_list = [{"word": value["word"], "pos": value["pos"], "count": value["count"]} for key, value in word_freq_dict.items()]
    word_freq_df = pd.DataFrame(data_list)
    print(word_freq_df[word_freq_df["pos"] == "AUX"].head())

    # Sort the DataFrame based on the "count" column in descending order
    word_freq_df = word_freq_df.sort_values(by="count", ascending=False)

    # Reset the index after sorting
    word_freq_df.reset_index(drop=True, inplace=True)

    # Save the frequency DataFrame to a tab-separated text file
    word_freq_df.to_csv(word_freq_output_file_path, sep="\t", index=False)

    # Confirm that the frequency DataFrame has been saved
    print(f"Frequency DataFrame saved to '{word_freq_output_file_path}'.")

    # Save the lemmatized DataFrame to a tab-separated text file
    df.to_csv(output_file_path, sep="\t", index=False)

    # Confirm that the lemmatized DataFrame has been saved
    print(f"Lemmatized DataFrame saved to '{output_file_path}'.")


# Analysis - get top four thousand words
# Generate categories - how?
# Generate levels - how? 
    
# Load the word_freq.txt file into a DataFrame
word_freq_df_loaded = pd.read_csv(word_freq_output_file_path, sep="\t")

def return_unique_pos(word_freq_df):
    # Output a list of unique POS tags
    unique_pos_tags = word_freq_df['pos'].unique()
    print("Unique POS tags:", unique_pos_tags)

return_unique_pos(word_freq_df_loaded)

def count_value_in_column(value: str, column_name: str, dataframe: pd.DataFrame) -> int:
    """
    Count the number of occurrences of a value in a specified column of a DataFrame.

    Parameters:
        value (str): The value to count occurrences of.
        column_name (str): The name of the column to search for the value.
        dataframe (pd.DataFrame): The DataFrame to search in.

    Returns:
        int: The number of times the value appears in the specified column of the DataFrame.
    """
    count = dataframe[column_name].eq(value).sum()
    return count

# Example usage:
# Assuming 'df' is your DataFrame
# Let's count how many times the value 'NOUN' appears in the 'pos' column
filtered_dataframe = word_freq_df_loaded[word_freq_df_loaded["count"] > 1]
for tag in ['DET', 'AUX', 'ADP', 'PRON', 'CCONJ', 'ADV', 'PART', 'VERB', 'ADJ', 'NOUN', 'SCONJ', 'X', 'INTJ']:
    value_count = count_value_in_column(tag, 'pos', filtered_dataframe)
    print(f"Number of times {tag} appears in the 'pos' column:", value_count)


