import sys
sys.path.append('lib/ruamel.yaml')
sys.path.append('lib/tweepy')
sys.path.append('lib/Pillow')

import os
import boto3
import io
import urllib.request
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
            for result in self.api.search(q='{} -filter:retweets filter:images'.format(SEARCH_TEXT), result_type='recent', count=SEARCH_COUNT):
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
                        "img": []
                    })
                    for i in range(num_media):
                        self.tweet_data[-1]["img"].append({
                        "id": result.extended_entities["media"][i]["id_str"],
                        "url": result.extended_entities["media"][i]["media_url_https"],
                        "labels": [],
                        "bounding_box": []
                        })
                
        except Exception as e:
            print('Twitter Search Error' + str(e))
        finally:
            print('Finish Twitter Search')

class SendRekognition:
    def __init__(self, data):
        self.data = data

    def send(self, img):
        try:
            return rekognition.detect_labels(Image={"Bytes": img}, MaxLabels=10)
        except Exception as e:
            print('Rekognition Error' + str(e))
        finally:
            print('Finish Rekognition')
    
    def add_labels(self):
        #各ツイート
        for i in range(len(self.data)):
            #各ツイート内の各画像
            for j in range(len(self.data[i]["img"])):
                img_in = urllib.request.urlopen(self.data[i]["img"][j]["url"]).read()
                img_bin = io.BytesIO(img_in)
                result = self.send(img_in)
                label_names = [l["Name"] for l in result["Labels"]] #ラベル名（Key）のリスト
                for label in result["Labels"]:
                    # labelが"Name": "Person"を持ち、ConfidenceがPERSON_THRESHOLDを超え、かつBoundingBoxを持つ場合
                    if "Person" in label["Name"] and label["Confidence"] > PERSON_THRESHOLD and len(label["Instances"]) > 0 and "BoundingBox" in [b for b in label["Instances"][0]]:
                        self.data[i]["img"][j]["labels"].append(label_names)
                        for b in range(len(label["Instances"])):
                            if label["Instances"][b]["Confidence"] > PERSON_THRESHOLD:
                                self.data[i]["img"][j]["bounding_box"].append(label["Instances"][b]["BoundingBox"])
                        break
    
def handler(event, context):
    scraper = TweetScraper()
    scraper.search()
    
    rekognition = SendRekognition(scraper.tweet_data)
    rekognition.add_labels()
    
    return{
        'isBase64Encoded': False,
        'statusCode': 200,
        'headers': {},
        'body': rekognition.data
    }
    
