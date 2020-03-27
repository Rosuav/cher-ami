import sys, os, subprocess
print("Mouse demo")
print("Click on any letter")
import tty, termios
fd = sys.stdin.fileno()
old_settings = termios.tcgetattr(fd)
last_click = None
try:
	tty.setcbreak(sys.stdin)
	print("\x1b[?1000;1006;1004h", end=""); sys.stdout.flush() # Mouse active
	while True:
		ch = os.read(fd, 1)
		if ch == b"\x1b" and os.read(fd, 1) == b"[": # CSI
			command = os.read(fd, 1)
			if command == b"M": # Mouse action, type 1000
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
			elif command == b"<": # Mouse action, type 1006
				params = b""
				while (chr := os.read(fd, 1)) not in b"Mm": params += chr
				params = [int(x) for x in params.decode().split(";")]
				is_release = chr == b"m"
				btn, x, y = params
				if btn == 64:
					subprocess.call(["xdotool", "key", "ctrl+F13"])
				elif btn == 65:
					subprocess.call(["xdotool", "key", "alt+F13"])
				else: print(btn, x, y, "up" if is_release else "down")
				continue
			elif command == b"I": # Mode 1004 (independent of the mouse actions)
				print("Focus gained")
				continue
			elif command == b"O":
				print("Focus lost")
				continue
			else:
				print("Unknown CSI", command)
		print(ascii(ch))
		if ch == "q" or ch == b"q": break
finally:
	termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
	print("\x1b[?1000;1006;1004l", end=""); sys.stdout.flush() # Mouse inactive
