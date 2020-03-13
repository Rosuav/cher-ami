import sys
sys.modules["cherami"] = cherami = __import__("cher-ami")
from cherami import *
null, true, false = None, True, False # for easy JSON importing
import json
def t():
	global tweet
	tweet = json.loads(input("> "))
