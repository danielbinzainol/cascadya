# Modbus Simulator

This folder mirrors the PLC / SBC simulator tooling so we can evolve it in parallel
with the control-plane, broker, and IPC adapters.

Contents:

- `src/`: simulator runtime Python modules
- `systemd/`: service unit templates for the simulator host
- `scripts/`: helper sync script for WSL-driven deployment to the simulator

Current deployment target assumptions:

- simulator host IP: `192.168.50.2`
- remote user: `cascadya`
- remote app dir: `/home/cascadya/simulator_sbc`
- systemd unit: `modbus-serveur.service`

The control panel Provisioning page exposes these same defaults as command previews.
