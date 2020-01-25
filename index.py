import sys
sys.path.append('lib/ruamel.yaml')
sys.path.append('lib/tweepy')

import boto3
import json
from decimal import Decimal
import datetime
import io
import urllib.request
import tweepy

#Secret ManagerからTWITTER API KeyとTokenを取得
import twitterAPI

#Twitterの認証 
twitter = json.loads(twitterAPI.get_secret())
CK = twitter["TWITTER_CK"]
CS = twitter["TWITTER_CS"]
AT = twitter["TWITTER_AT"]
AS = twitter["TWITTER_AS"]

#検索設定
SEARCH_TEXT = "(VRC OR VRChat OR #バーチャルストリート OR #VirtualStreet)"
SEARCH_COUNT = 100

#自撮り判定設定
PERSON_THRESHOLD = 75

#AWS設定
try:
    #DynamoDB設定
    dynamoDB = boto3.resource('dynamodb', 'ap-northeast-1')
    table = dynamoDB.Table("tweet2rekognition")
    #Rekognition設定
    rekognition = boto3.client('rekognition', 'ap-northeast-1')
except Exception as e:
    print('AWS Setup Error: ' + str(e))
finally:
    print('Finish AWS Setup')    

#json.dumps時のdecimal設定
def decimal_default_proc(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

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
            print('Twitter API Setup Error: ' + str(e))
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
                    self.tweet_data.append({"id": Decimal(result.id), 
                        "user_name": result.user.name, 
                        "user_screen_name": result.user.screen_name,
                        "text": result.text,
                        "favorite_count": Decimal(result.favorite_count),
                        "retweet_count": Decimal(result.retweet_count),
                        "created_at": Decimal(result.created_at.timestamp()),
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
            print('Twitter Search Error: ' + str(e))
        finally:
            print('Finish Twitter Search')

class LoadDynamoDB:
    def __init__(self, data):
        self.data = data
    

class SendRekognition:
    def __init__(self, data):
        self.data = data

    def send(self, img):
        try:
            return rekognition.detect_labels(Image={"Bytes": img}, MaxLabels=10)
        except Exception as e:
            print('Rekognition Error: ' + str(e))
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
                                #BoundingBoxをDecimal変換
                                label["Instances"][b]["BoundingBox"]["Width"] = Decimal(label["Instances"][b]["BoundingBox"]["Width"])
                                label["Instances"][b]["BoundingBox"]["Height"] = Decimal(label["Instances"][b]["BoundingBox"]["Height"])
                                label["Instances"][b]["BoundingBox"]["Left"] = Decimal(label["Instances"][b]["BoundingBox"]["Left"])
                                label["Instances"][b]["BoundingBox"]["Top"] = Decimal(label["Instances"][b]["BoundingBox"]["Top"])
                                self.data[i]["img"][j]["bounding_box"].append((label["Instances"][b]["BoundingBox"]))
                        break

class SendDynamoDB:
    def __init__(self, data):
        self.data = data
        
    def put(self):
        try:
            for i in range(len(self.data)):
                img_set = [img for img in self.data[i]["img"] if img["bounding_box"] != []]
                if img_set != []:
                    img_set = json.dumps(img_set, default=decimal_default_proc)
                    table.put_item(
                        Item = {
                            "id": self.data[i]["id"], 
                            "user_name": self.data[i]["user_name"], 
                            "user_screen_name": self.data[i]["user_screen_name"],
                            "text": self.data[i]["text"],
                            "favorite": self.data[i]["favorite_count"],
                            "retweet": self.data[i]["retweet_count"],
                            "timestamp": self.data[i]["created_at"],
                            "url": self.data[i]["url"],
                            "img": img_set
                        }
                    )
        except Exception as e:
            print('DynamoDB Error: ' + str(e))
        finally:
            print('Finish putting DynamoDB')
            
    
def handler(event, context):
    scraper = TweetScraper()
    scraper.search()
    
    rekognition = SendRekognition(scraper.tweet_data)
    rekognition.add_labels()
    send_dynamoDB = SendDynamoDB(rekognition.data)
    send_dynamoDB.put()
    
    return{
        'isBase64Encoded': False,
        'statusCode': 200,
        'headers': {},
        'body': rekognition.data
    }
    
