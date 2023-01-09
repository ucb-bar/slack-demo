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
        self.ts_from = int(time.time())

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

        files = []
        for page in self.client.files_list(channel=self.cid, types="images", ts_from=self.ts_from):
            files = files + page['files']

        #print(files)

        files = sorted(files, key=lambda x: int(x['timestamp']))
        #print("\nDEBUG")
        #print([print(f"{f['name']}: {f['timestamp']}") for f in files])
        ##print([print(f"{f['name']}: {self.ts_from - int(f['timestamp'])}") for f in files])
        #print("DONE DEBUG\n")

        im = None

        if len(files) > 0:
            x = files[-1] # look at the most recent file
            print(f"Looking at file: {x['name']}")
            img = requests.get(x['url_private'], headers=self.auth_header)
            path = pathlib.PosixPath(os.path.join(self.img_dir, x['name']))
            with open(path, 'wb') as f:
                f.write(img.content)

            # add some delay before the next image
            self.ts_from = int(x['timestamp']) + 1

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
        print("Loopin'")
        app.do_it()
        time.sleep(10)
