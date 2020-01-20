import sys
sys.path.append('lib/ruamel.yaml')
sys.path.append('lib/tweepy')

import json
import datetime
import os
import tweepy
from ruamel.yaml import YAML

#Load Key and Token
with open('secret.yml') as file:
    yaml = YAML(typ='safe')
    env = yaml.load(file)

#Twitterの認証 
CK = env['TWITTER_CK']
CS = env['TWITTER_CS']
AT = env['TWITTER_AT']
AS = env['TWITTER_AS']

def handler(event, context):
    #Twitterオブジェクトの生成
    auth = tweepy.OAuthHandler(CK, CS)
    auth.set_access_token(AT, AS)
    
    api = tweepy.API(auth)
    
    api.update_status("Hello Tweepy!")
