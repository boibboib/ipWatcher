#!/usr/bin/python

import praw
from praw.handlers import MultiprocessHandler
import re
import requests
import sys
import socket
import time
import datetime


# More than one bot running?
#---------------------------
MULTIPROCESS = True

# The subreddit here log messages will be sent
#---------------------------------------------
LOGSUBREDDIT = "blogspammr"


# Don't check for IPs on these domains
#-------------------------------------
ignoredomains=['yahoo.com', 'space.com', 'nytimes.com', 'cracked.com', '.gov', '.org', '.jp',
               '.ie', 'google.com', '.mil', 'thedodo.com', 'economist.com']


# IDs, secrets, uris, tokens, etc for OAuth2
# (https://redd.it/3cm1p8  OAuth2 instructions from /u/GoldenSights.  Thanks!)
#-----------------------------------------------------------------------------
app_id = ''
app_secret = ''
app_refresh = ''
app_uri = 'https://127.0.0.1:65010/authorize_callback'


# Today's date
#------------------
myToday = datetime.date.today()


# List of banned IPs - add IPs to this list or read them from a wiki page
#-------------------------------------------------------------------------
ipBanList = []


# init praw and log in
#----------------------
def login ():
    handler = MultiprocessHandler()
    if MULTIPROCESS:
        r=praw.Reddit("/u/boib ipWatcher", handler=handler)
    else:
        r=praw.Reddit("/u/boib ipWatcher")

    r.set_oauth_app_info(app_id, app_secret, app_uri)
    r.refresh_access_information(app_refresh)

    print ("\nI am %s" % (r.get_me().name))
    return r


# Get banned IP addrs from the wiki page
# Format of wiki page is: * <ip>\n* <ip>\n...
#---------------------
def getBannedIPs (subreddit):
    global ipBanList

    wp = r.get_wiki_page(subreddit, "ipban")
    text = wp.content_md.replace("*", "")
    ipBanList = text.split()


# Log found IPs in the log subreddit
# ----------------------------------
def doRedditLog (mysub, ip, post):

    global myToday
    global LOGSUBREDDIT

    lToday = datetime.date.today()

    # start a new log post once a day
    if lToday != myToday or not mysub:

        # reload banned IPs from wiki page once a day
        getBannedIPs(LOGSUBREDDIT)

        myToday = lToday
        postStr = "IP Log %s.%02d.%02d" % (myToday.year, int(myToday.month), int(myToday.day))
        srch = r.search(postStr, subreddit=LOGSUBREDDIT)
        searchResult = list(srch)
        if len(searchResult) == 0:
            mysub = r.submit(LOGSUBREDDIT, postStr, text="\nlink|sub|domain|ip|user\n---|---|---|---|---\n")
        else:
            mysub = searchResult[0]

    if not post:
        return mysub

    if not post.author:
        post.author = "[deleted]"

    posttext = "%s|%s|%s|%s|%s\n" % (post.short_link, post.subreddit.display_name, post.domain, ip, post.author)
    posttext.replace("_", "\_")
    return mysub.edit(mysub.selftext + posttext)




#==============================================================
if __name__=='__main__':

    SUB_TO_CHECK = 'all' # your sub goes here

    r = login ()

    # create the log post or get the current one
    mysub = doRedditLog (None, None, None)
    getBannedIPs(LOGSUBREDDIT)

    while True:

        try:
            for post in praw.helpers.submission_stream(r, SUB_TO_CHECK, limit = 10, verbosity=0):

                # skip self posts
                if post.domain.startswith('self.'):
                    continue

                # skip posts to domains in the ignore list
                if any(post.domain == item or post.domain.endswith(item) for item in ignoredomains):
                    continue


                ok = False
                result = False
                recheck = False
                foundIp = ""

                while not ok:
                    ok = True
                    try:
                        # check the domain's IP addr
                        foundIp = socket.gethostbyname(post.domain)
                    except Exception as e:
                        if not post.domain.startswith("www."):
                            post.domain = "www." + post.domain
                            recheck = True
                            ok = False
                        #else:
                        #    print ("exception at gethostbyname %s %s %s" % (e, post.domain, post.short_link))

                if foundIp:
                    for x in ipBanList:

                        # if the ip we're checking for is not complete (10.10.10) or
                        # there's a trailing '.' (10.10.), just check for a match with
                        # the start
                        if x.count('.') != 3 or x.endswith('.'):
                            if not x.endswith('.'):
                                x = x + '.'
                            if foundIp.startswith(x):
                                result = True
                        elif foundIp == x:
                            result = True

                        if result:
                            print(post.short_link)

                            # log it
                            mysub = doRedditLog(mysub, foundIp, post)

                            # report it
                            # post.report("Mobile redirect spam from %s" % (foundIp))

                            # if you're a mod, remove it
                            # post.remove()

                            break



        except Exception as e:
            print ("Exception in outer loop: %s" % e)
            time.sleep(15)



