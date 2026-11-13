"""Declarative configuration, platform selection and deterministic path resolution."""
import json,os,sys,shutil,hashlib
from urllib.parse import urlsplit
from pathlib import Path

NATIVE = {"sargon", "sargon-plus", "random", "doc", "microchess", "cerebrum", "keras", "alphazero", "bellman", "mctsp"}
EVALUATORS = {"null","classic","npz","cerebrum","cerebrum-1.1","cerebrum-2","stockfish","lc0","tinygyal","znpz","zclassic","grumpy","keras","microchess","bellmanr", "mctse"}

def platform_name():
    return "windows" if os.name=="nt" else "macOS" if sys.platform=="darwin" else "debian"

def platform_value(value):
    if isinstance(value,dict):
        p=platform_name()
        names=(p,p.lower(),"macos" if p=="macOS" else p)
        for k in names:
            if k in value:return value[k]
        raise ValueError(f"falta configuración de plataforma {p}")
    return value

def resolve_path(value,brains_path, *, executable=False):
    value=platform_value(value)
    if not isinstance(value,str) or not value.strip():raise ValueError("ruta inválida")
    path=Path(value).expanduser()
    if path.is_absolute():return str(path)
    # The first base is the source configuration; additionally accept the
    # historical Akkad layout (Sargon-NNUE/scripts) for legacy paths.
    bases=[Path(brains_path).resolve().parent,Path(brains_path).resolve().parent.parent.parent,
           Path(brains_path).resolve().parent.parent.parent/'scripts',Path.cwd()]
    # If `brains` sits under nurse/etc/brains, allow Akkad/Sargon-NNUE/scripts.
    for base in [Path(brains_path).resolve().parents[3]/'Sargon-NNUE'/'scripts'] if len(Path(brains_path).resolve().parents)>3 else []:
        bases.append(base)
    candidates=[(base/path).resolve() for base in bases]
    for candidate in candidates:
        if candidate.exists():return str(candidate)
    if executable and len(path.parts)==1 and shutil.which(value):return shutil.which(value)
    raise ValueError(f"ruta inexistente {value!r}; probadas: {', '.join(map(str,candidates))}")

def read_brains(path):
    with open(path,encoding="utf-8-sig") as f:data=json.load(f)
    if not isinstance(data,dict) or not isinstance(data.get("brains"),dict):raise ValueError("se requiere objeto brains")
    return data["brains"]

def brain_fingerprint(path, ident):
    """Cryptographically bind a subprocess to the precise brain JSON entry."""
    brains = read_brains(path)
    if ident not in brains:
        raise ValueError(f"brain desconocido: {ident}")
    payload = json.dumps(brains[ident], sort_keys=True, ensure_ascii=False,
                         separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()

def parse_uci_options(value):
    """Normalize generic UCI setoption declarations; no engine-specific knowledge.

    Dict: {"Skill Level": 5, "Clear Hash": null}
    List: [{"name":"Skill Level","value":5}, {"name":"Clear Hash"}]
    """
    if value is None:
        return []
    if isinstance(value, dict):
        items = list(value.items())
    elif isinstance(value, list):
        items = []
        for item in value:
            if not isinstance(item, dict) or set(item)-{"name", "value"} or "name" not in item:
                raise ValueError("uci_options: cada elemento requiere name y opcionalmente value")
            items.append((item["name"], item.get("value")))
    else:
        raise ValueError("uci_options requiere mapa o lista de objetos name/value")
    out = []
    for name, value in items:
        if not isinstance(name, str) or not name.strip() or "\n" in name or "\r" in name:
            raise ValueError("uci_options: nombre inválido")
        if value is not None and (not isinstance(value, (bool,int,float,str)) or "\n" in str(value) or "\r" in str(value)):
            raise ValueError(f"uci_options: valor inválido para {name!r}")
        if isinstance(value, bool):
            value = "true" if value else "false"
        elif value is not None:
            value = str(value)
        out.append((name, value))
    return out

def parse_external_endpoint(cfg):
    """Return (hostname, port), or fail closed on ambiguous/missing endpoints.

    Supported: url='picosargon.local:6110', url='tcp://host:6110',
    url='[2001:db8::1]:6110', or ipaddress + port.
    No network fallback or engine selection is allowed.
    """
    from_url = None
    if "url" in cfg:
        raw = cfg["url"]
        if not isinstance(raw, str) or not raw.strip() or raw != raw.strip():
            raise ValueError("external.url debe ser 'hostname:port'")
        if any(ch.isspace() for ch in raw):
            raise ValueError("external.url no admite espacios")
        if "://" in raw and not raw.startswith("tcp://"):
            raise ValueError("external.url solo admite el esquema opcional tcp://")
        try:
            parsed = urlsplit(raw if "://" in raw else "tcp://" + raw)
            if (parsed.scheme != "tcp" or not parsed.hostname or
                    parsed.username is not None or parsed.password is not None or
                    parsed.path or parsed.query or parsed.fragment):
                raise ValueError("se requiere host:port sin ruta, credenciales ni query")
            port = parsed.port
        except ValueError as exc:
            raise ValueError(f"external.url inválida: {raw!r}: {exc}") from exc
        if port is None or not 1 <= port <= 65535:
            raise ValueError("external.url requiere un puerto TCP entre 1 y 65535")
        from_url = (parsed.hostname, port)

    from_fields = None
    if "ipaddress" in cfg or "port" in cfg:
        host = cfg.get("ipaddress")
        port = cfg.get("port")
        if not isinstance(host,str) or not host.strip() or host != host.strip():
            raise ValueError("external requiere ipaddress no vacío junto a port")
        if isinstance(port,bool) or not isinstance(port,int) or not 1 <= port <= 65535:
            raise ValueError("external.port debe ser entero entre 1 y 65535")
        if any(c in host for c in "/\\@") or any(c.isspace() for c in host):
            raise ValueError("external.ipaddress debe ser un host, sin ruta ni puerto")
        from_fields = (host,port)

    if from_url is None and from_fields is None:
        raise ValueError("brain external sin destino TCP: indicar url='host:port' o ipaddress y port")
    if from_url is not None and from_fields is not None:
        if from_url[0].casefold() != from_fields[0].casefold() or from_url[1] != from_fields[1]:
            raise ValueError(f"external tiene destinos contradictorios: url={from_url} ipaddress/port={from_fields}")
    return from_fields or from_url

def read_brain(path,ident):
    brains=read_brains(path)
    if ident not in brains:raise ValueError(f"brain desconocido: {ident}")
    cfg=dict(brains[ident])
    # Shared timing contract, milliseconds, for ALL brain types.
    # tmax is the maximum thinking budget; timeout is communication tolerance.
    for key, default in (("tmax", 15000), ("timeout", 30000)):
        value = cfg.get(key, default)
        if isinstance(value, bool):
            raise ValueError(f"{key} debe ser entero positivo en milisegundos")
        try:
            value = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} debe ser entero positivo en milisegundos") from exc
        if value < 1:
            raise ValueError(f"{key} debe ser mayor que cero")
        cfg[key] = value
    # Warmup is intentionally as expensive as an ordinary move, by contract.
    # Do not admit a divergent warmup budget in brains.json.
    if "warmup_movetime" in cfg and int(cfg["warmup_movetime"]) != cfg["tmax"]:
        raise ValueError("warmup_movetime debe ser igual a tmax")
    cfg["warmup_movetime"] = cfg["tmax"]
    # The transport MUST be explicit.  Never infer it from `player`, an
    # incomplete legacy record, or any default host/port. In particular,
    # player=external without type=external is an error, not a fallback.
    raw_type = cfg.get("type")
    if not isinstance(raw_type, str) or raw_type.strip().lower() not in {"nurse", "uci", "external"}:
        raise ValueError(
            f"brain {ident!r}: type obligatorio: 'nurse', 'uci' o 'external'; "
            "no se infiere desde player"
        )
    typ = raw_type.strip().lower()
    cfg["type"] = typ
    if "ELO" in cfg and (isinstance(cfg["ELO"],bool) or not isinstance(cfg["ELO"],(int,float))):raise ValueError("ELO inválido")
    if "network" in cfg:
        raise ValueError("network debe estar exclusivamente dentro de evaluator para type=nurse; para type=uci usar args con --weights y ruta por plataforma")
    if typ=="nurse":
        if "uci_options" in cfg:raise ValueError("uci_options solo aplica a motores UCI (uci/external)")
        name=str(cfg.get("player","")).replace(".py","").replace("_","-").lower()
        if name not in NATIVE:raise ValueError(f"player no portado: {name}")
        evaluator_cfg=cfg.get("evaluator","null")
        if isinstance(evaluator_cfg,dict):
            if set(evaluator_cfg)-{"evaluator","network"}:
                raise ValueError("evaluator admite solamente evaluator y network")
            if "evaluator" not in evaluator_cfg:
                raise ValueError("evaluator.evaluator es obligatorio")
            ev=evaluator_cfg["evaluator"]
            network=evaluator_cfg.get("network")
        else:
            ev=evaluator_cfg
            network=None
        if ev is None:ev="null"
        if not isinstance(ev,str):raise ValueError("evaluator.evaluator debe ser string o null")
        evname=ev.replace(".py","").lower()
        if evname not in EVALUATORS:
            cfg["_evaluator_path"]=resolve_path(ev,path,executable=True)
            evname='external-evaluator'
        if name=='mctsp' and evname!='mctse':
            raise ValueError('MCTSP requiere evaluator=MCTSE')
        if evname=='mctse' and name!='mctsp':
            raise ValueError('MCTSE solo admite player=MCTSP')
        if name=='mctsp' and network is None:
            raise ValueError('MCTSP/MCTSE requieren evaluator.network')
        if evname=='null' and network is not None:
            raise ValueError("evaluator=null no admite network")
        cfg["_player"]=name;cfg["_evaluator"]=evname
        if network is not None:
            cfg["_network"]=resolve_path(network,path)
        args=cfg.get("arguments",{})
        if not isinstance(args,dict):raise ValueError("arguments requiere objeto")
        if "Depth" in cfg and int(cfg["Depth"])<1:raise ValueError("Depth debe ser >=1")
    elif typ=="uci":
        if str(cfg.get("evaluator","null")).lower()!="null":raise ValueError("type=uci requiere evaluator=null")
        cfg["_engine"]=resolve_path(cfg.get("player"),path,executable=True)
        # A UCI engine owns its weights. Paths belong to the startup argv,
        # not to Nurse's evaluator schema. No implicit {network} expansion.
        args=platform_value(cfg.get("args",[]))
        if not isinstance(args,list) or not all(isinstance(a,str) for a in args):
            raise ValueError("args debe ser lista de strings o mapa por plataforma de listas")
        if any("{network}" in a for a in args):
            raise ValueError("{network} fue eliminado: declarar la ruta de los pesos directamente en args por plataforma")
        cfg["_args"]=list(args)
        cfg["_uci_options"]=parse_uci_options(cfg.get("uci_options", {}))
    else:
        # `player` is not a selector for external transport.  Accept null,
        # omitted, and the historical sentinel 'external' only, without
        # allowing a different executable/brain to be silently selected.
        external_player = cfg.get("player")
        if external_player is not None and not (
            isinstance(external_player, str)
            and external_player.strip().lower() in ("null", "external")
        ):
            raise ValueError(
                f"brain {ident!r}: type=external admite player=null, "
                "player='external' o player omitido"
            )
        host,port=parse_external_endpoint(cfg)
        cfg["ipaddress"]=host
        cfg["port"]=port
        if "evaluator" in cfg and str(cfg["evaluator"]).lower()!="null":
            raise ValueError("type=external requiere evaluator=null")
        try:
            retry=float(cfg.get("retry",5))
        except (TypeError,ValueError) as exc:
            raise ValueError("external.retry debe ser un número positivo de segundos") from exc
        if not (0 < retry < float("inf")):
            raise ValueError("external.retry debe ser un número positivo de segundos")
        cfg["retry"]=retry
        # The remote's UCI id name is descriptive, not an authorization token.
        # Arbitrary hostnames, aliases and engine names are supported.
        cfg["_uci_options"]=parse_uci_options(cfg.get("uci_options", {}))
    cfg["_type"]=typ
    return cfg
