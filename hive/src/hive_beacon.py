"""Versioned LAN discovery and conservative nominal capacity transformation."""
import ipaddress
import json
import math
import re


def effective_times(endpoints,shares):
    total=math.fsum(1/e.last_test_ms for e in endpoints)
    return [dict(name=e.name,effective_ms=1/(shares[e.name]*total) if shares[e.name]>0 else None)
            for e in endpoints]


def aggregate_ms(engines):
    total=math.fsum(1/e['effective_ms'] for e in engines if e['effective_ms'] is not None)
    return 1/total if total else None


def decode(data):
    a=json.loads(data.decode('utf-8'))
    if not isinstance(a,dict) or a.get('protocol')!='HIVE' or a.get('version')!=1:raise ValueError('protocol')
    for key in ('node_id','boot_id'):
        if not isinstance(a.get(key),str) or not re.fullmatch('[0-9a-f]{32}',a[key]):raise ValueError(key)
    if type(a.get('master')) is not bool or type(a.get('sequence')) is not int or a['sequence']<1:raise ValueError('role/sequence')
    if a.get('event') not in ('STARTUP','UPDATE','RESPONSE','HEARTBEAT','SHUTDOWN'):raise ValueError('event')
    if not isinstance(a.get('name'),str) or not a['name'] or len(a['name'])>256:raise ValueError('name')
    if not isinstance(a.get('ip'),str):raise ValueError('ip')
    ip=ipaddress.IPv4Address(a['ip'])
    if ip.is_unspecified or ip.is_multicast or str(ip)=='255.255.255.255':raise ValueError('ip')
    if type(a.get('tcp_port')) is not int or not 1<=a['tcp_port']<=65535:raise ValueError('port')
    if not isinstance(a.get('engines'),list) or len(a['engines'])>1024:raise ValueError('engines')
    names=set()
    for e in a['engines']:
        if not isinstance(e,dict) or not isinstance(e.get('name'),str) or not e['name'] or e['name'] in names or 'effective_ms' not in e:raise ValueError('engine')
        names.add(e['name']);t=e['effective_ms']
        if t is not None and (type(t) not in (int,float) or not math.isfinite(t) or t<=0 or not math.isfinite(1/t)):raise ValueError('time')
    if a['event']=='SHUTDOWN' and a['engines']:raise ValueError('shutdown capacity')
    aggregate_ms(a['engines'])
    return a
