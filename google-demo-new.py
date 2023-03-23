#!/usr/bin/env python3

import slack_sdk
import imghdr
import requests
import time
import os
import pathlib
import subprocess

import pickle
import os.path
from os import path

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

import requests
import datetime

# yucky way to import from stuff above you in the directory hierarchy
import sys

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

# The ID and range of a sample spreadsheet.
SAMPLE_SPREADSHEET_ID = '1d1pvrUN1X-pCXgiSsWVQX8YrVDQTOCW1ZI6jNg0nGCg'
SAMPLE_RANGE_NAME = 'Form Responses 1'



retreat_dir = "/home/firetower/Documents"
sd_scripts_dir = f"{retreat_dir}/slack-demo"
g_scripts_dir = f"{sd_scripts_dir}"
fdir = f"{retreat_dir}/firesim/"
#fdir = f"{retreat_dir}/firesim-pre-1.16.0/"
g_sw_dir = f"{fdir}/target-design/chipyard/generators/gemmini/software/gemmini-rocc-tests/"
conda_torch = "/home/firetower/miniforge3/envs/torch"

class SlackDemoApplication:

    def __init__(self):
        # Path to slack token
        tloc = os.path.expanduser(f"{sd_scripts_dir}/.slack-token-new")
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
        self.ts_from = (datetime.datetime.now())

        ## Channel to monitor for images
        #channel = "demo-input"
        #self.cid = None

        post_channel = "demo-output"
        self.post_cid = None

        self.old_hash = None

        channels = []
        # look for public channels only
        for page in self.client.conversations_list():
            channels = channels + page['channels']

        for c in channels:
            if (c['name'] == post_channel):
                self.post_cid = c['id']

        if self.post_cid is None:
            print("Could not find channel: " + channel + " " + post_channel)
            exit(1)
        else:
            print(f"Attaching to channel: {self.post_cid}")

        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        service = build('sheets', 'v4', credentials=creds)

        # Call the Sheets API
        self.sheet = service.spreadsheets()


    def do_it(self):
        print(f"Listing files from ts: {self.ts_from}")


        t_api_access = datetime.datetime.now()

        # get files from sheet (as url)
        result = self.sheet.values().get(spreadsheetId=SAMPLE_SPREADSHEET_ID,
                                    range=SAMPLE_RANGE_NAME
                                    ).execute()
        values = result.get('values', [])

        # skip header
        values = values[1:]
        print(values)
        url_to_predict = None

        for value in values:
            if len(value) != 2:
                continue

            timestamp = value[0]
            url = value[1]
            d = datetime.datetime.strptime(timestamp, '%m/%d/%Y %H:%M:%S')
            print(f"Got {d}")

            if d > self.ts_from:
                self.ts_from = d
                url_to_predict = url
                break

        print(url_to_predict)
        t_api_access_done = datetime.datetime.now()

        new_hash = hash(url_to_predict)
        if self.old_hash == new_hash:
            return
        self.old_hash = new_hash

        # x = sorted_files[0]

        print(f"Looking at file: {url_to_predict}")

        # get png preview associated w/ image (all images converted to this)
        #thumb_img_url = x[sorted([e for e in x.keys() if "thumb" in e])[0]]
        thumb_img_url = url_to_predict

        if not (("png" in url_to_predict) or ("jpg" in url_to_predict) or ("jpeg" in url_to_predict)):
            print("skipping since url doesn't have with png jpg jpeg")
            return

        img = requests.get(thumb_img_url, headers=self.auth_header)
        path = pathlib.PosixPath(os.path.join(self.img_dir, f"{new_hash}.png"))

        t_download = datetime.datetime.now()

        with open(path, 'wb') as f:
            f.write(img.content)

        print(f"Wrote file: {path}")
        t_write = datetime.datetime.now()


        self.client.chat_postMessage(
            channel=self.post_cid,
            unfurl_media=True,
            unfurl_links=True,
            text=f"MobileNet is predicting the following image: {url_to_predict}",
        )
        #with open(path.resolve(), 'rb') as f:
        #    self.client.files_upload_v2(
        #        channel=self.post_cid,
        #        file=f,
        #        filename=f"image.png",
        #        initial_comment=f"MobileNet is predicting the following image...",
        #    )

        t_post = datetime.datetime.now()

        # create the input file for the NN
        def run_and_fail(*args, **kwargs):
            t = subprocess.run(*args, **kwargs)
            if t.returncode != 0:
                print("Error!")
            return t

        run_and_fail(f"rm -rf {fdir}/deploy/results-workload/*", shell=True)
        run_and_fail(f"mkdir -p {g_scripts_dir}/audience_images/audience_images/", shell=True)
        run_and_fail(f"cp {path.resolve()} {g_scripts_dir}/audience_images/audience_images/image.png", shell=True)
        run_and_fail(f"cp {path.resolve()} {g_scripts_dir}/audience_images/audience_images/image2.png", shell=True)
        run_and_fail(f"cp {path.resolve()} {g_scripts_dir}/audience_images/audience_images/image3.png", shell=True)
        run_and_fail(f"cp {path.resolve()} {g_scripts_dir}/audience_images/audience_images/image4.png", shell=True)
        run_and_fail(f"source $(conda info --base)/etc/profile.d/conda.sh && conda activate {conda_torch} && cd {g_scripts_dir} && python3 gen_images.py", shell=True)
        run_and_fail(f"cp {g_scripts_dir}/images.h {g_sw_dir}/imagenet/images.h", shell=True)
        run_and_fail(f"cd {g_sw_dir} && ./build.sh imagenet", shell=True)
        run_and_fail(f"cd {sd_scripts_dir} && ./run-fs.sh", shell=True)
        t = subprocess.run(f"grep -r -h 'P .: ' {fdir}/deploy/results-workload", shell=True, capture_output=True)
        if t.returncode != 0:
            print("Unable to get predictions")
        else:
            print(t.stdout)
            preds = str(t.stdout, 'UTF-8').strip().split("\n")
            for pred in preds:
                print(f"Reading prediction: {pred}")
                prednum = int(pred.split()[-1])
                o = run_and_fail(f"source $(conda info --base)/etc/profile.d/conda.sh && conda activate {conda_torch} && cd {g_scripts_dir} && python3 print_class.py {prednum}", shell=True, capture_output=True)
                labelname = str(o.stdout, 'UTF-8')

                # with open(path.resolve(), 'rb') as f:
                #     self.client.files_upload_v2(
                #         channel=self.post_cid,
                #         file=f,
                #         filename=x['name'],
                #         initial_comment=f"MobileNet predicted this is `{labelname.strip()}`!",
                #     )

                t_finish_pred = datetime.datetime.now()

                self.client.chat_postMessage(
                    channel=self.post_cid,
                    text=f"MobileNet predicted this is `{labelname.strip()}`!",
                )

                t_post_again = datetime.datetime.now()

                print(f"API Access: {t_api_access_done - t_api_access}")
                print(f"Download time: {t_download - t_api_access_done}")
                print(f"Write img: {t_write - t_download}")
                print(f"1st post: {t_post - t_write}")
                print(f"Prediction: {t_finish_pred - t_post}")
                print(f"2nd post: {t_post_again - t_finish_pred}")

                # since all 4 predictions are the same immediatedly exit
                break

if __name__ == "__main__":
    app = SlackDemoApplication()
    while True:
        try:
            print("Loopin'")
            app.do_it()
            time.sleep(5)
        except:
            time.sleep(5)
            pass
