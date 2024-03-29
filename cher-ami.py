import code
import json
import os
import readline
import shutil
import sys
import textwrap
import time
import threading
import traceback
import urllib
from pprint import pprint
sys.path.append("../mustard-mine") # Hack: Lift credentials from Mustard Mine if we don't have our own
from config import TWITTER_CLIENT_ID, TWITTER_CLIENT_SECRET
from twitter import OAuth, Twitter, oauth_dance, read_token_file
from twitter.stream import TwitterStream, Timeout, HeartbeatTimeout, Hangup
from twitter.api import TwitterHTTPError

CREDENTIALS_FILE = os.path.expanduser('~/.cherami-login')
if not os.path.exists(CREDENTIALS_FILE):
	oauth_dance("Cher Ami", TWITTER_CLIENT_ID, TWITTER_CLIENT_SECRET, CREDENTIALS_FILE)

auth = OAuth(*read_token_file(CREDENTIALS_FILE), TWITTER_CLIENT_ID, TWITTER_CLIENT_SECRET)
twitter = Twitter(auth=auth)
stream = TwitterStream(auth=auth, timeout=60)

who_am_i = twitter.account.verify_credentials()
my_id = who_am_i["id"]

displayed_tweets = {"": 0}
def fix_extended_tweet(tweet):
	# Streaming mode doesn't include the full_text. It will show short tweets
	# with just "text", and longer ones with an "extended_tweet" that includes
	# the full text.
	if "extended_tweet" in tweet:
		tweet.update(tweet["extended_tweet"])
	if "full_text" not in tweet: tweet["full_text"] = tweet["text"]
	replace = {url["indices"][0]: (url["indices"][1], url["expanded_url"]) for url in tweet["entities"]["urls"]}
	for media in tweet.get("extended_entities", {}).get("media", ()):
		if "video_info" in media:
			# For videos, pick the best - currently just going for highest
			# bitrate and hoping that quantity correlates with quality
			url = max(media["video_info"]["variants"], key=lambda v: v.get("bitrate", 0))["url"]
		else:
			url = media["media_url_https"]
		# NOTE: If multiple images are attached to a tweet, they (might?) get
		# the *same* indices. The spares just get tacked onto the end.
		if media["indices"][0] in replace:
			tweet["full_text"] += " "
			p = len(tweet["full_text"])
			replace[p] = (p, url) # Remove nothing, keep the space.
		else:
			replace[media["indices"][0]] = (media["indices"][1], url)
	for start in sorted(replace, reverse=True):
		end, replacement = replace[start]
		tweet["full_text"] = tweet["full_text"][:start] + replacement + tweet["full_text"][end:]
	# Twitter replaces <>& with entities, for some reason.
	# NOTE: If a URL contains "&lt;" in it, Twitter breaks stuff. It kinda
	# severs the URL but doesn't have any gap after it, so the only way for
	# Cher Ami to get it even compatible with the Twitter UI (never mind
	# "right") would be to add its own gap. For now, I'm going to assume
	# that this won't ever happen; having "&lt=foo" is okay, and that's what
	# you're more likely to see anyway.
	tweet["full_text"] = tweet["full_text"].replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

seen_tweets = set()
def print_tweet(tweet, indent=""):
	"""TODO:
	* Convert URLs using display_url, but retain the expanded_url and react to clicks
	* Retain the ID. If the marker is clicked, open the tweet in a browser.
	"""
	try:
		seen_tweets.add(tweet["id"])
		if "retweeted_status" in tweet: seen_tweets.add(tweet["retweeted_status"]["id"])
		fix_extended_tweet(tweet)
		# TODO: If it's a poll, show the options, or at least show that it's a poll.
		# (Polls should be shown as a form of media, same as attached images.)
		# Check if polls look different in home_timeline vs stream??
		displayed_tweets[""] += 1
		ref = displayed_tweets[""] % 260
		ref = chr(ref // 10 + 0x61) + chr(ref % 10 + 0x30)
		displayed_tweets[ref] = tweet # Retain the tweet under its two-letter code reference
		if "retweeted_status" in tweet:
			# Retweets have their own full_text, but it's often truncated. And
			# yet, the "truncated" flag is False. Go figure.
			fix_extended_tweet(tweet["retweeted_status"])
			tweet["full_text"] = ("RT @" + tweet["retweeted_status"]["user"]["screen_name"]
				+ ": " + tweet["retweeted_status"]["full_text"])
			# For retweets, retain the retweeted tweet rather than the retweet.
			# This means, for instance, that attempting to open it in a browser will show
			# the original, not the retweet.
			displayed_tweets[ref] = tweet["retweeted_status"]
		# NOTE: In order to make things line up nicely without having ANSI codes mess it up,
		# we use a couple of Unicode private-use characters to represent an ellipsis and an
		# escape code. It needs one character of width (for the ellipsis) and should count as
		# such to the textwrap module (since it's one character here).
		label = f"{indent}\U0010cc32{ref}\U0010cc00 @{tweet['user']['screen_name']}: "
		wrapper = textwrap.TextWrapper(
			initial_indent=label,
			subsequent_indent=indent + " " * 12,
			width=shutil.get_terminal_size().columns,
			break_long_words=False, break_on_hyphens=False, # Stop URLs from breaking
		)
		for line in tweet["full_text"].splitlines():
			print(wrapper.fill(line)
				.replace("\U0010cc32", "\x1b[32m\u2026") # Colour start
				.replace("\U0010cc00", "\u2026\x1b[0m") # Colour end
			)
			wrapper.initial_indent = wrapper.subsequent_indent # For subsequent lines, just indent them
		# Some types of quoted tweets aren't currently getting shown properly.
		# See if there's a difference between (a) clicking Retweet and then
		# adding a message, and (b) clicking Tweet, and pasting in a tweet URL.
		if "quoted_status" in tweet:
			print_tweet(tweet["quoted_status"], indent=wrapper.subsequent_indent)
	except Exception as e:
		print("%%%%%%%%%%%%%%%%%%%%%%%%%%%")
		pprint(tweet)
		raise

def get_following(_cache={}):
	if _cache.get("stale", 0) < time.time():
		_cache["following"] = twitter.friends.ids()["ids"] + [my_id]
		_cache["no_retweets"] = twitter.friendships.no_retweets.ids()
		_cache["stale"] = time.time() + 900
	return _cache["following"], _cache["no_retweets"]

# log = open("cher-ami.json", "a", buffering=1)

def interesting_tweet(tweet):
	"""Figure out whether a tweet is 'interesting' or not

	Interesting tweets get shown to the user. Uninteresting ones do not.
	The exact rules are complicated but generally immaterial.
	Returns (True, "some reason") or (False, "some reason")
	"""
	following, no_retweets = get_following()
	if "retweeted_status" in tweet:
		if not tweet["is_quote_status"] and tweet["retweeted_status"]["id"] in seen_tweets:
			return False, "Retweet of something we've seen"
		if tweet["user"]["id"] in no_retweets:
			return False, "Retweet from a filtered-RTs user"
		# Hopefully a quoting-retweet will still get shown.
	if tweet["user"]["id"] == my_id: return True, "from me"
	# I'm assuming that any reply to a tweet of mine will list me among the mentions.
	if my_id in [m["id"] for m in tweet["entities"]["user_mentions"]]:
		return True, "mentions me"
	if tweet["user"]["id"] not in following:
		# Can happen with the streaming API - replies to people I follow
		# can be shown. I don't want them.
		return False, "not from someone I follow"
	if tweet["in_reply_to_user_id"] is None:
		return True, "author followed and non-reply"
	if tweet["in_reply_to_user_id"] == tweet["user"]["id"]:
		# For self-replies, look for threads that start with something we would have
		# looked at. If you reply to someone else, then reply to your own reply, that
		# should be taken as a reply to the original someone else.
		if tweet["in_reply_to_status_id"] in seen_tweets:
			return True, "author followed and self-reply to shown tweet"
		# ? I think this will work. If you aren't mentioning anyone else, it's probably
		# a thread, not a reply to someone else. Ultimately, what I want to do is to
		# ask "Would we have shown the tweet that this is a reply to?". I'm not sure
		# why, but sometimes you are in your own mention list and sometimes not.
		elif {m['id'] for m in tweet["entities"]["user_mentions"]} <= {tweet["user"]["id"]}:
			return True, "author followed and pure self-reply"
	return False, "no reason to display it"

last_catchup = 0.0
def catchup(count):
	global last_catchup
	t = time.time()
	if t > last_catchup + 600: last_catchup = t
	else: return # Been less than three minutes? No need to catch up.
	lastid = None
	for tweet in reversed(twitter.statuses.home_timeline(count=count, tweet_mode="extended")):
		lastid = tweet["id"]
		if tweet["id"] in seen_tweets: continue
		# json.dump(tweet, log); print("", file=log)
		print_tweet(tweet)
		# print("-- accepted: catchup --", file=log)
	return lastid

def spam_requests(last):
	# This would work, but the home_timeline API is rate-limited to 15 every 15 minutes.
	# So at best, we could get a 60-secondly poll.
	while True:
		time.sleep(120)
		for tweet in reversed(twitter.statuses.home_timeline(since_id=last, count=25, tweet_mode="extended")):
			last = tweet["id"]
			print_tweet(tweet)

report_status = False
def stream_from_friends():
	# TODO: Notice if you follow/unfollow someone, and adjust this (or just return and re-call)
	# TODO: Switch to the Labs API instead and see if it copes with private accounts.
	# This API doesn't, which means that tweets from private accounts are only seen in catchup.
	for tweet in stream.statuses.filter(follow=",".join(str(f) for f in get_following()[0]), tweet_mode="extended"):
		if report_status: print("Yielded:", tweet)
		if tweet is Timeout:
			catchup(10)
			continue
		if "id" not in tweet: continue # Not actually a tweet (and might be followed by the connection closing)
		# json.dump(tweet, log); print("", file=log)
		keep, why = interesting_tweet(tweet)
		if not keep: continue
		print_tweet(tweet)
		# print("-- accepted: %s --" % why, file=log) # Don't print the why for those we discard
	# print("End of stream", time.time())

def stream_forever():
	while True:
		try:
			stream_from_friends()
			# After disconnecting, do a timeline check to see if we missed any
			catchup(10)
		except (TwitterHTTPError, urllib.error.URLError) as e:
			print(e)
			time.sleep(30)

def main():
	lastid = catchup(25)
	print("---------")
	threading.Thread(target=spam_requests, args=(lastid,), daemon=True).start()
	interp = code.InteractiveConsole({"tweet": displayed_tweets})
	prefix = prompt = ""
	try:
		while True:
			cmd = prefix + input(prompt)
			prefix = prompt = "" # One-time prefix and prompt - will be reactivated if needed
			if cmd == "quit": break
			elif cmd == "": continue
			elif cmd == "help": print("Type a tweet code to open it in a browser") # TODO: Or other actions?
			elif cmd == "bt":
				# Show backtraces from all other threads - might help diagnose CPU load issues
				# Normally that's just the stream_forever thread.
				me = threading.current_thread().ident
				for thrd, frm in sys._current_frames().items():
					if thrd == me: continue
					print("Thread", thrd, "--->")
					traceback.print_stack(frm)
					print()
					interp.locals["frm"] = frm
			elif cmd == "report":
				global report_status
				report_status = not report_status
				print("Will %s report yielded values." % ["not", "now"][report_status])
			elif cmd.startswith("x "):
				if interp.push(cmd[2:]):
					# We need more text. Show the continuation prompt and send the
					# next (one) line back into the REPL.
					prefix, prompt = "x ", "... "
			elif cmd in displayed_tweets:
				tweet = displayed_tweets[cmd]
				# It seems that getting the username wrong doesn't even
				# matter - Twitter will just redirect you.
				url = "https://twitter.com/x/status/%s" % tweet["id"]
				source = tweet.get("source", "<UNKNOWN>")
				if source.startswith("<a"): # it usually will
					source = source.split(">", 1)[1].replace("</a>", "")
				print("Tweet from", tweet["user"]["screen_name"], "via", source)
				import webbrowser
				webbrowser.open(url)
			else:
				print("Unknown command", cmd, "-- 'help' for help")
	except (KeyboardInterrupt, EOFError):
		pass # Normal termination

if __name__ == "__main__": main()
