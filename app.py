import base64
import json
import os
import pathlib
import re

import boto3
import botocore.exceptions
import dash
import dash_bootstrap_components as dbc
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
import dash_table
import emoji
import matplotlib.pyplot as plt
import networkx as nx
from networkx.drawing.nx_agraph import graphviz_layout
import plotly.graph_objs as go
import tweepy
import yaml

from tweet_stats import *


BEARER_TOKEN = 'AAAAAAAAAAAAAAAAAAAAABDqLgEAAAAAt6lwdR6KoXfai3ARtSEeadyp44k%3DNHwq0XVKHxiRwymPkL7L0SQ4pn30FLwZrLRlbg2bJZYWlljWDE'
HEADERS = {'Authorization': 'Bearer {}'.format(BEARER_TOKEN)}
OLDER_TWEETS = {'kerrywashington': ['1351210811574906897', '1351314103902453762',
                                    '1351708601648254981', '1351708605179809792',
                                    '1351917962744066054', '1351939067370381313',
                                    '1351943779717062656', '1351983569829154817',
                                    '1352140446403751937', '1352376698830905346']}

external_stylesheets = [dbc.themes.COSMO]

app = dash.Dash(__name__, external_stylesheets=external_stylesheets, suppress_callback_exceptions=True)

SIDEBAR_STYLE = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "bottom": 0,
    "width": "20rem",
    "padding": "2rem 1rem",
    "background-color": "#f5faff",
    "font-size": 20
}

CONTENT_STYLE = {
    "margin-left": "30rem",
    "margin-right": "10rem",
    "padding": "2rem 1rem",
    "font-size": 14
}

sidebar = html.Div(
    [
        html.H2("Navigation", className="display-4"),
        html.Hr(),
        dbc.Nav(
            [
                dbc.NavLink("Overview", href="/", active="exact"),
                dbc.NavLink("Page 1", href="/page-1", active="exact"),
                dbc.NavLink("Page 2", href="/page-2", active="exact"),
            ],
            vertical=True,
            pills=True,
        ),
    ],
    style=SIDEBAR_STYLE,
)

content = html.Div(id="page-content", style=CONTENT_STYLE)

app.layout = html.Div([dcc.Location(id="url"), sidebar, content])

home_page = html.Div([
    html.Div(['Twitter username: ',
              dcc.Input(id='twitter-username', value='', type='text', debounce=True)], style={'font-size': 15}),
    html.Div(['Press enter to submit']),
    html.Br(),
    html.H2('Dashboard', style={'font-size': 34}),
    dbc.Tabs([
        dbc.Tab(label='Quick Stats', children=[
            html.Br(),
            html.Div(id='output-twitter-timeline'),
            html.Br(),
            html.Div(id='new-propagation-output', style={'width': '30%', 'display': 'inline-block'}),
            html.Div(id='new-benchmark-output', style={'width': '66%', 'display': 'inline-block', 'margin-left': '3rem'}),
            html.Br(),
            html.Div(id='new-ranking', style={'width': '20%', 'display': 'inline-block'}),
            # html.Div(id='new-retweet-cascade', style={'width': '80%', 'display': 'inline-block'}),
            html.Br(),
            html.Div(id='tweet-dropdown'),
            html.Div(id='older-tweet-selected'),
            html.Br(),
            html.Div(id='old-propagation-output', style={'width': '30%', 'display': 'inline-block'}),
            html.Div(id='old-benchmark-output', style={'width': '66%', 'display': 'inline-block', 'margin-left': '3rem'}),
            html.Br(),
            html.Div(id='old-ranking', style={'width': '20%', 'display': 'inline-block'}),
        ], active_label_style={
            'color': '#3d8ddf'
        }, label_style={
            'color': '#84c1ff',
        }, tab_style={
            'border-radius': '0rem'
        }),
        dbc.Tab(label='Insights', children=[
            html.Br(),
            html.Div(id='output-twitter-timeline-2'),
            html.Br(),
            html.Div(id='new-retweet-cascade', style={'width': '100%', 'display': 'inline-block'}),
            html.Br(),
            html.Div(id='tweet-dropdown-2'),
            html.Div(id='older-tweet-selected-2'),
            html.Br(),
            html.Div(id='old-retweet-cascade', style={'width': '100%', 'display': 'inline-block'})
        ], active_label_style={
            'color': '#3d8ddf'
            # 'fontWeight': 'bold'
        }, label_style={
            'color': '#84c1ff',
        }, tab_style={
            'border-radius': 0
        })
    ], style={
        'font-size': 20
    })
])


@app.callback(Output("page-content", "children"), [Input("url", "pathname")])
def render_page_content(pathname):
    if pathname == "/":
        return home_page
    elif pathname == "/page-1":
        return html.P("filler")
    elif pathname == "/page-2":
        return html.P("filler")
    # If the user tries to reach a different page, return a 404 message
    return dbc.Jumbotron(
        [
            html.H1("404: Not found", className="text-danger"),
            html.Hr(),
            html.P(f"The pathname {pathname} was not recognised..."),
        ]
    )


@app.callback(Output('tweet-dropdown', 'children'),
              Input('twitter-username', 'value'))
def get_older_tweets(username):
    if username != '':
        dropdown_tweet_ids = OLDER_TWEETS.get(username, [])
        api = get_twitter_api()
        dropdown_tweets = []
        for id in dropdown_tweet_ids:
            tweet = api.get_status(id=id, tweet_mode='extended').full_text
            dropdown_tweets.append({'label': tweet, 'value': id})
        return [html.Hr(),
                html.H6('Older tweets by @{}'.format(username), style={'font-size': 20}),
                dcc.Dropdown(id='tweet-options', options=dropdown_tweets),
                html.Br()]

@app.callback(Output('older-tweet-selected', 'children'),
              Input('tweet-options', 'value'))
def display_tweet(tweet_id):
    if tweet_id:
        api = get_twitter_api()
        tweet = api.get_status(id=tweet_id, tweet_mode='extended')
        selected_tweet = {'tweet': tweet.full_text, 'created_at': tweet.created_at}
        return [html.Div('Tweet selected:'),
                html.Div([
                    dash_table.DataTable(
                        style_cell={
                            'whiteSpace': 'normal',
                            'height': 'auto',
                            'textAlign': 'left'
                        },
                        style_cell_conditional=[
                            {'if': {'column_id': 'tweet'},
                             'width': '70%'}
                        ],
                        data=[selected_tweet],
                        columns=[{'name': i, 'id': i} for i in [k for k in selected_tweet.keys()]],
                    )
                ]),
                html.Br(),
                html.Div(["Find propagation time for x users: ",
                          dcc.Input(id='old-propagation-input', value='', type='text')],
                          style={'width': '40%', 'display': 'inline-block'}),
                html.Div(["Benchmark against previous x tweets: ",
                          dcc.Input(id='old-benchmark-input', value='', type='text')],
                          style={'width': '40%', 'display': 'inline-block'})]

@app.callback(Output('tweet-dropdown-2', 'children'),
              Input('twitter-username', 'value'))
def get_older_tweets_2(username):
    if username != '':
        dropdown_tweet_ids = OLDER_TWEETS.get(username, [])
        api = get_twitter_api()
        dropdown_tweets = []
        for id in dropdown_tweet_ids:
            tweet = api.get_status(id=id, tweet_mode='extended').full_text
            dropdown_tweets.append({'label': tweet, 'value': id})
        # dropdown_tweets = [{'label': api.get_status(id=id, tweet_mode='extended').full_text} for id in dropdown_tweet_ids]
        return [html.Hr(),
                html.H6('Older tweets by @{}'.format(username), style={'font-size': 20}),
                dcc.Dropdown(id='tweet-options-2', options=dropdown_tweets),
                html.Br()]

@app.callback(Output('older-tweet-selected-2', 'children'),
              Input('tweet-options-2', 'value'))
def display_tweet_2(tweet_id):
    if tweet_id:
        api = get_twitter_api()
        tweet = api.get_status(id=tweet_id, tweet_mode='extended')
        selected_tweet = {'tweet': tweet.full_text, 'created_at': tweet.created_at}
        return [html.Div('Tweet selected:'),
                html.Div([
                    dash_table.DataTable(
                        style_cell={
                            'whiteSpace': 'normal',
                            'height': 'auto',
                            'textAlign': 'left'
                        },
                        style_cell_conditional=[
                            {'if': {'column_id': 'tweet'},
                             'width': '70%'}
                        ],
                        data=[selected_tweet],
                        columns=[{'name': i, 'id': i} for i in [k for k in selected_tweet.keys()]],
                    )
                ])]

@app.callback(Output('output-twitter-timeline', 'children'),
              Input('twitter-username', 'value'))
def update_timeline(username):
    if username != '':
        api = get_twitter_api()
        tweets = get_timeline(api, username)
        return [html.H6('Tweets by @{} from the past 7 days'.format(username), style={'font-size': 20}),
                html.Div([
                    dash_table.DataTable(
                        id='timeline',
                        style_cell={
                            'whiteSpace': 'normal',
                            'height': 'auto',
                            'textAlign': 'left'
                        },
                        style_cell_conditional=[
                            {'if': {'column_id': 'Tweet'},
                             'width': '70%'}
                        ],
                        data=tweets,
                        columns=[{'name': i, 'id': i} for i in [k for k in tweets[0].keys()]],
                        page_size=15,
                        row_selectable='single',
                        selected_rows=[]
                    )
                ]),
                html.Br(),
                html.Div(["Find propagation time for x users: ",
                          dcc.Input(id='new-propagation-input', value='', type='text')],
                          style={'width': '40%', 'display': 'inline-block'}),
                html.Div(["Benchmark against previous x tweets: ",
                          dcc.Input(id='new-benchmark-input', value='', type='text')],
                          style={'width': '40%', 'display': 'inline-block'})]

@app.callback(Output('output-twitter-timeline-2', 'children'),
              Input('twitter-username', 'value'))
def update_timeline_2(username):
    if username != '':
        api = get_twitter_api()
        tweets = get_timeline(api, username)
        return [html.H6('Tweets by @{} from the past 7 days'.format(username), style={'font-size': 20}),
                html.Div([
                    dash_table.DataTable(
                        id='timeline-2',
                        style_cell={
                            'whiteSpace': 'normal',
                            'height': 'auto',
                            'textAlign': 'left'
                        },
                        style_cell_conditional=[
                            {'if': {'column_id': 'Tweet'},
                             'width': '70%'}
                        ],
                        data=tweets,
                        columns=[{'name': i, 'id': i} for i in [k for k in tweets[0].keys()]],
                        page_size=15,
                        row_selectable='single',
                        selected_rows=[]
                    )
                ])]

def get_ranking(ranking):
    return [html.Br(),
            html.Label('Retweeters Ranked By Followers'),
            html.Div([
            dash_table.DataTable(
                style_cell={
                    'whiteSpace': 'normal',
                    'height': 'auto',
                    'textAlign': 'left'
                },
                style_cell_conditional=[
                    {'if': {'column_id': 'retweeter'},
                     'width': '60%'}
                ],
                data=ranking,
                columns=[{'name': i, 'id': i} for i in [k for k in ranking[0].keys()]],
                page_size=15
            )
        ])]

@app.callback(Output('old-ranking', 'children'),
              Input('tweet-options', 'value'))
def update_ranking_old(tweet_id):
    if tweet_id:
        filename = '../tweets/' + tweet_id + '.json'
        with open(filename, 'r') as f:
            retweets = json.load(f)
        ranking = rank_by_followers_from_file(retweets)
        return get_ranking(ranking)

@app.callback(Output('new-ranking', 'children'),
              Input('timeline', 'selected_rows'),
              Input('timeline', 'data'))
def update_ranking(selected_rows, data):
    if selected_rows:
        row = selected_rows[0]
        text = data[row]['Tweet']
        # api = get_twitter_api()
        # cursor = tweepy.Cursor(api.search, q='{} filter:retweets'.format(text))
        text = re.sub('http[^\s]+', '', text)
        text = re.sub('&[^\s]*', '', text)
        text = re.sub('[\s]+', ' ', text)
        text = emoji.get_emoji_regexp().sub('', text)
        url = 'https://api.twitter.com/2/tweets/search/recent'
        params = {'query': '(is:retweet OR is:quote) \"' + text + '\"',
                  'expansions': 'author_id',
                  'user.fields': 'public_metrics',
                  'max_results': 100}
        r = requests.get(url, headers=HEADERS, params=params)
        meta = r.json()['meta']
        retweeters = r.json()['includes']['users']
        while 'next_token' in meta:
            params['next_token'] = meta['next_token']
            r = requests.get(url, headers=HEADERS, params=params)
            users = r.json()['includes']['users']
            meta = r.json()['meta']
            retweeters.extend(users)
        retweeters.sort(key=lambda x:x['public_metrics']['followers_count'], reverse=True)
        ranking = [{'retweeter': rter['username'], 'followers': rter['public_metrics']['followers_count']} for rter in retweeters]
        return get_ranking(ranking)

@app.callback(
    Output(component_id='new-propagation-output', component_property='children'),
    Input(component_id='new-propagation-input', component_property='value'),
    Input('timeline', 'selected_rows'),
    Input('timeline', 'data')
)
def update_propagation(num_users, selected_rows, data):
    if num_users != '' and selected_rows is not []:
        api = get_twitter_api()
        row = selected_rows[0]
        text = data[row]['Tweet']
        text = re.sub('http[^\s]+', '', text)
        text = re.sub('&[^\s]*', '', text)
        text = re.sub('[\s]+', ' ', text)
        text = emoji.get_emoji_regexp().sub('', text)
        days, hours, minutes, seconds = propagation_time(api, int(num_users), text)
        formatted_time = '{} days, {} hours, {} minutes, {} seconds'.format(days, hours, minutes, seconds)
        return html.Div('Time taken to propagate to {} users: {}'.format(num_users, formatted_time))

@app.callback(
    Output(component_id='old-propagation-output', component_property='children'),
    Input(component_id='old-propagation-input', component_property='value'),
    Input('tweet-options', 'value')
)
def update_propagation_old(num_users, tweet_id):
    if num_users != '':
        filename = '../tweets/' + tweet_id + '.json'
        with open(filename, 'r') as f:
            retweets = json.load(f)
        days, hours, minutes, seconds = propagation_time_from_file(retweets, int(num_users))
        formatted_time = '{} days, {} hours, {} minutes, {} seconds'.format(days, hours, minutes, seconds)
        return html.Div('Time taken to propagate to {} users: {}'.format(num_users, formatted_time))

def get_metrics(user_id, tweet_id, num_tweets):
    metrics = benchmark(user_id, tweet_id, int(num_tweets))
    return [html.Label('Benchmark Metrics Table'),
            html.Div([
            dash_table.DataTable(
                style_cell={
                    'whiteSpace': 'normal',
                    'height': 'auto',
                    'textAlign': 'left'
                },
                style_cell_conditional=[
                    {'if': {'column_id': 'Tweet'},
                     'width': '40%'},
                    {'if': {'column_id': 'Post Date'},
                     'width': '30%'},
                    {'if': {'column_id': 'Retweets'},
                     'width': '10%'},
                    {'if': {'column_id': 'Replies'},
                     'width': '10%'}
                ],
                style_data_conditional=[
                    {'if': {'row_index': 0},
                     'backgroundColor': 'antiquewhite'}
                ],
                data=metrics,
                columns=[{'name': i, 'id': i} for i in [k for k in metrics[0].keys()]]
            )
        ])]

@app.callback(
    Output(component_id='new-benchmark-output', component_property='children'),
    Input(component_id='new-benchmark-input', component_property='value'),
    Input('timeline', 'selected_rows'),
    Input('timeline', 'data'),
    Input('twitter-username', 'value')
)
def update_benchmark(num_tweets, selected_rows, data, username):
    if num_tweets != '' and selected_rows is not []:
        row = selected_rows[0]
        text = data[row]['Tweet']
        api = get_twitter_api()
        tweet = api.search(q='from:{} {}'.format(username, text))[0]
        user_id = tweet.user.id
        tweet_id = tweet.id
        return get_metrics(user_id, tweet_id, num_tweets)

@app.callback(
    Output(component_id='old-benchmark-output', component_property='children'),
    Input(component_id='old-benchmark-input', component_property='value'),
    Input('tweet-options', 'value'),
    Input('twitter-username', 'value')
)
def update_benchmark_old(num_tweets, tweet_id, username):
    if num_tweets != '':
        api = get_twitter_api()
        user_id = api.get_user(screen_name=username).id
        return get_metrics(user_id, tweet_id, num_tweets)

@app.callback(Output('old-retweet-cascade', 'children'),
              Input('tweet-options-2', 'value'))
def update_retweet_cascade_old(tweet_id):
    if tweet_id:
        simple_cascade_file = 'retweet-cascades/{}_simple_cascade.json'.format(tweet_id)
        with open(simple_cascade_file, 'r') as f:
            simple_cascade = json.load(f)
        inferred_cascade_file = 'retweet-cascades/{}_retweet_cascade.json'.format(tweet_id)
        with open(inferred_cascade_file, 'r') as f:
            inferred_cascade = json.load(f)
        return get_cascade(simple_cascade, inferred_cascade)

@app.callback(Output('new-retweet-cascade', 'children'),
              Input('timeline-2', 'selected_rows'),
              Input('timeline-2', 'data'))
def update_retweet_cascade(selected_rows, data):
    if selected_rows:
        row = selected_rows[0]
        text = data[row]['Tweet']
        text = re.sub('http[^\s]+', '', text)
        text = re.sub('&[^\s]*', '', text)
        text = re.sub('[\s]+', ' ', text)
        text = emoji.get_emoji_regexp().sub('', text)
        url = 'https://api.twitter.com/2/tweets/search/recent'
        params = {'query': '(is:retweet OR is:quote) \"' + text + '\"',
                  'tweet.fields': 'created_at,author_id',
                  'expansions': 'referenced_tweets.id',
                  'max_results': 100}
        r = requests.get(url, headers=HEADERS, params=params)
        retweets = r.json()['data']
        original_tweet = r.json()['includes']['tweets'][0]
        original_tweet['tweet_id'] = original_tweet['id']
        original_tweet['author_id'] = int(original_tweet['author_id'])
        meta = r.json()['meta']
        while 'next_token' in meta:
            params['next_token'] = meta['next_token']
            params.pop('expansions', None)
            r = requests.get(url, headers=HEADERS, params=params)
            data = r.json()['data']
            meta = r.json()['meta']
            retweets.extend(data)
        if len(retweets) == 0:
            return html.Div('There are no retweets yet - please select a different tweet')
        simple_cascade, inferred_cascade = construct_retweet_cascade(api, retweets, original_tweet)
        return get_cascade(simple_cascade, inferred_cascade)

def get_cascade(simple_cascade, inferred_cascade):
    num_vertices = len(inferred_cascade)
    visualized_cascade = nx.Graph()
    visualized_cascade.add_nodes_from([x['tweet_id'] for x in simple_cascade])
    visualized_cascade.add_edges_from(inferred_cascade)
    pos = graphviz_layout(visualized_cascade, prog='dot')
    for node in visualized_cascade.nodes:
        visualized_cascade.nodes[node]['pos'] = list(pos[node])
    node_x = []
    node_y = []
    for node in visualized_cascade.nodes():
        x, y = visualized_cascade.nodes[node]['pos']
        node_x.append(x)
        node_y.append(y)
    edge_x = []
    edge_y = []
    for edge in visualized_cascade.edges():
        x0, y0 = visualized_cascade.nodes[edge[0]]['pos']
        x1, y1 = visualized_cascade.nodes[edge[1]]['pos']
        edge_x.append(x0)
        edge_x.append(x1)
        edge_x.append(None)
        edge_y.append(y0)
        edge_y.append(y1)
        edge_y.append(None)
    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=0.5, color='#888'),
        hoverinfo='none',
        mode='lines')
    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers',
        hoverinfo='text',
        marker=dict(
            colorscale='YlGnBu',
            reversescale=True,
            color=[],
            size=10,
            line_width=2))
    fig = go.Figure(data=[edge_trace, node_trace],
         layout=go.Layout(
            title='<br>Retweet Cascade of '+str(visualized_cascade.number_of_nodes())+' Retweets',
            titlefont=dict(size=16),
            showlegend=False,
            hovermode='closest',
            margin=dict(b=20,l=5,r=5,t=40),
            annotations=[ dict(
                showarrow=False,
                xref="paper", yref="paper",
                x=0.005, y=-0.002 ) ],
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)))
    return dcc.Graph(figure=fig)


def get_metrics(user_id, tweet_id, num_tweets):
    metrics = benchmark(user_id, tweet_id, int(num_tweets))
    return [html.Label('Benchmark Metrics Table'),
            html.Div([
            dash_table.DataTable(
                style_cell={
                    'whiteSpace': 'normal',
                    'height': 'auto',
                    'textAlign': 'left'
                },
                style_cell_conditional=[
                    {'if': {'column_id': 'tweet'},
                     'width': '45%'},
                    {'if': {'column_id': 'created_at'},
                     'width': '25%'},
                    {'if': {'column_id': 'retweets'},
                     'width': '10%'},
                    {'if': {'column_id': 'replies'},
                     'width': '10%'}
                ],
                style_data_conditional=[
                    {'if': {'row_index': 0},
                     'backgroundColor': 'antiquewhite'}
                ],
                data=metrics,
                columns=[{'name': i, 'id': i} for i in [k for k in metrics[0].keys()]]
            )
        ])]

def load_credentials(path):
    try:
        with open(path, "r") as finp:
            return yaml.load(finp, Loader=yaml.Loader)
    except FileNotFoundError:
        print("could not find credentials file: %s" % path)

    return {}

def load_ssm(param):
    try:
        ssm = boto3.client("ssm", region_name="us-east-1")
        val = ssm.get_parameter(Name=param, WithDecryption=True)
        return yaml.load(val["Parameter"]["Value"], Loader=yaml.Loader)
    except (
        ssm.exceptions.ParameterNotFound,
        KeyError,
        botocore.exceptions.NoCredentialsError,
    ):
        pass

    print("did not find parameter store value for %s" % param)
    return {}

def get_twitter_api():
    creds = load_ssm("/twitter/dev/credentials")
    if "twitter" not in creds:
        raise ValueError("unable to find Twitter API key")

    consumer_key = creds["twitter"]["key"]
    consumer_secret = creds["twitter"]["secret"]
    auth = tweepy.AppAuthHandler(consumer_key, consumer_secret)
    api = tweepy.API(
        auth,
        wait_on_rate_limit=True,
        wait_on_rate_limit_notify=True,
        retry_count=1000000,
        retry_delay=10,
        retry_errors=[429]
    )

    return api


api = get_twitter_api()


if __name__ == '__main__':
    app.run_server(debug=True)
