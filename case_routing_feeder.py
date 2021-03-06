
import os
#os.chdir("/Users/manuel/Documents/SpringML/case-routing/final_scripts")
import pandas as pd
import time
import argparse, datetime, re
from google.cloud import language # pip install --upgrade google-cloud-language
from sklearn.utils import shuffle

GROUP_NAMES = ['Legal', 'AutoResponded', 'Emergencies', 'TechSupport', 'Utilities', 'Sales']

Case_Assignments = {"Legal": ["Charles Anderson", "Robert Heller", "Jane Jackson"],
        "Information": ["Ann Gitlin", "Harrison Davis", "Raj Kumar"],
        "Emergancies": ["Eduardo Sanchez", "Jack Lee", "Sarah Jefferson"],
        "TechSupport": ["Kris Hauser", "Sheryl Thomas", "Yash Patel"],
        "Utilities": ["Mike Camica", "Jose Lopez", "Greg Guniski"],
        "Sales": ["Taylor Traver", "Sam Goldberg", "Jen Kuecks"],
        "Region": ["West", "South", "Midwest", "Northeast"]
}

regions = ["West", "South", "Midwest", "Northeast"]


def clean_text(message_subject, message_content):
    message_subject = re.sub('[^A-Za-z0-9.?!; ]+', ' ', message_subject)
    message_content = re.sub('[^A-Za-z0-9.?!; ]+', ' ', message_content)
    return message_subject, message_content

def get_bag_of_word_counts(message_subject, message_content, word_bags, departments):
 
    text = message_subject + message_content
    text = text.lower()
    # loop through all emails and count group words in each raw text
    words_groups = []
    for group_id in range(len(departments)):
        work_group = []
        top_words = word_bags[group_id]
        # work_group.append(len(set(top_words) & text.split()))
        work_group.append(len([w for w in text.split() if w in set(top_words)]))
        words_groups.append(work_group)
    return words_groups
def get_entity_counts_sentiment_score(message_subject, message_content):
    """Extract entities using google NLP API

    Sentiment analysis inspects the given text and identifies the
    prevailing emotional opinion within the text, especially to
    determine a writer's attitude as positive, negative, or neutral.

    Entity analysis inspects the given text for known entities (Proper
    nouns such as public figures, landmarks, and so on. Common nouns
    such as restaurant, stadium, and so on.) and returns information
    about those entities.

    Args
    text: content of text to feed into API

    Returns:
    entity_count_person, entity_count_location, entity_count_organization,
    entity_count_event, entity_count_work_of_art, entity_count_consumer_good,
    sentiment_score
    """

    text = message_subject + message_content

    client = language.Client()
    document = client.document_from_text(text)


    # Detects sentiment in the document.
    annotations = document.annotate_text(include_sentiment=True,
                                            include_syntax=False,
                                            include_entities=True)

    # get overal text sentiment score
    sentiment_score = annotations.sentiment.score

    # get total counts for each entity found in text
    PERSON = []
    LOCATION = []
    ORGANIZATION = []
    EVENT = []
    WORK_OF_ART = []
    CONSUMER_GOOD = []

    entities_found = []
    for e in annotations.entities:
        entities_found.append(e.entity_type)

    entity_count_person = len([i for i in entities_found if i == 'PERSON'])
    entity_count_location = len([i for i in entities_found if i == 'LOCATION'])
    entity_count_organization = len([i for i in entities_found if i == 'ORGANIZATION'])
    entity_count_event = len([i for i in entities_found if i == 'EVENT'])
    entity_count_work_of_art = len([i for i in entities_found if i == 'WORK_OF_ART'])
    entity_count_consumer_good = len([i for i in entities_found if i == 'CONSUMER_GOOD'])

    return entity_count_person, entity_count_location, entity_count_organization, entity_count_event, entity_count_work_of_art, entity_count_consumer_good, sentiment_score

def get_basic_quantitative_features(message_subject, message_content, message_time):
    """


    Args


    Returns:

    """
    subject_length = len(message_subject)
    subject_word_count = len(message_subject.split())
    content_length = len(message_content)
    content_word_count = len(message_content.split())
    dt = message_time
    is_am = 'no'
    if (dt.time() < datetime.time(12)): is_am = 'yes'
    is_weekday = 'no'
    if (dt.weekday() < 6): is_weekday = 'yes'
    return subject_length, subject_word_count, content_length, content_word_count, is_am, is_weekday

def unpack_word_bags(word_bags_path):
    """ 

    Args:
    word_bags_path: full path and file name to pickle file holding words representing  
    each routing groups
     

    Returns:
 
    """
    import cPickle as pickle
    with open(word_bags_path, 'rb') as handle:
        groups = pickle.load(handle)
 
    return groups

def get_assignee_region(category):
    return random.choice(Case_Assignments[category]), random.choice(regions)

def get_region():
    return random.choice(["West", "South", "Midwest", "Northeast"])

def feature_engineering(subject, content):
    subject, content = clean_text(subject, content)
    word_bags = unpack_word_bags(word_bags_path = args.DATA_PATH)
    words_groups = get_bag_of_word_counts(subject, content, word_bags, GROUP_NAMES)
    entity_count_person, entity_count_location, entity_count_organization, entity_count_event, entity_count_work_of_art, entity_count_consumer_good, sentiment_score = get_entity_counts_sentiment_score(subject, content)
    subject_length, subject_word_count, content_length, content_word_count, is_am, is_weekday = get_basic_quantitative_features(subject, content, sample_request_timestamp)
    
    json_to_submit = {'content_length':content_length,
                'content_word_count':content_word_count,
                'group1':words_groups[0][0],
                'group2':words_groups[1][0],
                'group3':words_groups[2][0],
                'group4':words_groups[3][0],
                'group5':words_groups[4][0],
                'group6':words_groups[5][0],
                'is_am':is_am,
                'is_weekday':is_weekday,
                'subject_length':subject_length,
                'subject_word_count':subject_word_count,
                'nlp_consumer_goods':entity_count_consumer_good,
                'nlp_events':entity_count_event,
                'nlp_locations':entity_count_location,
                'nlp_organizations':entity_count_organization,
                'nlp_persons':entity_count_person,
                'nlp_work_of_arts':entity_count_work_of_art,
                'sentiment_scores':sentiment_score
    }

    return json_to_submit

def get_prediction(json_to_submit):
    service = googleapiclient.discovery.build('ml', 'v1')
    PROJECT = 'emailinsight-1'
    MODEL = 'case_routing_model_v5'
    name = 'projects/{}/models/{}'.format(PROJECT, MODEL)
    response = service.projects().predict(
        name=name,
        body={'instances': [json_to_submit]}
    ).execute()

    return GROUP_NAMES[response['predictions'][0]['classes']]

def feeder():
    case_traffic = pd.read_csv('simulated_case_traffic.csv')
    case_traffic = shuffle(case_traffic)

    SEND_CASE_EVERY_X_SECONDS = 2 # email sent every x seconds


    for index, row in case_traffic.iterrows():
    	subject = row['subject']
    	content = row['content']
        date_created = 
        json_to_submit = feature_engineering(subject, content)
        category = get_prediction(json_to_submit)
        print category
        break

if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description='Arguments for running web server')
    parser.add_argument(
        '--DATA_PATH', required=True, help='Bag of Words Path')
    args = parser.parse_args()
    feeder()
        
	    