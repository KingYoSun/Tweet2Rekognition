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

#Decimal型で返す
def return_decimal(num):
    return Decimal(num)

#json.dumps時のdecimal設定
def decimal_default_proc(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

#更新日時、時刻の取得
def get_update_at():
    today = datetime.date.today()
    today_obj = datetime.datetime.combine(today, datetime.time())
    updated_at_date = Decimal(today_obj.timestamp())
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

    # In this sample we only handle the specific exceptions for the 'GetSecretValue' API.
    # See https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
    # We rethrow the exception by default.

    try:
        global get_secret_value_response
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
        return get_secret_value_response["SecretString"]
    except ClientError as e:
        if e.response['Error']['Code'] == 'DecryptionFailureException':
            # Secrets Manager can't decrypt the protected secret text using the provided KMS key.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'InternalServiceErrorException':
            # An error occurred on the server side.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'InvalidParameterException':
            # You provided an invalid value for a parameter.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'InvalidRequestException':
            # You provided a parameter value that is not valid for the current state of the resource.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        elif e.response['Error']['Code'] == 'ResourceNotFoundException':
            # We can't find the resource that you asked for.
            # Deal with the exception here, and/or rethrow at your discretion.
            raise e
        else:
            # Decrypts secret using the associated KMS CMK.
            # Depending on whether the secret is a string or binary, one of these fields will be populated.
            if 'SecretString' in get_secret_value_response:
                secret = get_secret_value_response['SecretString']
            else:
                decoded_binary_secret = base64.b64decode(get_secret_value_response['SecretBinary'])