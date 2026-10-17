# Pico SargonPlus NPZ — v0.1.2 (independent experimental port)

**Target: Raspberry Pi Pico W (RP2040)**, Pico 2 W is not required *by the static model size*. This package is experimental, not a verified chess engine on physical MicroPython hardware.

## What is implemented

- Single self-contained fixed **Sargon-inspired alpha-beta** player; `depth=2`, `qdepth=2` (check/captures/promotions in qsearch), **no BOOST**. Fixed **TURBO 0x01-inspired** strategy: try full-width depth 1 then 2, retain last complete search if time budget expires. There is no engine/evaluator plugin architecture, and **the full PC SargonPlus implementation has not been reproduced bit-for-bit**.
- Minimal chess legal moves, FEN, castling, en passant and promotions, TCP single-client UCI; fixed configured port; Wi-Fi reconnection and transport cleanup. USB serial text telemetry for connect/commands/disconnect. Uses no external chess library on device.
- Fixed 781-64-1 model exported from user's `nnue_best.npz` to 50,400-byte custom `nnue.bin`. **Input matrix loaded once into SRAM** (49,984 bytes) at startup and retained there. All per-evaluation input-matrix accesses use direct indexed RAM; no disk reads. Biases float32, input INT8 with scale, output INT16 with scale, and halfmove term. Binary Adler32 integrity checked at startup. Model replacement requires converting and uploading new `nnue.bin` (restart device); not on-the-fly switchable.
- `config.bin` fixed-length binary holds name, SSID, password and TCP port with integrity check. Wi-Fi password is stored as **plaintext in the binary**; do not commit or share it.

## Build on Windows PC with Python and NumPy

```powershell
cd Pico_SargonPlus_NPZ_v0.1.2
python -m pip install numpy mpremote
python tools/convert_nnue.py C:\path\to\nnue_best.npz -o device/nnue.bin
python tools/compare_nnue.py C:\path\to\nnue_best.npz -n 200
python tools/make_config.py --name "Pico SargonPlus NPZ" --ssid "MY_SSID" --port 6110 -o device/config.bin
python -m unittest discover -s tests -v
```

The config utility interactively requests the Wi-Fi password unless `--password` is supplied. It does not print the password. Install a Pico W MicroPython UF2 compatible with Pico W manually, then connect the board USB for its MicroPython serial port:

```powershell
python tools/deploy.py --port COM6
```

After resetting, watch the serial REPL to obtain the IP address. Configure a UCI chess GUI or TCP bridge to connect to `<PICO_IP>:6110`, or test using `tools/uci_client.py`. **VS Code** can edit this folder directly; use its terminal and `mpremote` for upload, rather than copying all development/reference files to the Pico.

## Constraints and risks

1. Pico W has **264 KB physical SRAM, not 264 KB of free MicroPython heap**. Peak heap after import, after Wi-Fi/TCP, and during `go` must be measured on the actual board (`gc.mem_free()`). The resident matrix consumes about 49 KB of heap; memory must be measured after Wi-Fi/TCP initialization and at peak search. Python move generation may still be too slow for normal chess clock settings.
2. Search has a fixed depth ceiling 2. If time expires before any complete depth, a legal fallback move is chosen; it is **not** claimed to be strength-equivalent to PC SargonPlus. `stop` / disconnect are polled during search, so reaction is bounded by evaluation/check intervals, not instantaneous.
3. Chess rules are simplified: no complete threefold repetition tracking inside search, no 75-move / fivefold automatic draw detection and no insufficient-material draw detection. The network feature *en-passant* matches `python-chess` only when a legal EP capture exists.
4. `go infinite` and `ponder` are not supported; commands `setoption`, `debug`, `register` are ignored. `go` without a time control uses a 5-second cap. Only one TCP session is active. `position` is validated atomically, but malformed FEN castling-right combinations may still be accepted.
5. Physical hardware: **not tested** on Pico W or Pico 2 W. **Not proven:** UCI compliance under all GUI behaviors, timing accuracy, peak RAM, link stability, chess strength, quantization impact in played games, and full legal parity vs python-chess.

## Engineering acceptance gates on Pico W

- Verify boot/startup without `MemoryError`; print or inspect heap free at startup and after 10 sequential `go` commands.
- Verify Wi-Fi reconnect after AP down/up, clean TCP close and new session, `quit`, `ucinewgame`, stop while searching, malformed input, and no spurious `bestmove 0000` outside terminal positions/fatal errors.
- Benchmark depths 1/2 on start position and several midgames against wall time; compare bestmove and scoring with native PC SargonPlus without claiming equality.
- Use chess reference positions to compare legal moves, perft counts, checks, promotions and draws to an independent implementation. Only after this gate describe it as tournament-capable.

## License / lineage

Independent research port for Dr. Pedro E. Colla, 2026, developed using the Sargon-NNUE source as an algorithmic and network-format reference. User project attribution: **CC BY-SA 4.0** (confirm original repository LICENSE before distribution). No LC0/TinyGyal code or weights are included.

## v0.1.2 — resident-weight variant (17 October 2026)

This is an experiment specifically to remove per-feature file seek/read overhead. `nnue.bin` remains on filesystem for installation, but it is loaded **only once** at startup into a single `bytearray(49984)` and CRC-checked. Weights remain alive for the server process lifetime. Startup reports `heap_before` and `heap_after` in serial telemetry, where `-1` indicates a desktop interpreter without `gc.mem_free`. No unvalidated automatic fallback to streaming. The file header, quantization and neural arithmetic have not changed.

**Hardware gate**: with Pico W and Wi-Fi active, verify remaining heap after first client connects, and after search. A failed `MemoryError` means we must consider frozen constant weights/XIP or a native evaluator, not simply assume the 264 KiB SRAM is available to Python.

RP2040 XIP is a memory-mapped external flash access mechanism, *not* flash-backed virtual RAM. A normal filesystem `.bin` has no stable address to hand to an arbitrary `machine.mem8` lookup. Building the weights as a frozen `bytes` module in a custom MicroPython firmware is a promising **future alternative** that could keep immutable data in flash; it has not been implemented or tested in this release. The hardware XIP cache is only 16 KiB, so access patterns will affect speed.

Test: `python -m unittest discover -s tests -v` on desktop. Device startup and physical memory usage remain unverified.

## v0.1.2 — onboard LED (Pico W)

Uses `machine.Pin('LED')` (Wi-Fi Pico W firmware: onboard LED via CYW43) and a `machine.Timer(-1)` hardware timer. Blinking continues during blocking TCP receive, sleep, and synchronous engine search, using `micropython.schedule()` to switch the CYW43-controlled LED outside hardware IRQ context, without serial output from the timer callback. The LED states are:

| State | LED indication | Transition |
|---|---|---|
| Initializing, loading NNUE, reconnecting Wi-Fi | Solid ON | Power-on / Wi-Fi disconnected / server restart |
| UCI TCP server listening, no client | 1-second complete blink cycle (0.5 s ON, 0.5 s OFF) | Server starts listening or client disconnects |
| TCP client connected / game session active | 3-second complete blink cycle (1.5 s ON, 1.5 s OFF) | TCP connection accepted; stays active through `go` |
| Unrecoverable boot/initialization exception | 200-ms complete blink cycle (100 ms ON, 100 ms OFF) | Fatal exception in `boot()` |

A recoverable Wi-Fi/socket error transitions to initializing and retries; it is **not** treated as fatal. The timer is reconfigured only on state transitions. The LEDs are independent of UCI stdout; no heartbeat lines are added to UCI protocol. Full-cycle interpretation of timing is deliberate. **Hardware validation is pending:** the Pico W `LED` pin and Timer implementation must be verified with the installed MicroPython firmware.
