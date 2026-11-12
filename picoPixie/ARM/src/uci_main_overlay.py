#!/usr/bin/env python3
'''Build-time picoPixie UCI overlay; source picoSargon remains untouched.

The replacements are intentionally exact: a future incompatible change in the
shared UCI driver must fail the build rather than silently skip integrity logic.
'''
import sys
from pathlib import Path

source=Path(sys.argv[1]).read_text(encoding="utf-8")
output=Path(sys.argv[2])

def replace_once(old,new):
    global source
    found=source.count(old)
    if found!=1:
        raise SystemExit(f"picoPixie UCI integration requires review: expected one anchor, found {found}: {old[:100]!r}")
    source=source.replace(old,new,1)

replace_once('#include "picolichess_adapter.hpp"', '#include "picolichess_adapter.hpp"\n#include "uci_transaction_queue.hpp"\n#include "engine_runtime.hpp"')
# Do not alter picoSargon sources. Adapt the obsolete global-throttle argument
# in the generated picoPixie-only UCI translation unit.
replace_once('board, millis(), runtime_config::THROTTLE,', 'board, millis(),')
replace_once('bool connected=false,request_stop=false,request_quit=false,valid_position=true,go_pending=false;',
'''bool connected=false,request_stop=false,request_quit=false,valid_position=true,go_pending=false;
#ifdef PICOSARGON_CLOUD_HOOK
picoLichess::UciTransactionQueue uci_deferred;
bool uci_search_active=false;
#endif''')
replace_once('else if(!cmd.empty())dispatch(cmd);',
'''else if(!cmd.empty()){
#ifdef PICOSARGON_CLOUD_HOOK
 // No position/ucinewgame/go may mutate the active transaction's board.
 // Include go_pending: several commands may arrive in the same TCP segment.
 if(uci_search_active || go_pending || !uci_deferred.empty()){
   if(!uci_deferred.push(std::move(cmd))){
     debug_log("UCI queue overflow: closing session instead of dropping commands\\n");
     request_stop=true;request_quit=true;session_error=true;++recoverable_errors;
   }
 }else dispatch(cmd);
#else
 dispatch(cmd);
#endif
}''')
replace_once('request_quit=false;request_stop=false;session_error=false;pending.clear();',
'''request_quit=false;request_stop=false;session_error=false;pending.clear();
#ifdef PICOSARGON_CLOUD_HOOK
uci_deferred.clear();go_pending=false;
#endif
''')
# Disconnect cleanly ends this session's deferred data. Stop cancels the
# active search; no queued command can be applied to a new client.
replace_once('connected=false;client=nullptr;status_led(',
'''connected=false;client=nullptr;
#ifdef PICOSARGON_CLOUD_HOOK
uci_deferred.clear();go_pending=false;request_stop=true;
#endif
status_led(''')
replace_once('client=nullptr;connected=false;request_stop=true;session_error=true;',
'''client=nullptr;connected=false;request_stop=true;
#ifdef PICOSARGON_CLOUD_HOOK
uci_deferred.clear();go_pending=false;
#endif
session_error=true;''')
replace_once('connected=false;request_stop=true;go_pending=false;pending.clear();',
'''connected=false;request_stop=true;go_pending=false;pending.clear();
#ifdef PICOSARGON_CLOUD_HOOK
uci_deferred.clear();
#endif''')
replace_once('if(client){tcp_abort(pcb);return ERR_ABRT;}client=pcb;',
'''if(client
#ifdef PICOSARGON_CLOUD_HOOK
 || uci_search_active
#endif
){tcp_abort(pcb);return ERR_ABRT;}client=pcb;''')
replace_once('  if(go_pending && connected && wifi_up)run_search();',
'''#ifdef PICOSARGON_CLOUD_HOOK
  // A bounded queue cannot silently discard commands; close on overflow/quit.
  if(request_quit && connected && !uci_search_active){
    if(client){tcp_recv(client,nullptr);tcp_err(client,nullptr);tcp_abort(client);client=nullptr;}
    connected=false;go_pending=false;uci_deferred.clear();pending.clear();
  }
  // The previous search must finish (including its bestmove) before any
  // queued ucinewgame/position/go gets dispatched, preserving FIFO order.
  if(connected && !request_quit && !go_pending && !uci_search_active && !uci_deferred.empty()){
    std::string command;
    if(uci_deferred.pop(command)) dispatch(command);
  }
  if(go_pending && connected && !request_quit && wifi_up){
    uci_search_active=true;
    run_search();
    uci_search_active=false;
  }
#else
  if(go_pending && connected && wifi_up)run_search();
#endif''')
# Resolve engine settings exactly once during startup, before UCI accepts work.
replace_once(' stdio_init_all();', ' stdio_init_all();\n picoLichess::initialize_engines();')
# Print effective configuration on the USB boot console, not only during
# the later UCI handshake.  This is after stdio is connected and the
# runtime engine table has been resolved; the names/values come from it.
replace_once('  debug_log("%s BOOT (USB debug connected)\\n",VERSION);',
'''  debug_log("%s BOOT (USB debug connected)\\n",VERSION);
  {
    std::string priority="SLOTS priority=[";
    for(unsigned i=0;i<picoLichess::config::SLOT_COUNT;++i){
      const auto& e=*picoLichess::engine_slot(i).settings;
      if(i) priority+=",";
      priority+=std::to_string(i)+":"+e.name;
    }
    debug_log("%s]\\n",priority.c_str());
    for(unsigned i=0;i<picoLichess::config::SLOT_COUNT;++i){
      const auto& e=*picoLichess::engine_slot(i).settings;
      debug_log("SLOT[%u] processor=%s THROTTLE=%dms TIMEGUARD=%dms depth=%d thinking_ms=%d verbose=%s key=%s url=%s\\n",
        i,e.name,e.throttle,e.timeguard,e.depth,e.thinking_time,
        e.verbose?"true":"false",e.key[0]?"configured":"none",e.url);
    }
  }''' )

# Engine configuration belongs exclusively to the one-time USB boot log.
# Do not inject it into the TCP/UCI handshake: those long lines may exhaust
# lwIP's send buffer, and standard UCI clients need only id/uciok at startup.
# Explicitly report exhausted slot chain, rather than silently returning
# without a bestmove and leaving UCI clients indefinitely waiting.
replace_once(' if(!outcome.fallback){\n   status_led(LedState::Ready);\n   return;\n }',
''' if(!outcome.fallback){
   if(outcome.no_evaluator && connected && !request_quit){
     send_line("info string error no-evaluator-available");
     send_line("bestmove 0000");
   }
   status_led(LedState::Ready);
   return;
 }''')
# On a disconnect during search, a stale bestmove must never reach another
# client. An attempted new accept is rejected until active search unwinds.
output.parent.mkdir(parents=True,exist_ok=True)
if not output.exists() or output.read_text(encoding="utf-8")!=source:
    output.write_text(source,encoding="utf-8")
