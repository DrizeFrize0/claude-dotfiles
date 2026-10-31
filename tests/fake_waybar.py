import signal, sys, time, os
log = os.path.join(os.environ["STUBLOG"], "waybar.signals")
signal.signal(signal.SIGRTMIN + 8, lambda *_: open(log, "a").write("ws\n"))
time.sleep(20)
