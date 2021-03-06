# -*- coding: utf-8 -*-
import json
import logging
import math

import time
import string
import re
from config import FILEDIR
from stopKeywords import keywords_stoplist

logging.basicConfig(format='%(asctime)s - %(levelname)s : %(message)s', level=logging.INFO)


def tokenizer(text):
    """
    Given an input string, tokenize it into an array of word tokens.
    :param text: (str)
    :return: (list)
    """
    # remove punctuation from text - remove anything that isn't a word char or a space
    replace_punctuation = str.maketrans(string.punctuation, ' ' * len(string.punctuation))
    text = text.translate(replace_punctuation)
    return re.split('\s+', text)


def frequency_table(tokens):
    freq_table = {}
    for token in tokens:
        if token not in keywords_stoplist:
            if token not in freq_table.keys():
                freq_table[token] = 1
            else:
                freq_table[token] += 1
    return freq_table


class DictBuilder:
    """
    Build spam and whitelist keywords lists
    """

    def __init__(self):
        self.category = ""
        self.current_file = ""
        self.tweets = []
        self.count = 0

        # initialize our vocabulary and its size
        self.vocabulary = {}
        self.vocabularySize = 0

        # number of documents we have learned from
        self.totalDocuments = 0

        # document frequency table for each of our categories
        # => for each category, how often were documents mapped to it
        self.docCount = {}

        # for each category, how many words total were mapped to it
        self.wordCount = {}

        # word frequency table for each category
        # => for each category, how frequent was a given word mapped to it
        self.wordFrequencyCount = {}

        # hashmap of our category names
        self.categories = {}

    def retrieve(self):
        logging.info("Retrieving " + self.category + " data...")
        with open(self.current_file) as json_data:
            self.tweets = json.load(json_data)

    def initialize_category(self):
        """
        Initialize each of our data structure entries for this new category
        """
        if self.category not in self.categories.keys():
            self.docCount[self.category] = 0
            self.wordCount[self.category] = 0
            self.wordFrequencyCount[self.category] = {}
            self.categories[self.category] = True

    def learn(self, text):
        self.initialize_category()

        # update our count of how many documents mapped to this category
        self.docCount[self.category] += 1

        # update the total number of documents we have learned from
        self.totalDocuments += 1
        tokens = tokenizer(text)
        freq_table = frequency_table(tokens)

        # update vocabulary and frequency count
        keys = freq_table.keys()
        for token in keys:
            if token not in self.vocabulary.keys():
                self.vocabulary[token] = True
                self.vocabularySize += 1

            freq_in_text = freq_table[token]
            # update the frequency information for this word in this category
            if token not in self.wordFrequencyCount[self.category]:
                self.wordFrequencyCount[self.category][token] = freq_in_text
            else:
                self.wordFrequencyCount[self.category][token] += freq_in_text

            # update the count of all words we have seen mapped to this category
            self.wordCount[self.category] += freq_in_text

    def build(self, category):
        self.category = category
        self.current_file = FILEDIR + "tweets_" + self.category + "2.json"
        start = time.time()
        self.retrieve()
        logging.info("Building " + self.category + " frequency tables...")
        for tweet in self.tweets:
            self.learn(tweet['text'])
        print(self.wordFrequencyCount)
        print(self.wordCount)
        print(self.docCount)
        end = time.time()
        logging.info("Took {0} seconds".format(end - start))

    def build_white_list(self):
        whitelist = []
        info_words = self.wordFrequencyCount["info"].keys()
        spam_words = self.wordFrequencyCount["spam"].keys()
        for word in info_words:
            if self.wordFrequencyCount["info"][word] > 1:
                if word not in spam_words:
                    whitelist.append(word)
        print(whitelist)

    # Calculate probability that a `token` belongs to a `category`
    def token_probability(self, token, category):
        word_freq_count = self.wordFrequencyCount[category][token] | 0
        word_count = self.wordCount[category]
        # use laplace Add-1 Smoothing equation
        return (word_freq_count + 1) / (word_count + self.vocabularySize)

    # def categorize(self, text):
    #     tokens = tokenizer(text)
    #     freq_table = frequency_table(tokens)
    #     # iterate through our categories to find the one with max probability for this text
    #     for category in self.categories.keys():
    #         # start by calculating the overall probability of this category
    #         category_probability = self.docCount[category] / self.totalDocuments
    #         # take the log to avoid underflow
    #         log_probability = math.log(category_probability)
    #         # now determine P( w | c ) for each word `w` in the text
    #         for token in freq_table.keys():
    #             frequency_in_text = freq_table[token]
    #             token_probability = token_probability(token, category)
    #             # determine the log of the P( w | c ) for this word
    #             log_probability += frequency_in_text * math.log(token_probability)


if __name__ == "__main__":
    data = DictBuilder()
    data.build("info")
    data.build("spam")
    data.build_white_list()
