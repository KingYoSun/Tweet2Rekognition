import sys
sys.path.append('lib/ruamel.yaml')
sys.path.append('lib/tweepy')

import json
import datetime
import os
import boto3
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

#検索設定
SEARCH_TEXT = env['SEARCH_TEXT']
SEARCH_COUNT = env['SEARCH_COUNT']

#自撮り判定設定
PERSON_THRESHOLD = env['PERSON_THRESHOLD']

#Rekognition設定
rekognition = boto3.client('rekognition', 'ap-northeast-1')

class TweetScraper:
    def __init__(self):
        self.tweet_data = []
        self.set_twitter_api()
    
    #Twitterオブジェクトの生成
    def set_twitter_api(self):
        try:
            auth = tweepy.OAuthHandler(CK, CS)
            auth.set_access_token(AT, AS)
            self.api = tweepy.API(auth)
        except Exception as e:
            print('Twitter API Setup Error' + str(e))
            self.api = None
        finally:
            print('Set Twitter API Object')
    
    #画像ありツイートをSEARCH_TEXTでSEARCHCOUNTだけ検索        
    def search(self):
        try:
            for result in self.api.search(q='{} -filter:retweets'.format(SEARCH_TEXT), result_type='recent', count=SEARCH_COUNT):
                url = 'https://twitter.com/{}/status/{}'.format(result.user.screen_name, result.id)
                text = result.text.replace('\n', '')
                #画像ありツイートのみ抽出
                if 'media' in result.entities.keys():
                    #画像の個数
                    num_media = len(result.extended_entities["media"])
                    #データ入力
                    self.tweet_data.append({"id": result.id, 
                        "user_name": result.user.name, 
                        "user_screen_name": result.user.screen_name,
                        "text": result.text,
                        "favorite_count": result.favorite_count,
                        "retweet_count": result.retweet_count,
                        "created_at": result.created_at.isoformat(),
                        "url": url,
                        "media_url": []
                    })
                    for i in range(num_media):
                        self.tweet_data[-1]["media_url"].append(result.extended_entities["media"][i]["media_url_https"])
                
        except Exception as e:
            print('Twitter Search Error' + str(e))
        finally:
            print('Finish Twitter Search')

class SendRekognition:
    def __init__(self, data):
        self.data = data
        self.person_th = PERSON_THRESHOLD
        self.image = None #画像データ
    
    def send(self):
        try:
            self.response = rekognition.detect_labels(Image={"Bytes": self.image}, MaxLabels=10)
        except Exception as e:
            print('Rekognition Error' + str(e))
        finally:
            print('Finish Rekognition')
    
def handler(event, context):
    scraper = TweetScraper()
    scraper.search()
    
    rekognition = SendRekognition(scraper.tweet_data)
    
    return{
        'isBase64Encoded': False,
        'statusCode': 200,
        'headers': {},
        'body': rekognition.data
    }
    
