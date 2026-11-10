"""Console-only presentation of Nurse brain metadata."""

def format_external_tcp_line(details: dict) -> str:
    """One compact diagnostic line; never infer or validate remote identity."""
    host = details['requested']
    resolved = ', '.join(details['dns'])
    remote = details.get('uci_name') or '(no informado)'
    return f"   🌐 TCP {host} DNS=[{resolved}] name={remote}"


def benchmark_engine_heading(identity: str, config: dict, name: str | None = None) -> str:
    """Local brain name for UCI/Nurse; remote UCI id name for external."""
    display = name if config.get('type') == 'external' and name else identity
    return f"{display} ({config['player']} | {config['evaluator']} | {config.get('lc0-backend') or 'default'})"


