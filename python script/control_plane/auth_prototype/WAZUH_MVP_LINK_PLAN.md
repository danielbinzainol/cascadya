# Wazuh MVP Link Plan

## 1. Objective

This document defines the first MVP for the link between a provisioned Cascadya
IPC and the Wazuh Manager VM `wazuh-Dev1-S`.

The goal is not to build the final security observability model immediately.
The goal is to move from:

- `wazuh-agent is installed and connected`

to:

- `useful IPC and runtime events are visible and filterable in the Wazuh dashboard`

with a configuration simple enough to ship now and refine later.

## 2. Current state

Validated on `2026-04-07`:

- the provisioning workflow completes in `real/auto`;
- the first reference IPC is `cascadya-ipc-10-109`;
- the Wazuh manager is reachable on `51.15.48.174:1514`;
- the Wazuh enrollment endpoint is reachable on `51.15.48.174:1515`;
- the agent is `active/enabled`;
- an established TCP session is observed between the IPC and the Wazuh manager.

This first validation used the Wazuh public IP path. It is valid as a lab proof
point, but it is not the durable target if the site egress IP can rotate after
router reboot or WAN reconnect.

What is missing today is the product layer that makes IPC runtime events visible
and useful in the dashboard.

## 3. Recommended MVP choice

### 3.1 Chosen path

Recommended MVP:

1. Keep agent installation and enrollment on the IPC in the current provisioning workflow.
2. Assign enrolled IPCs to a dedicated Wazuh group such as `cascadya-ipc-dev1`.
3. Push log collection and labels from the Wazuh manager through centralized
   configuration using `agent.conf`.
4. Start with filtered `journald` collection for a very small number of
   Cascadya-relevant systemd units.
5. Add a first local ruleset on the manager that turns only important events
   into alerts.

This gives us:

- a low-risk first implementation;
- no need to rebuild the whole IPC image;
- no need to rework the Wazuh agent role deeply for the first iteration;
- a clean place to refine the behavior later on the manager side.

### 3.2 Why this path is the best MVP

It fits the current repo and current product state:

- the control plane already supports `wazuh_agent_group`;
- the agent is already deployed from provisioning;
- `agent.conf` lets us refine collection later without redeploying every IPC;
- Wazuh officially supports centralized configuration for `localfile`, `labels`,
  `syscollector`, `sca`, `command`, and more.

### 3.3 Durable transport recommendation

The recommended durable transport is:

- keep the Wazuh agent payload and manager-side logic from this MVP;
- stop depending on a rotating public site egress IP for `1514/TCP` and `1515/TCP`;
- point `wazuh_agent_manager_address` and
  `wazuh_agent_registration_server` to the Wazuh private IP or internal FQDN;
- carry that traffic through the site WireGuard tunnel already used to reach the IPC.

For the current Teltonika layout, this implies:

- the peer to `VM_Cloud` must advertise a route to the Wazuh private target;
- the narrowest acceptable form is the `/32` of the Wazuh private IP;
- if the Cloud gateway intentionally exposes the whole private network through
  WireGuard, `10.42.0.0/16` can be used instead.

This removes the operational dependency on the site's current public NAT IP.

## 4. Repo-specific decision

The current control plane code already exposes a Wazuh group setting:

- `AUTH_PROTO_PROVISIONING_WAZUH_AGENT_GROUP_DEFAULT`
- `wazuh_agent_group`

Relevant code paths:

- [config.py](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/config.py)
- [fleet.py](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/app/fleet.py)
- [defaults/main.yml](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/provisioning_ansible/roles/wazuh-agent/defaults/main.yml)
- [tasks/main.yml](/c:/Users/Daniel%20BIN%20ZAINOL/Desktop/GIT%20-%20Daniel/python%20script/control_plane/auth_prototype/provisioning_ansible/roles/wazuh-agent/tasks/main.yml)

Recommended default value for now:

```env
AUTH_PROTO_PROVISIONING_WAZUH_AGENT_GROUP_DEFAULT=cascadya-ipc-dev1
```

This group must exist on the Wazuh manager before enrollment if we want the
agent to receive a dedicated shared configuration immediately.

## 5. What we want to send from the IPC to the manager

### 5.1 MVP scope now

For the first MVP, collect and classify only these sources:

- `wazuh-agent.service`
- `wg-quick@wg0.service`
- `cascadya-unlock-data.service`
- `cascadya-network-persist.service`
- `gateway_modbus.service`
- `telemetry_publisher.service`

Why these sources:

- they correspond directly to the provisioning workflow we already validate;
- they map to the real production path of the IPC;
- they are visible through `journald`;
- they are enough to understand whether a failure comes from security,
  transport, boot-unlock, or edge runtime.

### 5.2 What to defer for later

Do not try to ship all of this in the first MVP:

- raw telemetry as one alert per measurement;
- broad log ingestion for every system service on the IPC;
- high-volume file monitoring;
- command checks every few seconds;
- full security correlation across multiple IPCs;
- a polished dashboard information architecture.

## 6. Options we have

### Option A. Centralized config through `agent.conf` on the manager

What it is:

- configure Wazuh collection centrally on `wazuh-Dev1-S`;
- target all IPC agents in one group;
- push `localfile`, `labels`, `syscollector`, and later `command` checks.

Pros:

- best fit for iterative tuning;
- no IPC redeploy needed for every rule change;
- official Wazuh path;
- ideal for `Dev1`.

Cons:

- requires first access discipline on the manager VM;
- depends on group hygiene.

Recommendation:

- use this as the default MVP path.

### Option B. Local `ossec.conf` management from provisioning on each IPC

What it is:

- extend the existing Ansible role so the control plane writes more Wazuh agent
  config locally on each IPC.

Pros:

- fully deterministic from provisioning;
- stored in our own repo and deployment path.

Cons:

- every tuning requires replaying provisioning or another agent-specific play;
- less flexible than manager-side central config;
- heavier for fast iteration.

Recommendation:

- keep this as a second step if we want stronger infra-as-code later.

### Option C. Syslog forwarding directly to the manager

What it is:

- send logs to the manager as syslog instead of using the Wazuh agent logcollector.

Pros:

- useful for non-agent devices;
- standard pattern.

Cons:

- unnecessary for this IPC because we already run a Wazuh agent;
- loses the advantage of agent-level labels and inventory;
- adds another transport path for no strong MVP gain.

Recommendation:

- do not use for the first IPC MVP.

### Option D. Command monitoring

What it is:

- run commands on the IPC through Wazuh agent modules and analyze their output.

Good use cases:

- `systemctl is-active gateway_modbus.service`
- `systemctl is-active telemetry_publisher.service`
- `systemctl is-active wg-quick@wg0.service`
- `findmnt /data`

Pros:

- good for state snapshots when logs are not enough.

Cons:

- more invasive;
- must be rate-limited;
- can create noise quickly if overused.

Recommendation:

- keep for phase 2, not MVP phase 1.

### Option E. File integrity monitoring

What it is:

- monitor specific files or directories for change events.

Good later targets:

- `/etc/cascadya/unlock/`
- `/var/lib/cascadya/unlock/last-validate.json`
- `/data/cascadya/agent/certs/`

Pros:

- very useful for detecting drift or broken bundles.

Cons:

- not the fastest path to a visible dashboard MVP;
- easy to over-collect.

Recommendation:

- add later once the first runtime alert flow is proven.

## 7. Specific MVP choices

### 7.1 Grouping

Use:

- Wazuh group: `cascadya-ipc-dev1`

Rationale:

- environment-specific and future-proof;
- can later coexist with `cascadya-ipc-prod1`, `cascadya-ipc-lab`, etc.

### 7.2 Labels

Add labels so every alert is filterable even before custom dashboards mature.

Recommended labels for IPC agents:

- `cascadya.role=ipc`
- `cascadya.env=dev1`
- `cascadya.site=dev1`
- `cascadya.stack=remote-unlock-wireguard-edge`

Recommended per-agent labels:

- `cascadya.asset=cascadya-ipc-10-109`
- `cascadya.uplink_ip=192.168.10.109`
- `cascadya.process_ip=192.168.50.1`

The static labels can live in the group config. Asset-specific labels can be
added later through a more targeted config if needed.

### 7.3 First log sources

Collect via `journald` with filters:

- `_SYSTEMD_UNIT = wazuh-agent.service`
- `_SYSTEMD_UNIT = wg-quick@wg0.service`
- `_SYSTEMD_UNIT = cascadya-unlock-data.service`
- `_SYSTEMD_UNIT = cascadya-network-persist.service`
- `_SYSTEMD_UNIT = gateway_modbus.service`
- `_SYSTEMD_UNIT = telemetry_publisher.service`

Use `PRIORITY` filtering to reduce noise where appropriate:

- `wazuh-agent.service`: `[0-6]`
- `wg-quick@wg0.service`: `[0-6]`
- `cascadya-network-persist.service`: `[0-6]`
- `gateway_modbus.service`: all lines or `[0-6]` depending on desired visibility
- `telemetry_publisher.service`: errors only at first, not every pressure value

### 7.4 Alerting posture

For MVP, create alerts for:

- service failures;
- crashes;
- repeated reconnects;
- clear error strings;
- transport errors;
- remote-unlock errors.

Do not create alerts for every normal heartbeat or every telemetry sample.

## 8. Proposed `agent.conf` for the manager

Suggested file on `wazuh-Dev1-S`:

- `/var/ossec/etc/shared/cascadya-ipc-dev1/agent.conf`

Example:

```xml
<agent_config name="^cascadya-ipc-.*">
  <labels>
    <label key="cascadya.role">ipc</label>
    <label key="cascadya.env">dev1</label>
    <label key="cascadya.site">dev1</label>
    <label key="cascadya.stack">remote-unlock-wireguard-edge</label>
  </labels>

  <localfile>
    <location>journald</location>
    <log_format>journald</log_format>
    <filter field="_SYSTEMD_UNIT">^wazuh-agent\.service$</filter>
    <filter field="PRIORITY">[0-6]</filter>
  </localfile>

  <localfile>
    <location>journald</location>
    <log_format>journald</log_format>
    <filter field="_SYSTEMD_UNIT">^wg-quick@wg0\.service$</filter>
    <filter field="PRIORITY">[0-6]</filter>
  </localfile>

  <localfile>
    <location>journald</location>
    <log_format>journald</log_format>
    <filter field="_SYSTEMD_UNIT">^cascadya-unlock-data\.service$</filter>
  </localfile>

  <localfile>
    <location>journald</location>
    <log_format>journald</log_format>
    <filter field="_SYSTEMD_UNIT">^cascadya-network-persist\.service$</filter>
    <filter field="PRIORITY">[0-6]</filter>
  </localfile>

  <localfile>
    <location>journald</location>
    <log_format>journald</log_format>
    <filter field="_SYSTEMD_UNIT">^gateway_modbus\.service$</filter>
  </localfile>

  <localfile>
    <location>journald</location>
    <log_format>journald</log_format>
    <filter field="_SYSTEMD_UNIT">^telemetry_publisher\.service$</filter>
    <filter field="PRIORITY">[0-4]</filter>
  </localfile>
</agent_config>
```

Notes:

- this is intentionally narrow;
- `telemetry_publisher` is restricted first because it can be noisy;
- we can widen it later if we want a timeline of business runtime events.

## 9. Proposed manager-side rules

Suggested file:

- `/var/ossec/etc/rules/local_rules.xml`

Rule ID range:

- use `100000-120000` for custom rules.

### 9.1 Remote unlock

```xml
<group name="cascadya,remote_unlock,">
  <rule id="100500" level="3">
    <match>\[remote-unlock\]</match>
    <description>Cascadya remote-unlock log observed.</description>
    <group>cascadya,remote_unlock,</group>
  </rule>

  <rule id="100501" level="10">
    <if_sid>100500</if_sid>
    <match>Missing environment file|does not include a hostname|fail|error|timeout</match>
    <description>Cascadya remote-unlock error on $(hostname).</description>
    <group>cascadya,remote_unlock,error,</group>
  </rule>
 </group>
```

### 9.2 WireGuard

```xml
<group name="cascadya,wireguard,">
  <rule id="100510" level="5">
    <match>wg-quick@wg0</match>
    <description>Cascadya WireGuard event on $(hostname).</description>
    <group>cascadya,wireguard,</group>
  </rule>

  <rule id="100511" level="10">
    <if_sid>100510</if_sid>
    <match>Failed|failure|Cannot|error</match>
    <description>Cascadya WireGuard failure on $(hostname).</description>
    <group>cascadya,wireguard,error,</group>
  </rule>
</group>
```

### 9.3 Gateway

```xml
<group name="cascadya,gateway_modbus,">
  <rule id="100520" level="3">
    <match>\[GATEWAY\]</match>
    <description>Cascadya gateway_modbus runtime event.</description>
    <group>cascadya,gateway_modbus,</group>
  </rule>

  <rule id="100521" level="12">
    <if_sid>100520</if_sid>
    <match>Traceback|Exception|ERROR|Failed|timeout|refused</match>
    <description>Cascadya gateway_modbus error.</description>
    <group>cascadya,gateway_modbus,error,</group>
  </rule>

  <rule id="100522" level="4">
    <if_sid>100520</if_sid>
    <match>SteamSwitch gateway is running</match>
    <description>Cascadya gateway_modbus started successfully.</description>
    <group>cascadya,gateway_modbus,lifecycle,</group>
  </rule>
</group>
```

### 9.4 Telemetry publisher

```xml
<group name="cascadya,telemetry_publisher,">
  <rule id="100530" level="3">
    <match>\[TELEMETRY\]</match>
    <description>Cascadya telemetry_publisher runtime event.</description>
    <group>cascadya,telemetry_publisher,</group>
  </rule>

  <rule id="100531" level="10">
    <if_sid>100530</if_sid>
    <match>Traceback|Exception|ERROR|Failed|timeout|refused</match>
    <description>Cascadya telemetry_publisher error.</description>
    <group>cascadya,telemetry_publisher,error,</group>
  </rule>
</group>
```

This keeps normal pressure logs out of the high-signal alert stream.

## 10. Suggested manager-side validation

On `wazuh-Dev1-S`, validate in this order:

1. Create the group `cascadya-ipc-dev1`.
2. Put `agent.conf` in `/var/ossec/etc/shared/cascadya-ipc-dev1/`.
3. Validate it with:

```bash
sudo /var/ossec/bin/verify-agent-conf -f /var/ossec/etc/shared/cascadya-ipc-dev1/agent.conf
```

4. Restart the manager to accelerate distribution:

```bash
sudo systemctl restart wazuh-manager
```

5. Confirm the agent is synced with the group config.
6. Add custom rules in `/var/ossec/etc/rules/local_rules.xml`.
7. Restart the manager again.
8. Trigger a few known events on the IPC and observe them in the dashboard.

## 11. What to test from the IPC

Good first tests:

- restart `gateway_modbus.service`;
- restart `telemetry_publisher.service`;
- restart `wg-quick@wg0.service`;
- run a remote-unlock manual helper path that emits a known log line;
- create one intentional failure on a non-critical path and verify the alert.

We want to prove:

- the log reaches the manager;
- a custom rule classifies it;
- the dashboard can filter by agent and component;
- the signal is understandable by an operator.

## 12. First dashboard views to aim for

The dashboard does not need to be perfect in the MVP.

Useful first saved searches or dashboard panels:

- `IPC Health`
  - filter on `agent.name: cascadya-ipc-*`
- `Remote Unlock / WireGuard`
  - filter on `rule.groups: remote_unlock OR rule.groups: wireguard`
- `Edge Agent Runtime`
  - filter on `rule.groups: gateway_modbus OR rule.groups: telemetry_publisher`
- `Wazuh Transport`
  - filter on `agent.name: cascadya-ipc-* AND rule.groups: wazuh`

## 13. Recommended phased rollout

### Phase 1. Dashboard-visible runtime alerts

Implement now:

- Wazuh group `cascadya-ipc-dev1`
- centralized `agent.conf`
- focused `journald` collection
- first `local_rules.xml`

### Phase 2. Stronger state validation

Add later:

- command monitoring for a few critical services;
- file integrity monitoring for selected files;
- agent labels enriched per asset.

### Phase 3. Better product signal

Add later:

- manager VM health signals;
- site-aware filters and dashboards;
- lower-noise rules with severity tuning;
- more explicit business-state alerts.

## 14. Practical recommendation

If we want the fastest useful MVP, do this next:

1. create the Wazuh group `cascadya-ipc-dev1`;
2. move the Wazuh transport target from the public IP to the manager private IP
   or internal FQDN over WireGuard;
3. set `AUTH_PROTO_PROVISIONING_WAZUH_AGENT_GROUP_DEFAULT=cascadya-ipc-dev1`;
4. deploy the `agent.conf` above on `wazuh-Dev1-S`;
5. add the first custom rules;
6. replay or re-sync the agent;
7. trigger one event per component and validate it in the dashboard.

This is the shortest path to a real operator-visible IPC -> Wazuh Manager link.

## 15. Official references

- Centralized configuration:
  https://documentation.wazuh.com/current/user-manual/reference/centralized-configuration.html
- Journald log collection:
  https://documentation.wazuh.com/current/user-manual/capabilities/log-data-collection/journald.html
- Agent labels:
  https://documentation.wazuh.com/current/user-manual/agent/agent-management/labels.html
- Custom rules:
  https://documentation.wazuh.com/current/user-manual/ruleset/rules/custom.html
- Log data collection overview:
  https://documentation.wazuh.com/current/user-manual/capabilities/log-data-collection/index.html
