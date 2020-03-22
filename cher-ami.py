import json
import os
import shutil
import sys
import textwrap
import time
from pprint import pprint
sys.path.append("../mustard-mine") # Hack: Lift credentials from Mustard Mine if we don't have our own
from config import TWITTER_CLIENT_ID, TWITTER_CLIENT_SECRET
from twitter import OAuth, Twitter, oauth_dance, read_token_file
from twitter.stream import TwitterStream, Timeout, HeartbeatTimeout, Hangup

CREDENTIALS_FILE = os.path.expanduser('~/.cherami-login')
if not os.path.exists(CREDENTIALS_FILE):
	oauth_dance("Cher Ami", TWITTER_CLIENT_ID, TWITTER_CLIENT_SECRET, CREDENTIALS_FILE)

auth = OAuth(*read_token_file(CREDENTIALS_FILE), TWITTER_CLIENT_ID, TWITTER_CLIENT_SECRET)
twitter = Twitter(auth=auth)
stream = TwitterStream(auth=auth, timeout=10)

who_am_i = twitter.account.verify_credentials()
my_id = who_am_i["id"]

def fix_extended_tweet(tweet):
	# Streaming mode doesn't include the full_text. It will show short tweets
	# with just "text", and longer ones with an "extended_tweet" that includes
	# the full text.
	if "extended_tweet" in tweet:
		tweet.update(tweet["extended_tweet"])
	if "full_text" not in tweet: tweet["full_text"] = tweet["text"]
	# FIXME: This sometimes doesn't catch every URL - some are left as t.co. Watch for an example.
	# TODO: Also catch media entries. The indices will need to be merged with URLs.
	# (Can I assume they'll never overlap? If so, build a mapping start=>replacement, sort, go.)
	# tweet->extended_entities->media[*]->indices
	# tweet->extended_entities->media[*]->video_info->variants[0]->url
	# What if there are multiple variants?
	for url in reversed(tweet["entities"]["urls"]):
		start, end = url["indices"]
		tweet["full_text"] = tweet["full_text"][:start] + url["expanded_url"] + tweet["full_text"][end:]

def print_tweet(tweet, indent=""):
	"""TODO:
	* Convert URLs using display_url, but retain the expanded_url and react to clicks
	* Retain the ID. If the marker is clicked, open the tweet in a browser.
	* Show tweet["source"] on request??
	"""
	try:
		fix_extended_tweet(tweet)
		# TODO: If it's a poll, show the options, or at least show that it's a poll.
		# (Polls should be shown as a form of media, same as attached images.)
		if "retweeted_status" in tweet:
			# Retweets have their own full_text, but it's often truncated. And
			# yet, the "truncated" flag is False. Go figure.
			fix_extended_tweet(tweet["retweeted_status"])
			tweet["full_text"] = ("RT @" + tweet["retweeted_status"]["user"]["screen_name"]
				+ ": " + tweet["retweeted_status"]["full_text"])
		label = indent + "@" + tweet["user"]["screen_name"] + ": "
		wrapper = textwrap.TextWrapper(
			initial_indent=label,
			subsequent_indent=" " * len(label),
			width=shutil.get_terminal_size().columns,
			break_long_words=False, break_on_hyphens=False, # Stop URLs from breaking
		)
		for line in tweet["full_text"].splitlines():
			print(wrapper.fill(line))
			wrapper.initial_indent = wrapper.subsequent_indent # For subsequent lines, just indent them
		# Some types of quoted tweets aren't currently getting shown properly.
		# See if there's a difference between (a) clicking Retweet and then
		# adding a message, and (b) clicking Tweet, and pasting in a tweet URL.
		if "quoted_status" in tweet:
			print_tweet(tweet["quoted_status"], indent=" " * len(label))
	except Exception as e:
		print("%%%%%%%%%%%%%%%%%%%%%%%%%%%")
		pprint(tweet)
		raise

log = open("cher-ami.json", "a", buffering=1)
seen_tweets = set()
def catchup(count):
	for tweet in reversed(twitter.statuses.home_timeline(count=count, tweet_mode="extended")):
		if tweet["id"] in seen_tweets: continue
		seen_tweets.add(tweet["id"])
		json.dump(tweet, log); print("", file=log)
		print_tweet(tweet)
		print("-- accepted: catchup --", file=log)

def spam_requests(last):
	# This would work, but the home_timeline API is rate-limited to 15 every 15 minutes.
	# So at best, we could get a 60-secondly poll.
	while True:
		print("---------")
		time.sleep(5)
		for tweet in reversed(twitter.statuses.home_timeline(since_id=last, count=2, tweet_mode="extended")):
			last = tweet["id"]
			print_tweet(tweet)

def stream_from_friends():
	# TODO: Notice if you follow/unfollow someone, and adjust this (or just return and re-call)
	# TODO: Switch to the Labs API instead and see if it copes with private accounts.
	# This API doesn't, which means that tweets from private accounts are only seen in catchup.
	following = twitter.friends.ids()["ids"] + [my_id]
	no_retweets = twitter.friendships.no_retweets.ids()
	for tweet in stream.statuses.filter(follow=",".join(str(f) for f in following), tweet_mode="extended"):
		if tweet is Timeout:
			# TODO: If it's been more than a minute, ping the timeline for any
			# we missed.
			continue
		if "id" not in tweet: continue # Not actually a tweet (and might be followed by the connection closing)
		json.dump(tweet, log); print("", file=log)
		if "retweeted_status" in tweet:
			if not tweet["is_quote_status"] and tweet["retweeted_status"]["id"] in seen_tweets:
				continue # Ignore plain retweets where we've seen the original
			if tweet["user"]["id"] in no_retweets: continue # User requested not to see their RTs
			# Hopefully a quoting-retweet will still get shown.
		# Figure out if this should be shown or not. If I sent it, show it.
		# If someone I follow sent it and isn't a reply, show it. If it is
		# a reply to something I sent, show it. If it mentions me, show it.
		# Otherwise don't.
		from_me = tweet["user"]["id"] == my_id
		nonreply = tweet["in_reply_to_user_id"] is None
		if tweet["in_reply_to_user_id"] == tweet["user"]["id"]:
			# For self-replies, look for threads that start with something we would have
			# looked at. If you reply to someone else, then reply to your own reply, that
			# should be taken as a reply to the original someone else.
			if tweet["in_reply_to_status_id"] in seen_tweets: nonreply = True # Easy - we showed that one!
			# ? I think this will work. If you aren't mentioning anyone else, it's probably
			# a thread, not a reply to someone else. Ultimately, what I want to do is to
			# ask "Would we have shown the tweet that this is a reply to?".
			elif len(tweet["entities"]["user_mentions"]) == 1: nonreply = True
		# I'm assuming that any reply to a tweet of mine will list me among the mentions.
		mentions_me = my_id in [m["id"] for m in tweet["entities"]["user_mentions"]]
		if from_me or mentions_me or (tweet["user"]["id"] in following and nonreply):
			seen_tweets.add(tweet["id"])
			if "retweeted_status" in tweet: seen_tweets.add(tweet["retweeted_status"]["id"])
			print_tweet(tweet)
			if from_me: print("-- accepted: from me --", file=log)
			if mentions_me: print("-- accepted: mentions me --", file=log)
			else: print("-- accepted: author followed and %s --" % "non-reply" if nonreply else "self-reply", file=log)
	print("End of stream", time.time())

def main():
	catchup(25)
	print("---------")
	try:
		while True:
			stream_from_friends()
			# After disconnecting, do a timeline check to see if we missed any
			catchup(10)
	except KeyboardInterrupt:
		pass # Normal termination

if __name__ == "__main__": main()
