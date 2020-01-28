import sys
sys.path.append('lib/tweepy')

import boto3
import json
import io
import urllib.request
import tweepy
import datetime

#自作関数
import functions

#Twitterの認証 
twitter = json.loads(functions.get_secret())
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

#Twitterのスクレイピング
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
                    self.tweet_data.append({"id": functions.return_decimal(result.id), 
                        "user_name": result.user.name, 
                        "user_screen_name": result.user.screen_name,
                        "text": result.text,
                        "favorite_count": functions.return_decimal(result.favorite_count),
                        "retweet_count": functions.return_decimal(result.retweet_count),
                        "created_at": functions.return_decimal(result.created_at.timestamp()),
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

#Rekognitionでラベル付け
class SendRekognition:
    def __init__(self, data):
        self.data = data
    
    def send(self, img):
        try:
            return rekognition.detect_labels(Image={"Bytes": img}, MaxLabels=10)
        except Exception as e:
            print('Rekognition Error: ' + str(e))
    
    def checking_img(self, i, j, labels):
        label_names = [l["Name"] for l in labels] #ラベル名（Key）のリスト
        keyword_set = ["Clothing", "Fashion", "Apparel", "Accessories", "Accessory"]
        for label in labels:
            # labelが"Name": "Person"を持ち、ConfidenceがPERSON_THRESHOLDを超え、keyword_setうちどれかをラベルに持ち、かつBoundingBoxを持つ場合
            if "Person" in label_names and label["Confidence"] > PERSON_THRESHOLD and (len(set(label_names) & set(keyword_set)) != 0) and len(label["Instances"]) > 0 and "BoundingBox" in [b for b in label["Instances"][0]]:
                self.data[i]["img"][j]["labels"] = label_names
                for b in range(len(label["Instances"])):
                    if label["Instances"][b]["Confidence"] > PERSON_THRESHOLD:
                        #BoundingBoxをDecimal変換
                        label["Instances"][b]["BoundingBox"]["Width"] = functions.return_decimal(label["Instances"][b]["BoundingBox"]["Width"])
                        label["Instances"][b]["BoundingBox"]["Height"] = functions.return_decimal(label["Instances"][b]["BoundingBox"]["Height"])
                        label["Instances"][b]["BoundingBox"]["Left"] = functions.return_decimal(label["Instances"][b]["BoundingBox"]["Left"])
                        label["Instances"][b]["BoundingBox"]["Top"] = functions.return_decimal(label["Instances"][b]["BoundingBox"]["Top"])
                        self.data[i]["img"][j]["bounding_box"].append((label["Instances"][b]["BoundingBox"]))
                break
    
    def add_labels(self):
        try:
            #各ツイート
            new_tweet_count = 0
            update_tweet_count = 0
            latest_tweet_id = 0
            for i in range(len(self.data)):
                scanned_tweet = functions.get_tweet_id(table, self.data[i]["id"])
                #ツイート（ID)が既に存在する場合scaned_tweetに入る
                if latest_tweet_id == 0:
                    #dataのツイートは新しい順なので、get_tweet_idにヒットした場合以降のツイートは全て検索済みになる
                    if len(scanned_tweet) == 1:
                        latest_tweet_id = int(scanned_tweet[0]["id"])
                        print("latest_tweet_id: {}".format(latest_tweet_id))
                    
                if self.data[i]["id"] > latest_tweet_id:
                    if len(scanned_tweet) == 0:
                        #各ツイート内の各画像
                        for j in range(len(self.data[i]["img"])):
                            img_in = urllib.request.urlopen(self.data[i]["img"][j]["url"]).read()
                            img_bin = io.BytesIO(img_in)
                            result = self.send(img_in)
                            self.checking_img(i, j, result["Labels"])
                        if len(self.data[i]["img"]) > 0:
                            new_tweet_count += 1
                else:
                    if len(scanned_tweet) > 0:
                        self.data[i]["img"] = json.loads(scanned_tweet[0]["img"])
                        update_tweet_count +=1
        except Exception as e:
            print("Add Labels Error: " +str(e))
        finally:
            print("Finish Labeling, Add {} Tweet, Update {} Tweet".format(new_tweet_count, update_tweet_count))

#DynamoDBにデータを送信
class SendDynamoDB:
    def __init__(self, data):
        self.data = data
        
    def put(self):
        try:
            count = 0 # NewTweetCount
            updated_at = functions.get_update_at()
            for i in range(len(self.data)):
                #SendRekognition.checking_imgで除外された画像を除く画像セット（各ツイート）
                img_set = [img for img in self.data[i]["img"] if img["bounding_box"] != []]
                if img_set != []:
                    img_set = json.dumps(img_set, default=functions.decimal_default_proc)
                    table.put_item(
                        Item = {
                            "id": self.data[i]["id"], 
                            "user_name": self.data[i]["user_name"], 
                            "user_screen_name": self.data[i]["user_screen_name"],
                            "text": self.data[i]["text"],
                            "favorite": self.data[i]["favorite_count"],
                            "retweet": self.data[i]["retweet_count"],
                            "timestamp": self.data[i]["created_at"],
                            "updated_at_str": updated_at["datetime_str"],
                            "updated_at_date": updated_at["updated_at_date"],
                            "updated_at_time": updated_at["updated_at_time"],
                            "url": self.data[i]["url"],
                            "img": img_set
                        }
                    )
                    count += 1
        except Exception as e:
            print('DynamoDB Error: ' + str(e))
        finally:
            print('Finish putting DynamoDB, put {} Tweet'.format(count))
            
    
def handler(event, context):
    scraper = TweetScraper()
    scraper.search()
    
    rekognition = SendRekognition(scraper.tweet_data)
    rekognition.add_labels()
    send_dynamoDB = SendDynamoDB(rekognition.data)
    send_dynamoDB.put()
    
    #Appear rekognition.data
    #return{
    #    'isBase64Encoded': False,
    #    'statusCode': 200,
    #    'headers': {},
    #    'body': rekognition.data
    #}
    
