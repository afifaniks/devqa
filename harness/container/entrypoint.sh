#!/usr/bin/env bash
# SecDevQA container entrypoint — installs the egress allowlist, then execs the agent.
#
# Egress control is DNS-driven and application-transparent (no dependency on the agent honoring
# proxy env vars): dnsmasq resolves ONLY allowlisted domains and adds each resolved IP to an
# ipset as it answers; iptables drops all outbound traffic except to that ipset (plus loopback,
# the DNS upstream, and any explicit host:port allowances). Because the resolver populates the
# firewall set at resolve time, CDN/round-robin IP churn is handled automatically.
#
# Environment (set by the container runner):
#   SECDEVQA_EGRESS         restricted (default) | open
#   SECDEVQA_ALLOW_DOMAINS  comma-separated domains to permit (matches subdomains too)
#   SECDEVQA_ALLOW_HOSTS    comma-separated ip:port literals to permit directly (e.g. host Ollama)
#   SECDEVQA_DNS_UPSTREAM   upstream resolver for allowlisted domains (default 8.8.8.8)
#
# In `open` mode the firewall is not installed and the container keeps full default egress
# (used only for the +web condition, which intentionally breaks the time-cap).
#
# Requires: run with --cap-add=NET_ADMIN,NET_RAW (for iptables/ipset) and, for host access,
# --net slirp4netns:allow_host_loopback=true (host reachable at 10.0.2.2).
set -euo pipefail

log() { echo "[entrypoint] $*" >&2; }

setup_restricted_egress() {
    local upstream="${SECDEVQA_DNS_UPSTREAM:-8.8.8.8}"
    local domains="${SECDEVQA_ALLOW_DOMAINS:-}"
    local hosts="${SECDEVQA_ALLOW_HOSTS:-}"

    log "restricted egress: domains=[${domains}] hosts=[${hosts}] upstream=${upstream}"

    # 1. ipset the firewall consults; dnsmasq fills it as it resolves allowlisted names.
    ipset create allowed hash:ip -exist

    # 2. dnsmasq: forward ONLY allowlisted domains to the upstream, and mirror answers into the
    #    ipset. Any other name has no server and no default upstream -> refused (blocked).
    {
        echo "no-resolv"
        echo "no-hosts"
        echo "listen-address=127.0.0.1"
        echo "bind-interfaces"
        local IFS=,
        for d in $domains; do
            [ -n "$d" ] || continue
            echo "server=/${d}/${upstream}"
            echo "ipset=/${d}/allowed"
        done
    } > /etc/dnsmasq-egress.conf
    dnsmasq --conf-file=/etc/dnsmasq-egress.conf
    echo "nameserver 127.0.0.1" > /etc/resolv.conf

    # 3. iptables: default-drop egress, permit loopback, DNS to the upstream, established flows,
    #    the resolved-IP ipset, and any explicit ip:port host allowances.
    iptables -P OUTPUT DROP
    iptables -A OUTPUT -o lo -j ACCEPT
    iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
    iptables -A OUTPUT -p udp -d "${upstream}" --dport 53 -j ACCEPT
    iptables -A OUTPUT -p tcp -d "${upstream}" --dport 53 -j ACCEPT
    iptables -A OUTPUT -m set --match-set allowed dst -j ACCEPT
    local IFS=,
    for hp in $hosts; do
        [ -n "$hp" ] || continue
        iptables -A OUTPUT -p tcp -d "${hp%%:*}" --dport "${hp##*:}" -j ACCEPT
    done
    log "egress allowlist installed"
}

case "${SECDEVQA_EGRESS:-restricted}" in
    open)        log "OPEN egress (+web): no firewall, full internet" ;;
    restricted)  setup_restricted_egress ;;
    *)           log "unknown SECDEVQA_EGRESS='${SECDEVQA_EGRESS}', defaulting to restricted"
                 setup_restricted_egress ;;
esac

log "exec: $1 ($# args)"
exec "$@"
