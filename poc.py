import os
import sys
sys.path.append("../mustard-mine") # Hack: Lift credentials from Mustard Mine if we don't have our own
from config import TWITTER_CLIENT_ID, TWITTER_CLIENT_SECRET
from twitter import *
from twitter.stream import TwitterStream, Timeout, HeartbeatTimeout, Hangup

MY_TWITTER_CREDS = os.path.expanduser('~/.cherami-login')
if not os.path.exists(MY_TWITTER_CREDS):
    oauth_dance("Cher Ami", TWITTER_CLIENT_ID, TWITTER_CLIENT_SECRET,
                MY_TWITTER_CREDS)

oauth_token, oauth_secret = read_token_file(MY_TWITTER_CREDS)

auth = OAuth(oauth_token, oauth_secret, TWITTER_CLIENT_ID, TWITTER_CLIENT_SECRET)
twitter = Twitter(auth=auth)
stream = TwitterStream(auth=auth)

# Now work with Twitter
tweet = None
for tweet in reversed(twitter.statuses.home_timeline(count=5, tweet_mode="extended")):
	print(tweet["full_text"])
if tweet is None: print("No tweets, prolly gonna crash now")

from pprint import pprint
pprint(tweet)
