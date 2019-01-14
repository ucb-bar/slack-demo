#!/usr/bin/env python3

import requests
import time
import os
import json
import datetime
import numpy as np
import scipy.ndimage as si
from PIL import Image, ImageTk
import tkinter as tk


class SlackDemoApplication(tk.Frame):

    def slack_json_helper(self, resp, method):
        j = json.loads(resp.content)
        if (j['ok'] is not True):
            print("Error: Slack API method " + method + " failed.")
            exit(1)
        return j

    def slack_api_get(self, method, data={}):
        header = self.auth_header.copy()
        header.update(self.form_header)
        resp = requests.get("https://slack.com/api/" + method, data=data, headers=header)
        return self.slack_json_helper(resp, "GET" + method)

    def slack_api_post(self, method, data={}):
        header = self.auth_header.copy()
        header.update(self.form_header)
        resp = requests.post("https://slack.com/api/" + method, data=data, headers=header)
        return self.slack_json_helper(resp, "POST " + method)


    def __init__(self):
        # Path to slack token
        self.root = tk.Tk()
        self.w = self.root.winfo_screenwidth()/2
        self.h = self.root.winfo_screenheight() - 100
        self.ch = 30 # canvas height for text
        self.root.geometry("%dx%d+0+0" % (self.w,self.h + self.ch))
        self.root.title("Hurricane 2 Demo")
        self.root.configure(cursor="none")
        self.root.configure(background="black")
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_rowconfigure(3, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(2, weight=1)
        self.panel = tk.Label(self.root, borderwidth=0)
        self.canvas = tk.Canvas(self.root, width=self.w, height=self.ch, background="black", borderwidth=0)

        tk.Frame.__init__(self, self.root)
        self.panel.grid(column=1, row=1)
        self.canvas.grid(column=1, row=2)
        self.grid()

        tloc = os.path.expanduser("~/.slacktoken")
        if not os.path.isfile(tloc):
            print("Error: Slack token file " + tloc + " does not exist.")
            exit(1)

        self.slacktoken = open(tloc).read().strip()
        self.auth_header={'Authorization': 'Bearer ' + self.slacktoken}
        self.form_header={'content-type': 'application/x-www-form-urlencoded'}

        # Make the tmp directory
        self.img_dir = "img_tmp"
        if not os.path.isdir(self.img_dir):
            os.makedirs(self.img_dir)

        # Get the current time
        self.ts_from = int(time.time())
        self.ts_from = 0

        # Channel to monitor for images
        channel = "hurricane-demo"
        user = None
        self.cid = None
        self.uid = None

        if channel is None:
            users = self.slack_api_get("users.list")
            for u in users['members']:
                if (u['name'] == user):
                    self.uid = u['id']
                    break
        else:
            channels = self.slack_api_get("conversations.list")
            for c in channels['channels']:
                if (c['name'] == channel):
                    self.cid = c['id']
                    break

        if self.cid is None and self.uid is None:
            if user is None:
                print("Could not find channel: " + channel)
            else:
                print("Could not find user: " + user)
            exit(1)

    def update(self):
        data = {"types": "images", "ts_from": str(self.ts_from)}
        if self.uid is None:
            data["channel"] = self.cid
        else:
            data["user"] = self.uid

        files = sorted(self.slack_api_post("files.list", data)['files'], key=lambda x: int(x['timestamp']))

        im = None

        if len(files) > 0:
            x = files[0]
            img = requests.get(x['url_private'], headers=self.auth_header)
            path = os.path.join(self.img_dir, x['name'])
            with open(path, 'wb') as f:
                f.write(img.content)

            self.ts_from = int(x['timestamp']) + 1

            # display the image
            img = Image.open(path)
            scale = float(self.h)/float(img.height)
            if float(img.width)/float(img.height) > float(self.w)/float(self.h):
                scale = float(self.w)/float(img.width)
            new_w = int(round(img.width*scale))
            new_h = int(round(img.height*scale))
            im = ImageTk.PhotoImage(img.resize((new_w, new_h), Image.ANTIALIAS))
            self.panel.configure(image = im)
            self.panel.image = im

            # create the input file for the NN
            if path[-4:].lower() != '.jpg':
                print("File %s is not a JPEG. FIXME! Skipping this one..." % path)
            else:
                # crop
                if img.width > img.height:
                    margin = int((img.width - img.height)/2)
                    img = img.crop((margin, 0, margin + img.height, img.height))
                else:
                    margin = int((img.height - img.width)/2)
                    img = img.crop((0, margin, img.width, margin + img.width))

                img = img.resize((277, 277), Image.ANTIALIAS)
                img = np.array(img) - np.array([104, 117, 123])
                img.astype(np.float32)
                img = img.transpose([2, 0, 1])
                img.tofile(path + '.img')

                # TODO scp to board
                # "scp " + path + ".img root@" + self.zc706_ip + ":~/images"
                # TODO ssh to board and run demo command
                # "ssh root@" + self.zc706_ip + " -C " + self.nn_cmd
                thing = "TODO"
                self.canvas.create_text((self.w/2, self.ch/2 + 2), text="Detected " + thing, justify="center", fill="white", font=("Andale Mono", 28))

        # every 2 seconds (2000ms) check for new pictures
        self.root.after(2000, self.update)

if __name__ == "__main__":
    app = SlackDemoApplication()
    app.after(0, app.update)
    app.mainloop()

