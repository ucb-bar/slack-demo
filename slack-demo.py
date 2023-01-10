#!/usr/bin/env python3

import slack_sdk
import requests
import time
import os
import pathlib


class SlackDemoApplication:

    def __init__(self):
        # Path to slack token
        tloc = os.path.expanduser("/scratch/abe/winter-retreat-2023-firesim-gemmini-demo/slack-demo/.slack-token")
        if not os.path.isfile(tloc):
            print("Error: Slack token file " + tloc + " does not exist.")
            exit(1)

        self.slacktoken = open(tloc).read().strip()
        self.auth_header={'Authorization': 'Bearer ' + self.slacktoken}
        self.form_header={'content-type': 'application/x-www-form-urlencoded'}

        self.client = slack_sdk.WebClient(token=self.slacktoken)

        response1 = self.client.auth_revoke(test='true')
        assert not response1['revoked']

        response2 = self.client.auth_test()
        assert response2.get('ok', False)

        # Make the tmp directory
        self.img_dir = "img_tmp"
        if not os.path.isdir(self.img_dir):
            os.makedirs(self.img_dir)

        # Get the current time
        self.ts_from = 0 #int(time.time())

        # Channel to monitor for images
        channel = "winter-retreat-2023-firesim-demo"
        self.cid = None

        channels = []
        # look for public channels only
        for page in self.client.conversations_list():
            channels = channels + page['channels']

        for c in channels:
           if (c['name'] == channel):
               self.cid = c['id']
               break

        if self.cid is None:
            print("Could not find channel: " + channel)
            exit(1)

    def do_it(self):
        print(f"Listing files from: {self.ts_from}")


        cursor = None
        # result messages, oldest to newest
        results_group = []
        files = []
        while True:
            if cursor == None: 
                result = self.client.conversations_history(channel=self.cid, oldest=self.ts_from, inclusive = False)
            else:
                result = self.client.conversations_history(channel=self.cid, oldest=self.ts_from, cursor=cursor, inclusive = False)
            conversation_history = result["messages"]
            if result["has_more"]:
                cursor = result["response_metadata"]["next_cursor"]
            else:
                cursor = None
            #print(conversation_history)
            results_group = conversation_history[::-1] + results_group

            if cursor is None:
                break

        if len(results_group) > 0:
            self.ts_from = float(results_group[-1]["ts"])

            for message in results_group:
                print("\n\n\n\n-------------------------------------")
                print(message)
        
                if 'files' not in message.keys():
                    continue

                for file in message['files']:
                    files.append(file)
                    print("    file:-------------------------")
                    print(file)

        print(files)

        #im = None

        if len(files) > 0:
            x = files[-1] # look at the most recent file
            print(f"Looking at file: {x['name']}")
            img = requests.get(x['url_private'], headers=self.auth_header)
            path = pathlib.PosixPath(os.path.join(self.img_dir, x['name']))
            with open(path, 'wb') as f:
                f.write(img.content)

            # create the input file for the NN
            print(path.suffix)
            if path.suffix == '.jpg' or path.suffix == '.jpeg':
                # TODO: do something
                print(f"Operating on file {x['name']}")
            else:
                print(f"File {path} is not a .jpg or .jpeg. Skipping...")

if __name__ == "__main__":
    app = SlackDemoApplication()
    while True:
        try:
            print("Loopin'")
            app.do_it()
            time.sleep(10)
        except:
            pass

