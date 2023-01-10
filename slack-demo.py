#!/usr/bin/env python3

import slack_sdk
import requests
import time
import os
import pathlib
import subprocess

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
        else:
            print(f"Attaching to channel: {self.cid}")

    def do_it(self):
        print(f"Listing files from ts: {self.ts_from}")

        files = []
        for page in self.client.files_list(channel=self.cid, types="images", ts_from=self.ts_from):
        #for page in self.client.files_list(channel=self.cid, types="images"):
            files = files + page['files']

        sorted_files = sorted(files, key=lambda x: int(x['timestamp']))

        im = None

        if len(sorted_files) > 0:
            #print([print(f"{f['name']}: {f['timestamp']}") for f in sorted_files])

            x = sorted_files[0] # look at the most recent file
            print(f"Looking at file: {x['name']}")
            img = requests.get(x['url_private'], headers=self.auth_header)
            path = pathlib.PosixPath(os.path.join(self.img_dir, x['name']))
            with open(path, 'wb') as f:
                f.write(img.content)

            # add some delay before the next image
            self.ts_from = int(x['timestamp']) + 1

            # create the input file for the NN
            if path.suffix == '.jpg' or path.suffix == '.jpeg':
                # TODO: do something
                print(f"Operating on file {x['name']}")

                def run_and_fail(*args, **kwargs):
                    t = subprocess.run(*args, **kwargs)
                    if t.returncode != 0:
                        print("Error!")
                    return t

                retreat_dir = "/scratch/abe/winter-retreat-2023-firesim-gemmini-demo"
                g_scripts_dir = f"{retreat_dir}/gemmini-other/demo"
                g_sw_dir = f"{retreat_dir}/firesim/target-design/chipyard/generators/gemmini/software/gemmini-rocc-tests/"
                fdir = f"{retreat_dir}/firesim/"

                run_and_fail(f"rm -rf {fdir}/deploy/results-workload/*", shell=True)
                run_and_fail(f"cp {path.resolve()} {g_scripts_dir}/audience_images/audience_images/image.jpg", shell=True)
                run_and_fail(f"cp {path.resolve()} {g_scripts_dir}/audience_images/audience_images/image2.jpg", shell=True)
                run_and_fail(f"cp {path.resolve()} {g_scripts_dir}/audience_images/audience_images/image3.jpg", shell=True)
                run_and_fail(f"cp {path.resolve()} {g_scripts_dir}/audience_images/audience_images/image4.jpg", shell=True)
                run_and_fail(f"source $(conda info --base)/etc/profile.d/conda.sh && conda activate /home/abe/miniforge3/envs/torch && cd {g_scripts_dir} && python3 gen_images.py", shell=True)
                run_and_fail(f"cp {g_scripts_dir}/images.h {g_sw_dir}/imagenet/images.h", shell=True)
                run_and_fail(f"cd {g_sw_dir} && ./build.sh imagenet", shell=True)
                run_and_fail(f"cd {retreat_dir} && ./temp.sh", shell=True)
                t = subprocess.run(f"grep -r -h 'P .: ' {fdir}/deploy/results-workload", shell=True, capture_output=True)
                if t.returncode != 0:
                    print("Unable to get predictions")
                else:
                    print(t.stdout)
                    preds = str(t.stdout, 'UTF-8').strip().split("\n")
                    for pred in preds:
                        print(f"Reading prediction: {pred}")
                        prednum = int(pred.split()[-1])
                        o = run_and_fail(f"source $(conda info --base)/etc/profile.d/conda.sh && conda activate /home/abe/miniforge3/envs/torch && cd {g_scripts_dir} && python3 print_class.py {prednum}", shell=True, capture_output=True)
                        labelname = str(o.stdout, 'UTF-8')
                        self.client.chat_postMessage(channel=self.cid, text=f"IMG: `{x['name']}` is _100%, no question_... `{labelname.strip()}`!")
                        break

            else:
                print(f"File {path} is not a .jpg or .jpeg. Skipping...")

if __name__ == "__main__":
    app = SlackDemoApplication()
    while True:
        print("Loopin'")
        app.do_it()
        time.sleep(5)
