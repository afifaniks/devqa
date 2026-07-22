"""
SecDevQA — host-side egress policy for the per-item container.

Translates a run's intent (time-capped vs. +web, which model providers) into the podman network
flags and the ``SECDEVQA_*`` environment the in-container entrypoint (entrypoint.sh) consumes to
install the DNS-driven allowlist firewall. Validated behavior: with a restricted policy the
container reaches the allowlisted domains/hosts and nothing else — github.com, package registries,
and even direct-to-IP connections are dropped.

The `+web` condition uses an OPEN policy (no firewall, full internet); it intentionally breaks the
time-cap and is recorded with the distinct ``+web`` condition suffix elsewhere in the harness.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from harness.core.paths import RESOURCES_DIR

# slirp4netns exposes the host at this address when allow_host_loopback is set, so a host-local
# service (e.g. Ollama) is reachable here — local, not a time-cap leak.
HOST_GATEWAY = "10.0.2.2"
OLLAMA_HOSTPORT = f"{HOST_GATEWAY}:11434"

# Persisted, UI-editable allowlist config. Absent file → DEFAULT_CONFIG.
EGRESS_CONFIG_PATH = RESOURCES_DIR / "egress.json"

# Domains permitted under the time-capped (restricted) policy. Registration-domain granularity;
# the entrypoint's dnsmasq matches subdomains (api.anthropic.com, services.nvd.nist.gov, ...).
PROVIDER_DOMAINS = {
    # claude.ai included so subscription (OAuth) auth/token validation is reachable alongside
    # the api./console. endpoints under anthropic.com.
    "anthropic": ["anthropic.com", "claude.ai"],
    "openai": ["openai.com"],
}
# Canonical CVE/GHSA/CWE resolution sources for vuln_lookup (reference resolution, not a leak).
VULN_DOMAINS = ["osv.dev", "nist.gov", "mitre.org"]


@dataclass
class EgressPolicy:
    """Resolved egress intent for one run. `restricted=False` means open internet (+web)."""
    restricted: bool = True
    domains: list[str] = field(default_factory=list)
    hosts: list[str] = field(default_factory=list)   # ip:port literals allowed directly

    def env(self) -> dict[str, str]:
        """The ``SECDEVQA_*`` environment the entrypoint reads."""
        if not self.restricted:
            return {"SECDEVQA_EGRESS": "open"}
        return {
            "SECDEVQA_EGRESS": "restricted",
            "SECDEVQA_ALLOW_DOMAINS": ",".join(self.domains),
            "SECDEVQA_ALLOW_HOSTS": ",".join(self.hosts),
        }

    def podman_args(self) -> list[str]:
        """podman run flags: host-loopback networking, and NET_ADMIN/NET_RAW for the firewall."""
        args = ["--net", "slirp4netns:allow_host_loopback=true"]
        if self.restricted:
            args += ["--cap-add", "NET_ADMIN,NET_RAW"]
        return args


# ---------------------------------------------------------------------------
# Persisted config (edited from the monitor UI)
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "providers": ["anthropic", "openai"],   # which model-provider domains to allow
    "extra_domains": [],                    # operator-added domains (matches subdomains too)
    "allow_ollama": True,                   # reach the host's Ollama server
}


def load_config() -> dict:
    """The persisted egress config, merged over defaults. Never raises."""
    try:
        cfg = json.loads(EGRESS_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_CONFIG)
    return {**DEFAULT_CONFIG, **{k: cfg[k] for k in DEFAULT_CONFIG if k in cfg}}


def save_config(cfg: dict) -> dict:
    """Validate and persist the egress config; returns the cleaned config that was written.
    Only known model providers are accepted; domains are stripped and de-duplicated."""
    clean = {
        "providers": [p for p in (cfg.get("providers") or []) if p in PROVIDER_DOMAINS],
        "extra_domains": sorted({d.strip() for d in (cfg.get("extra_domains") or [])
                                 if d and d.strip()}),
        "allow_ollama": bool(cfg.get("allow_ollama", True)),
    }
    EGRESS_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    EGRESS_CONFIG_PATH.write_text(json.dumps(clean, indent=1), encoding="utf-8")
    return clean


def config_domains(cfg: dict) -> list[str]:
    """The full restricted-mode domain allowlist implied by a config (order-stable, de-duped)."""
    domains: list[str] = []
    for p in cfg.get("providers", []):
        domains += PROVIDER_DOMAINS.get(p, [])
    domains += VULN_DOMAINS
    domains += cfg.get("extra_domains", [])
    return list(dict.fromkeys(domains))


def default_policy(web: bool = False, config: dict | None = None) -> EgressPolicy:
    """Build the standard policy from the persisted (or given) config: allowlist the configured
    model providers + vuln-resolution hosts + operator extras (+ host Ollama), or an open policy
    when `web` is set."""
    if web:
        return EgressPolicy(restricted=False)
    cfg = config or load_config()
    hosts = [OLLAMA_HOSTPORT] if cfg.get("allow_ollama", True) else []
    return EgressPolicy(restricted=True, domains=config_domains(cfg), hosts=hosts)
