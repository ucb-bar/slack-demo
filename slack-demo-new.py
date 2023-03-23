#!/usr/bin/env python3

import slack_sdk
import requests
import time
import os
import pathlib
import subprocess

retreat_dir = "/home/firetower/Documents"
sd_scripts_dir = f"{retreat_dir}/slack-demo"
g_scripts_dir = f"{sd_scripts_dir}"
#fdir = f"{retreat_dir}/firesim/"
fdir = f"{retreat_dir}/firesim-pre-1.16.0/"
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
        self.ts_from = int(time.time())

        # Channel to monitor for images
        channel = "demo-input"
        self.cid = None

        post_channel = "demo-output"
        self.post_cid = None

        self.old_hash = None

        channels = []
        # look for public channels only
        for page in self.client.conversations_list():
            channels = channels + page['channels']

        for c in channels:
            if (c['name'] == channel):
                self.cid = c['id']
            if (c['name'] == post_channel):
                self.post_cid = c['id']

        if self.cid is None or self.post_cid is None:
            print("Could not find channel: " + channel + " " + post_channel)
            exit(1)
        else:
            print(f"Attaching to channel: {self.cid} {self.post_cid}")

    def do_it(self):
        print(f"Listing files from ts: {self.ts_from}")

        cursor = None
        # result messages, oldest to newest
        results_group = []
        files = []
        # for page in self.client.files_list(channel=self.cid, types="images", ts_from=self.ts_from):
        # #for page in self.client.files_list(channel=self.cid, types="images"):
        #     files = files + page['files']
        #
        # sorted_files = sorted(files, key=lambda x: int(x['timestamp']))
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
            self.ts_from = float(results_group[0]["ts"])

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
        sorted_files = files

        if len(sorted_files) > 0:

            x = None

            # TODO: Oh no!
            for sf in sorted_files:
                new_hash = hash(sf['url_private'])
                if self.old_hash == new_hash:
                    continue
                self.old_hash = new_hash
                x = sf
                break

            # x = sorted_files[0]

            print(f"Looking at file: {x['name']}")

            # get png preview associated w/ image (all images converted to this)
            #thumb_img_url = x[sorted([e for e in x.keys() if "thumb" in e])[0]]
            thumb_img_url = x['url_private']

            img = requests.get(thumb_img_url, headers=self.auth_header)
            path = pathlib.PosixPath(os.path.join(self.img_dir, x['name'].replace(" ", "")))
            path = path.with_suffix(".png") # rename to png (to match thumbnail)
            with open(path, 'wb') as f:
                f.write(img.content)

            print(f"Wrote file: {path}")

            with open(path.resolve(), 'rb') as f:
                self.client.files_upload_v2(
                    channel=self.post_cid,
                    file=f,
                    filename=x['name'],
                    initial_comment=f"MobileNet is predicting the following image...",
                )

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

                    self.client.chat_postMessage(
                        channel=self.post_cid,
                        text=f"MobileNet predicted this is `{labelname.strip()}`!",
                    )


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
            pass
