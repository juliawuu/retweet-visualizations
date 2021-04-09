import datetime
import json
import os
import pathlib

import boto3
import botocore.exceptions
import dateutil.parser as dateparser
import networkx as nx
from networkx.drawing.nx_agraph import graphviz_layout
import requests
import tweepy
import yaml


BEARER_TOKEN = ''   # add bearer token
HEADERS = {'Authorization': 'Bearer {}'.format(BEARER_TOKEN)}


def get_timeline(api, username):
    cursor = tweepy.Cursor(api.search, q='from:{} -filter:retweets'.format(username), tweet_mode='extended')
    tweets = list(cursor.items())
    return [{'Tweet': t.full_text, 'Post Date': t.created_at} for t in tweets]

def rank_by_followers_from_file(retweets):
    retweets.sort(key=lambda x:x['actor']['followersCount'], reverse=True)
    ranked = []
    for rt in retweets:
        ranked.append({'retweeter': rt['actor']['preferredUsername'],
                       'followers': rt['actor']['followersCount']})
    return ranked

def rank_by_followers(retweets):
    retweets.sort(key=lambda x:x.user.followers_count, reverse=True)
    ranked = []
    for rt in retweets:
        ranked.append({'retweeter': rt.user.screen_name,
                       'followers': rt.user.followers_count})
    return ranked

def propagation_time_from_file(retweets, num_users):
    retweets.sort(key=lambda x:dateparser.parse(x['postedTime']))
    propagate_time = dateparser.parse(retweets[min(len(retweets) - 1, num_users)]['postedTime']) - dateparser.parse(retweets[0]['postedTime'])
    days = propagate_time.days
    hours, rem = divmod(propagate_time.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return days, hours, minutes, seconds

def propagation_time(api, num_users, text):
    url = 'https://api.twitter.com/2/tweets/search/recent'
    params = {'query': '(is:retweet OR is:quote) \"' + text + '\"',
              'tweet.fields': 'created_at',
              'max_results': 100}
    r = requests.get(url, headers=HEADERS, params=params)
    retweets = r.json()['data']
    meta = r.json()['meta']
    while 'next_token' in meta:
        params['next_token'] = meta['next_token']
        r = requests.get(url, headers=HEADERS, params=params)
        data = r.json()['data']
        meta = r.json()['meta']
        retweets.extend(data)
    retweets.sort(key=lambda x:x['created_at'])
    propagate_time = dateparser.parse(retweets[min(len(retweets) - 1, num_users)]['created_at']) - dateparser.parse(retweets[0]['created_at'])
    days = propagate_time.days
    hours, r = divmod(propagate_time.seconds, 3600)
    minutes, seconds = divmod(r, 60)
    return days, hours, minutes, seconds

def benchmark(user_id, tweet_id, num_tweets=5):
    url = 'https://api.twitter.com/2/tweets?ids={}&tweet.fields=created_at,public_metrics'.format(tweet_id)
    r = requests.get(url, headers=HEADERS).json()['data'][0]
    benchmark_metrics = {'Tweet': r['text'],
                         'Post Date': r['created_at'],
                         'Retweets': r['public_metrics']['retweet_count'],
                         'Replies': r['public_metrics']['reply_count'],
                         'Likes': r['public_metrics']['like_count']}
    previous_tweets_url = 'https://api.twitter.com/2/users/{}/tweets'.format(user_id)
    params = {'tweet.fields': 'public_metrics,text,created_at', 'max_results': min(100, max(num_tweets, 5)), 'until_id': tweet_id}
    previous_data = requests.get(previous_tweets_url, headers=HEADERS, params=params).json()['data']
    metrics = [benchmark_metrics]
    for tweet in previous_data:
        metrics.append({'Tweet': tweet['text'],
                        'Post Date': tweet['created_at'],
                        'Retweets': tweet['public_metrics']['retweet_count'],
                        'Replies': tweet['public_metrics']['reply_count'],
                        'Likes': tweet['public_metrics']['like_count']})
    return metrics

def get_original_tweet(api, retweets):
    original_tweet_id = retweets[0]['object']['id']
    index = original_tweet_id.rfind(':') + 1
    original_tweet_id = original_tweet_id[index:]
    original_tweet = api.get_status(id=original_tweet_id, tweet_mode='extended')
    return {'text': original_tweet.full_text,
            'author': original_tweet.author.screen_name,
            'created_at': original_tweet.created_at}

def infer_diffusion(simple_cascade, user_id2friends):
    inferred_cascade=[]
    for i in range(1,len(simple_cascade)):
        link_found=False
        for j in range(i-1, -1, -1):
            if simple_cascade[j]['author_id'] in user_id2friends.get(simple_cascade[i]['author_id'],set([])):
                inferred_cascade.append((simple_cascade[j]['tweet_id'], simple_cascade[i]['tweet_id']))
                link_found=True
                break
        if not link_found:
            inferred_cascade.append((simple_cascade[0]['tweet_id'], simple_cascade[i]['tweet_id']))
    return inferred_cascade

def get_friends(api, users):
    user_id2friends = {}
    count = 0
    for u_id in users:
        try:
            cursor = tweepy.Cursor(api.friends_ids, user_id=u_id)
            following = list(cursor.items())
        except tweepy.error.TweepError as e:
            continue
        count += 1
        if count % 100 == 0:
            print(count)
        user_id2friends[u_id] = following
    return user_id2friends

def construct_retweet_cascade_from_file(api, retweets):
    original_tweet_id = retweets[0]['object']['id']
    tweet_index = original_tweet_id.rfind(':') + 1
    original_tweet_id = original_tweet_id[tweet_index:]
    original_created_at = retweets[0]['object']['postedTime']
    original_user_id = retweets[0]['object']['actor']['id']
    user_index = original_user_id.rfind(':') + 1
    original_user_id = original_user_id[user_index:]
    original_tweet = {'tweet_id': original_tweet_id, 'created_at': original_created_at, 'author_id': original_user_id}
    simple_cascade = [original_tweet]
    users = set() # set of all users who have retweeted the original tweet
    for rt in retweets:
        if rt['object']['id'].endswith(original_tweet_id):
            tweet_id_index = rt['id'].rfind(':') + 1
            tweet_id = rt['id'][tweet_id_index:]
            user_id_index = rt['actor']['id'].rfind(':') + 1
            user_id = int(rt['actor']['id'][user_id_index:])
            simple_cascade.append({'tweet_id': tweet_id, 'created_at': rt['postedTime'], 'author_id': user_id})
            users.add(user_id)
    simple_cascade.sort(key=lambda x:dateparser.parse(x['created_at']))

    user_id2friends = get_friends(api, users)

    inferred_cascade = infer_diffusion(simple_cascade, user_id2friends)
    return simple_cascade, inferred_cascade

def construct_retweet_cascade(api, retweets, original_tweet):
    simple_cascade = [original_tweet]
    users = set() # set of all users who have retweeted the original tweet
    for rt in retweets:
        user_id = int(rt['author_id'])
        simple_cascade.append({'tweet_id': rt['id'], 'created_at': rt['created_at'], 'author_id': user_id})
        users.add(user_id)
    simple_cascade.sort(key=lambda x:x['created_at'])

    user_id2friends = get_friends(api, users)

    inferred_cascade = infer_diffusion(simple_cascade, user_id2friends)
    return simple_cascade, inferred_cascade
