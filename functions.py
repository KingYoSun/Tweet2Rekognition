# Use this code snippet in your app.
# If you need more information about configurations or implementing the sample code, visit the AWS docs:   
# https://aws.amazon.com/developers/getting-started/python/

#Secret ManagerからTWITTER API KeyとTokenを取得

import boto3
import base64
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
from decimal import Decimal, ROUND_DOWN
import datetime
from dateutil.relativedelta import relativedelta

#Decimal型で返す
def return_decimal(num):
    return Decimal(num)

#json.dumps時のdecimal設定
def decimal_default_proc(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def date_to_unix(date):
    date_to_datetime = datetime.datetime.combine(date, datetime.time())
    date_to_unix = date_to_datetime.timestamp()
    unix_convert_decimal = Decimal(date_to_unix)
    return unix_convert_decimal
    
def get_one_month_later():
    today = datetime.date.today()
    one_month_later = today + relativedelta(months=1)
    one_month_later_convert = date_to_unix(one_month_later)
    return one_month_later_convert
    
#更新日時、時刻の取得
def get_update_at():
    today = datetime.date.today()
    updated_at_date = date_to_unix(today)
    current_time = datetime.datetime.now()
    current_time_for_unix = datetime.datetime(1970, 1, 1, hour=current_time.hour, minute=current_time.minute, second=current_time.second, microsecond=current_time.microsecond)
    updated_at_time = Decimal(current_time_for_unix.timestamp()).quantize(Decimal('0'), rounding=ROUND_DOWN)
    return {"datetime_str": str(current_time), "updated_at_date": updated_at_date, "updated_at_time": updated_at_time}
    
#指定のツイートIDを取得
def get_tweet_id(table, tweet_id):
    try:
        updated_at = get_update_at()
        today = updated_at["updated_at_date"]
        last_day = today - Decimal(60*60*24) #60*60*24はUnix時刻で一日分
        queryData = table.query(
            KeyConditionExpression = Key('updated_at_date').eq(today) & Key('id').eq(tweet_id),
            ScanIndexForward = True,
            Limit = 1
        )
        #最新日で検索して見つからない場合は前日の分も検索
        if len(queryData["Items"]) == 0:
            queryData = table.query(
            KeyConditionExpression = Key('updated_at_date').eq(last_day) & Key('id').eq(tweet_id),
            ScanIndexForward = True,
            Limit = 1
            )
        return queryData["Items"]
    except Exception as e:
        print('Tweet is not exist: ' + str(e))
        return None

#SecretsManegerからTwitter API KeyとTokenを入手
def get_secret():

    secret_name = "TWITTER_API_FOR_SEARCH"
    region_name = "ap-northeast-1"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
 
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        raise e
    else:
        return get_secret_value_response["SecretString"]