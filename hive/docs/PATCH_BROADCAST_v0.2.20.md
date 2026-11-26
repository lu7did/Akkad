# Hive v0.2.20 — LAN discovery and master/subordinate load balancing

Incremental patch over v0.2.19 (which requires v0.2.18). Apply at Akkad root.
The operational hive.yml is not overwritten. Merge the top-level keys from
hive/etc/hive.broadcast.example.yml. Set master: true on exactly one Hive,
master: false on its subordinates. Replace any old boolean broadcast setting
with a positive numeric interval in minutes; default 5. UDP port default 6251,
configurable with existing udp_port or broadcast_port alias. Keep the TCP port
and engine definitions specific to each machine. If needed, set advertise_ip
explicitly for the LAN interface. All participating Hives need v0.2.20.
Old hive_network / broadcast_seconds / max_hive_probe_jobs settings no longer
control discovery/probing. No engine or FICS change is required.

## Protocol and capacity
UDP IPv4 broadcast 255.255.255.255, JSON protocol HIVE version 1. Fields:
node_id (existing HiveNodeID), boot_id, sequence, name, ip, tcp_port, master,
event, engines [{name,effective_ms}]. Events STARTUP (after TCP bind and initial
calibration), UPDATE (new published resource generation, including periodic
recalibration or release of master session), HEARTBEAT (broadcast minutes),
RESPONSE (only to a foreign STARTUP), and best-effort SHUTDOWN (empty capacity).
Self and duplicate/out-of-order per-boot sequence messages are ignored. A
foreign master is detected for diagnostics but never incorporated. Non-masters
never initiate discovered Hive links. A subordinate never republishes remote
capacity; a master advertises its local-only distribution. Each snapshot is
published after completing the corresponding allocation, not during probing.

With T_i in ms, S=sum(1/T_i), local constrained K_i, effective_ms=1/(K_i*S).
Zero K_i is encoded as null (zero advertised capacity), not JSON Infinity.
The master sums inverse advertised times and represents the result as one
remote endpoint with kmin=0 and kmax=1. This is equivalent for the continuous
allocation because individual remote minima are zero and maxima are one.
The subordinate retains its own internal integer move allocation. Nominal
conservation is not a guarantee of physical throughput. The master preserves
local kmin and caps all allocations with the existing optimizer. A fresh
remote advertisement updates the same TCP endpoint; no witness probe is
performed on it, including at periodic recalibration. An empty advertisement
removes its capacity without opening another socket. TCP loss removes it from
allocation; subsequent advertisements can reconnect it. Existing startup
validation remains: local configuration and calibrated startup set must be
feasible independently of discovered Hives.

## TCP and exclusivity
Only the master opens discovered links and sends `uci (master)` as the first
nonempty command. The subordinate atomically claims the master slot and returns
ordinary UCI identification, options and uciok. A second master connection
(including one from the same IP) or a master-to-master attempt is closed without
uciok. The owner is the live TCP session, not the IP address. Its release waits
for its search and workers to drain, then triggers an UPDATE beacon. All other
commands, including isready, position, go searchmoves, stop, and quit, remain
unchanged. Ordinary clients send `uci` and retain existing scheduling behavior,
including concurrency with a connected master; this patch does not add exclusive
ownership against FICS/GUI clients. Direct static TCP links to another Hive are
rejected after HiveNodeID is detected, avoiding bypass of master-only discovery.
Normal TCP/UCI engines are unaffected. A LAN with two configured masters is
reported, not automatically repaired or elected. First accepted connection wins
at each subordinate. No cryptographic authentication; use a trusted LAN. TCP
keepalive is enabled for Hive links, with OS default timeout; loss detection can
be delayed on an idle broken connection. Broadcast is limited to the local
IPv4 broadcast domain and depends on firewall/interface configuration.

## Tests
Run `python -m unittest discover -s hive/tests -v`. 31 tests passed under Linux
in the patch workspace, including 19 previous resource/affinity tests, 500
randomized feasible allocations within an existing test, and 12 new tests for
capacity conservation, zero-share encoding, role matrix, snapshot publication,
remote capacity updates, no remote probes, YAML validation, UDP loopback and
real loopback TCP handshake/rejection/release. The chess dependency was absent
in this environment; handshake tests mock Board, and resource tests use
simulated engines. No actual chess searches, multi-host LAN or Windows/macOS
network integration have been validated. Do not infer real network throughput
from these tests.
