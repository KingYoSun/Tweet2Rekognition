Tweet2Rekogniton (and Store DynamoDB)
==============================================

Overview
-----------
Get tweets that include images and send AWS Rekognition to label images, finally, store tweets include labels to DynamoDB 

Description
-----------
This tool is executed in the following steps:
1. Search 100 tweets contains specific keywords and images using Tweepy
2. Send query to DynamoDB to see if the tweet is already stored in DynamoDB, 
   search until the previous day's scraping results
2. Send images of the tweet to Rekognition and label it
3. Extract tweets containing the "Person" label, bounding box, and some other labels
4. Store tweets in DynamoDB

This project includes:

* README.md - this file
* buildspec.yml - this file is used by AWS CodeBuild to package your
  application for deployment to AWS Lambda
* index.py - this file contains the main Python code
* functions - this file contains some functions. sending query searching tweet id to 
  DynamoDB, getting Twitter API ket and token from SecretsManager etc...
* template.yml - this file contains the AWS Serverless Application Model (AWS SAM) used
  by AWS CloudFormation to deploy your application to AWS Lambda and Amazon API
  Gateway.
* lib/ - this directory contains Tweepy 3.8.0
* tests/ - this directory contains unit tests for your application
* template-configuration.json - this file contains the project ARN with placeholders used for tagging resources with the project ID

Requirement
---------------
boto3
tweepy

Environment
-----------

License
-------
MIT

Author
------
[@knotted221](https://twitter.com/knotted221)


