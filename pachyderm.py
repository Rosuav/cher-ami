# What happens when a pigeon needs to become a pachyderm?
# Enter Mastodon support.
import requests
import clize
import config # ImportError? Copy config_sample.py to config.py and modify as needed.

commands = []
def command(f):
	commands.append(f)
	return f

@command
def register_app(*, appname="", website=""):
	if not appname: appname = input("Enter application name: ")
	if not website: website = input("Enter app web site: ")
	r = requests.post(config.MASTODON_SERVER + "/api/v1/apps", json={
		"client_name": appname,
		"redirect_uris": "urn:ietf:wg:oauth:2.0:oob", # TODO: Allow actual redirect
		"scopes": "read",
		"website": website,
	})
	r.raise_for_status()
	ret = r.json()
	with open("config.py", "a") as f:
		print("MASTODON_CLIENT_ID = %r" % ret["client_id"], file=f)
		print("MASTODON_CLIENT_SECRET = %r" % ret["client_secret"], file=f)
	print("Saved to config.py, edit as needed.")

if __name__ == "__main__":
	try: clize.run(commands)
	except KeyboardInterrupt: pass
