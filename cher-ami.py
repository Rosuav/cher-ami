import os
import shutil
import sys
import textwrap
import time
from pprint import pprint
sys.path.append("../mustard-mine") # Hack: Lift credentials from Mustard Mine if we don't have our own
from config import TWITTER_CLIENT_ID, TWITTER_CLIENT_SECRET
from twitter import OAuth, Twitter, read_token_file
from twitter.stream import TwitterStream, Timeout, HeartbeatTimeout, Hangup

CREDENTIALS_FILE = os.path.expanduser('~/.cherami-login')
if not os.path.exists(CREDENTIALS_FILE):
	oauth_dance("Cher Ami", TWITTER_CLIENT_ID, TWITTER_CLIENT_SECRET, CREDENTIALS_FILE)

auth = OAuth(*read_token_file(CREDENTIALS_FILE), TWITTER_CLIENT_ID, TWITTER_CLIENT_SECRET)
twitter = Twitter(auth=auth)
stream = TwitterStream(auth=auth, timeout=10)

def fix_extended_tweet(tweet):
	# Streaming mode doesn't include the full_text. It will show short tweets
	# with just "text", and longer ones with an "extended_tweet" that includes
	# the full text.
	if "extended_tweet" in tweet:
		tweet.update(tweet["extended_tweet"])
	if "full_text" not in tweet: tweet["full_text"] = tweet["text"]

def print_tweet(tweet, indent=""):
	"""TODO:
	* Put a marker in bold at the start of the tweet, to properly distinguish them
	* Convert URLs using tweet["entities"]["urls"][*]["display_url"]
	* Retain the expanded_url from the above and react to clicks
	* Figure out display_text_range
	* Retain the ID. If the marker is clicked, open the tweet in a browser.
	* Show quoted tweets.
	* Show tweet["source"] on request??
	"""
	try:
		fix_extended_tweet(tweet)
		# TODO: If it's a poll, show the options, or at least show that it's a poll.
		label = indent + "@" + tweet["user"]["screen_name"] + ": "
		wrapper = textwrap.TextWrapper(
			initial_indent=label,
			subsequent_indent=" " * len(label),
			width=shutil.get_terminal_size().columns,
		)
		for line in tweet["full_text"].splitlines():
			print(wrapper.fill(line))
			wrapper.initial_indent = wrapper.subsequent_indent # For subsequent lines, just indent them
		if "quoted_status" in tweet:
			print_tweet(tweet["quoted_status"], indent=" " * len(label))
	except Exception as e:
		print("%%%%%%%%%%%%%%%%%%%%%%%%%%%")
		pprint(tweet)
		raise

tweet = None
for tweet in reversed(twitter.statuses.home_timeline(count=10, tweet_mode="extended")):
	print_tweet(tweet)
if tweet is None: print("No tweets, prolly gonna crash now")

# pprint(tweet)
def spam_requests(last):
	# This would work, but the home_timeline API is rate-limited to 15 every 15 minutes.
	# So at best, we could get a 60-secondly poll.
	while True:
		print("---------")
		time.sleep(5)
		for tweet in reversed(twitter.statuses.home_timeline(since_id=last, count=2, tweet_mode="extended")):
			last = tweet["id"]
			print_tweet(tweet)
# spam_requests(tweet["id"])

def stream_from_friends():
	# TODO: Get all pages
	following = twitter.friends.ids()["ids"]
	print("---------")
	# TODO: Filter out replies to people I follow (unless I also follow the person)
	# Be sure to include replies to *me* from anyone, or mentions of me.
	for tweet in stream.statuses.filter(follow=",".join(str(f) for f in following), tweet_mode="extended"):
		if tweet is Timeout:
			# TODO: If it's been more than a minute, ping the timeline for any
			# we missed.
			continue
		if "retweeted_status" in tweet:
			if not tweet["is_quote_status"]: continue # Ignore plain retweets
			# Hopefully a quoting-retweet will still get shown.
		if "id" in tweet:
			# TODO: Remember the ID so we don't repeat this one
			print_tweet(tweet)
			# pprint(tweet)
	print("End of stream")
stream_from_friends()
# TODO: Handle reconnect logic
