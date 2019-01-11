#!/usr/bin/env python

import requests
import time
import os
import json
import datetime

# Path to slack token
tloc = os.path.expanduser("~/.slacktoken")
if not os.path.isfile(tloc):
    print "Error: Slack token file " + tloc + " does not exist."
    exit(1)

slacktoken=open(tloc).read().strip()
auth_header={'Authorization': 'Bearer ' + slacktoken}
form_header={'content-type': 'application/x-www-form-urlencoded'}

def slack_json_helper(resp, method):
    j = json.loads(resp.content)
    if (j['ok'] is not True):
        print "Error: Slack API method " + method + " failed."
        exit(1)
    return j

def slack_api_get(method, data={}):
    header=auth_header.copy()
    header.update(form_header)
    resp = requests.get("https://slack.com/api/" + method, data=data, headers=header)
    return slack_json_helper(resp, "GET" + method)

def slack_api_post(method, data={}):
    header=auth_header.copy()
    header.update(form_header)
    resp = requests.post("https://slack.com/api/" + method, data=data, headers=header)
    return slack_json_helper(resp, "POST " + method)

# Make the tmp directory
img_dir = "img_tmp"
if not os.path.isdir(img_dir):
    os.makedirs(img_dir)

# Get the current time
ts_from = int(time.time())

# Channel to monitor for images
channel = "hurricane-demo"
user = None
cid = None
uid = None

if channel is None:
    users = slack_api_get("users.list")
    for u in users['members']:
        if (u['name'] == user):
            uid = u['id']
            break
else:
    channels = slack_api_get("conversations.list")
    for c in channels['channels']:
        if (c['name'] == channel):
            cid = c['id']
            break

if cid is None and uid is None:
    if user is None:
        print "Could not find channel: " + channel
    else:
        print "Could not find user: " + user
    exit(1)

while True:
    data = {"types": "images", "ts_from": str(ts_from)}
    if uid is None:
        data["channel"] = cid
    else:
        data["user"] = uid

    files = slack_api_post("files.list", data)['files']

    if len(files) > 0:
        x = files[-1]
        img = requests.get(x['url_private'], headers=auth_header)
        with open(os.path.join(img_dir, x['name']), 'w') as f:
            f.write(img.content)

        ts_from = int(x['timestamp']) + 1
        # TODO do stuff with images here instead of exiting
        exit(0)

    time.sleep(2)
