# Ansible WireGuard

This repository manages `wireguard-DEV1-S` as the central WireGuard hub for the
`Cascadya Scale` target architecture.

Current deployed state reference:

- See `CURRENT_STATE_PRD.md` for the validated runtime state as of `2026-04-10`

## Target architecture

- `wg0` serves admins and human operators on `10.8.0.0/16`
- `wg1` serves Teltonika edge routers on `10.9.0.0/16`
- `ens5` connects the hub to the private cloud VPC `10.42.0.0/16`
- `ens2` remains the public uplink for WireGuard endpoints and optional admin
  Internet breakout
- traffic between `wg0`, `wg1`, and `10.42.0.0/16` is routed
- NAT is only used when explicitly configured, for example admin Internet
  breakout via `ens2`

The role is data-driven:

- multiple WireGuard interfaces are declared in `wireguard_interfaces`
- forwarding rules are declared in `wireguard_forward_rules`
- NAT rules are declared in `wireguard_nat_rules`
- interface peers are added by inventory variables, not by manual edits on the VM

## Internal DNS on the hub

This repository now also manages the hub-side `dnsmasq` configuration on
`wireguard-DEV1-S`.

- `dnsmasq` listens on `wg0` at `10.8.0.1`
- public DNS forwarding uses `1.1.1.1` and `1.0.0.1`
- private `*.cascadya.internal` records are declared in
  `inventory/group_vars/wireguard.yml`
- this removes drift from manual edits on `/etc/dnsmasq.d/cascadya-internal.conf`

Current managed internal records:

- `control-panel.cascadya.internal -> 10.42.1.2`
- `auth.cascadya.internal -> 10.42.2.4`
- `wazuh.cascadya.internal -> 10.42.1.7`
- `grafana.cascadya.internal -> 10.42.1.4`
- `infracontrol.cascadya.internal -> 10.42.1.4`
- `portal.cascadya.internal -> 10.42.1.2`
- `features.cascadya.internal -> 10.42.1.2`
- `mosquitto.cascadya.internal -> 10.42.1.6`

## Wazuh private flow

This repository manages the hub side only.

For private Wazuh transport to work end-to-end, the site router must also send
`10.42.1.7/32` or `10.42.0.0/16` through the tunnel, and the private cloud must
return site traffic through `10.42.1.5`, or use an explicit SNAT fallback on
the hub.

The preferred model is routed return, not NAT:

```bash
sudo ip route add 192.168.10.0/24 via 10.42.1.5
sudo ip route add 10.8.0.0/16 via 10.42.1.5
sudo ip route add 10.9.0.0/16 via 10.42.1.5
```

## Important scaling note

Do not advertise the same LAN prefix from many peers.

At scale, `192.168.50.0/24` cannot be globally routed from hundreds of sites if
it is duplicated everywhere. Keep that OT subnet hidden behind the site IPC, or
translate it into a unique per-site prefix before advertising it to the hub.

## Runtime secrets

Each WireGuard interface reads its private key from an environment variable on
the Ansible control machine.

Linux/macOS example:

```bash
export WIREGUARD_WG0_PRIVATE_KEY='replace-me'
export WIREGUARD_WG1_PRIVATE_KEY='replace-me'
ansible-playbook playbooks/wireguard.yml
```

PowerShell example:

```powershell
$env:WIREGUARD_WG0_PRIVATE_KEY = "replace-me"
$env:WIREGUARD_WG1_PRIVATE_KEY = "replace-me"
ansible-playbook playbooks/wireguard.yml
```

For a staged migration window where the Teltonika or Wazuh side is not switched
yet, you can temporarily skip the verification phase:

```bash
ansible-playbook playbooks/wireguard.yml -e wireguard_run_verify=false
```

## Notes

- Firewall persistence is managed by a dedicated systemd service, not by a
  static `iptables-save` snapshot.
- This avoids replaying brittle legacy rules and plays better with Docker-owned
  chains on the VM.
- The repo contains migration cleanup rules for the current single-interface
  runtime observed on `2026-04-10`.
- Site-side Teltonika provisioning via UCI or golden backup is out of scope for
  this repository and should live in a companion automation role.
