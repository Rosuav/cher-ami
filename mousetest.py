import sys, os
print("Mouse demo")
print("Click on any letter")
import tty, termios
fd = sys.stdin.fileno()
old_settings = termios.tcgetattr(fd)
last_click = None
try:
	tty.setcbreak(sys.stdin)
	print("\x1b[?1000h", end=""); sys.stdout.flush() # Mouse active
	while True:
		ch = os.read(fd, 1)
		if ch == b"\x1b" and os.read(fd, 1) == b"[":
			command = os.read(fd, 1)
			if command == b"M": # Mouse action
				buttons = os.read(fd, 1)[0]
				x = os.read(fd, 1)[0] - 32
				y = os.read(fd, 1)[0] - 32
				if buttons == 32: # Left click (probably)
					last_click = x, y
					continue
				elif buttons == 35 and last_click == (x, y): # Release
					print("Mouse click!", x, y)
				elif buttons == 96:
					... # Scroll up
				elif buttons == 97:
					... # Scroll down
				last_click = None
				print("Mouse action", buttons, x, y)
				continue
		print(ascii(ch))
		if ch == "q" or ch == b"q": break
finally:
	termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
	print("\x1b[?1000l", end=""); sys.stdout.flush() # Mouse inactive
