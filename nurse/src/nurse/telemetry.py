import sys,datetime,threading
_lock=threading.Lock()
def log(message):
    now=datetime.datetime.now().strftime("%H:%M:%S")
    with _lock:
        print(f"[{now}] {message}",file=sys.stderr,flush=True)
