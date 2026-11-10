import subprocess

engine = r"C:\Users\pedro\github\bobby\stockfish\stockfish.exe"

p = subprocess.run(
    [engine],
    input=b"uci\nisready\nquit\n",
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    timeout=15
)

output = p.stdout.decode("utf-8", errors="replace")
errors = p.stderr.decode("utf-8", errors="replace")

print(output)
print("STDERR:", errors)
print("EXIT:", p.returncode)
print("UCIOK:", "uciok" in output.splitlines())
print("READYOK:", "readyok" in output.splitlines())
