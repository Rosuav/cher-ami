import sys
sys.modules["cherami"] = cherami = __import__("cher-ami")
from cherami import *
null, true, false = None, True, False # for easy JSON importing
import json
def t():
	global tweet
	tweet = json.loads(input("> "))

def find(s):
	with open("cher-ami.json") as f:
		for line in f:
			if not line.startswith("{"): continue
			tw = json.loads(line)
			txt = tw.get("full_text", tw.get("text", ""))
			if s in txt:
				print(tw["created_at"], "@" + tw["user"]["screen_name"])
				global tweet
				tweet = tw
