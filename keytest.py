import tty, sys, termios
old_settings = termios.tcgetattr(sys.stdin)
try:
	tty.setcbreak(sys.stdin)
	while True:
		ch = sys.stdin.read(1)
		print(ch)
		if ch == "q" or ch == b"q": break
finally:
	termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
