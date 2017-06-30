import os
import json
from uuid import uuid4

import arrow
import boto3
from  twitter import *

token = os.environ['token_key']
token_secret = os.environ['token_secret']
consumer_key = os.environ['consumer_key']
consumer_secret = os.environ['consumer_secret']
create_animation_arn = os.environ['create_animation_arn']

LENGTH = '6'
BACKGROUND = 'bom'

s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')

def s3_to_disk(bucket, key):

    local_file = '/tmp/{}'.format(str(uuid4()))
    s3_client.download_file(bucket, key, local_file)

    return local_file


def handler(event, context):

    print(json.dumps(event))
    message = json.loads(event['Records'][0]['Sns']['Message'])
    print(message)

    rain_key = message['lambda']['key']
    rain_bucket = message['lambda']['bucket']
    print('rain_key: {} rain_bucket: {}'.format(rain_key, rain_bucket))

    pref, radar_id, size, file = rain_key.split('/')
    end_timestamp = file.replace('.png', '')

    payload = {
        'end_timestamp': end_timestamp,
        'length': LENGTH,
        'size': size,
        'bg': BACKGROUND,
        'radar_id': radar_id,
        'block': True
    }

    print('this will be the payload: {}'.format(json.dumps(payload)))

    #with the 'rain key' we just infer now that it's possible to create the animation
    response = lambda_client.invoke(
        FunctionName=create_animation_arn,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)
    )

    if response['StatusCode'] == 200:

        response_payload = json.loads(response['Payload'].read())
        print(response_payload)

        local_file = s3_to_disk(response_payload['animated_bucket'], response_payload['animated_key'])

        with open(local_file, "rb") as imagefile:
            imagedata = imagefile.read()

        t = Twitter(auth=OAuth(token, token_secret, consumer_key, consumer_secret))
        t_upload = Twitter(domain='upload.twitter.com', auth=OAuth(token, token_secret, consumer_key, consumer_secret))

        #this is the gif upload-to-twitter part
        print('starting animated gif upload')
        start = arrow.utcnow()
        id_img1 = t_upload.media.upload(media=imagedata)["media_id_string"]
        finish = arrow.utcnow()
        print('animated gif uploaded in {} seconds'.format(finish.timestamp - start.timestamp))
        print(id_img1)

        dt = arrow.get(response_payload['animated_key'].split('/')[2], 'YYYYMMDDHHmm').to('Australia/Hobart')
        print(dt)

        human_time = dt.format('ha')
        elapsed_hours = LENGTH

        print('human_time: {}'.format(human_time))

        #this does the actual tweet
        res = t.statuses.update(status='{} hours to {}'.format(elapsed_hours, human_time), media_ids=",".join([id_img1]))
        print(res['entities']['media'][0]['url'])

        os.remove(local_file)
    else:
        print('there was a a problem invoking CreateAnimation lambda')
        print(response)

    return {}

#test
#with open('test.json', 'r') as fp:
#    handler(json.loads(fp.read()), {})
