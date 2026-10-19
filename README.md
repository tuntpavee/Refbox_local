# ILC Refbox in Docker (no VirtualBox)

The ILC Referee Box (Server + Bridge) for the Industrial Logistics Challenge, as Docker containers on **one machine**, with one script: `./refbox.sh start`.

The lab ships the refbox as two VirtualBox VMs (`ILC-Refbox-Server`, `ILC-Refbox-Bridge`). They are **x86_64 Ubuntu** images and cannot boot on an Apple Silicon Mac (VirtualBox for Apple Silicon runs ARM guests only). Inside, both VMs are just Docker Compose stacks, so this repo runs the same stacks directly:
- same compose files, configs and scripts, copied out of the VM disks (Oct 2026)
- the **exact images** the VMs had (pinned by digest, tagged locally as `:ilc`)
- x86-only images (refbox, frontend, mqtt-bridge) run through Rosetta on Apple Silicon

## Set up on a new machine
| Machine | Needs | Status |
|---|---|---|
| macOS (Apple Silicon or Intel) | [OrbStack](https://orbstack.dev) (`brew install --cask orbstack`) | tested (M4, macOS 26.5, OrbStack, 2026-10-17/19) |
| Linux (Ubuntu 22.04/24.04, x86_64 or arm64) | Docker Engine + compose plugin, your user in the `docker` group | script path tested in a container; full stack not yet run on Linux |
| Windows | not supported (the refbox needs `network_mode: host`) | use WSL2 Ubuntu or a Linux PC |

```bash
git clone https://github.com/tuntpavee/Refbox_local.git
cd Refbox_local
./refbox.sh start        # first run pulls and builds ~3.5 GB of images (several minutes), later starts ~1 min
```
Then open **http://localhost:8080**, press `Ctrl+Alt+O`, click **Connect** under *Referee a game*.

- On a Mac with OrbStack installed, the script uses it automatically (`DOCKER_CONTEXT=orbstack`) without changing your default Docker context. To use another engine: `DOCKER_CONTEXT=<name> ./refbox.sh start`.
- Ports 8080, 1883, 4444–4447, 4500–4501 and 27017 must be free (see *Ports* below).
- The robot connects to this machine's LAN IP on port **1883**; `start` prints it as `Robot broker: <ip>:1883`. For the robot's IP see *Connecting the robot*.
- The game database (`server/rcll-get-started/compose_files/data/`) and logs are not in git; `start` creates them empty.

Verified end to end on 2026-10-17 (M4, macOS 26.5, OrbStack):
- refbox runs `thopen/nav_hard` with the lab's `raikmitl_comm.yaml`; teams TEAM_CYAN / TEAM_MAGENTA are set
- public beacons go refbox → `udp_forwarder` → both bridges → MQTT
- a simulated CYAN robot (`robot_pub.py`) **received its private navigation routes**, game state, phase and team color
- its pose beacons **reached the refbox** (BeaconSignal from TEAM_CYAN/R2 recorded in MongoDB; the frontend shows the robot ACTIVE)
- exploration machine reports are scored (zone + rotation), after the `mqtt_forward.py` fix (change 7)
- the referee frontend connects at `ws://localhost:1234`

## Use
```bash
./refbox.sh start                  # everything (Server + Bridge), ~1 min
./refbox.sh status
./refbox.sh challenge nav_easy     # nav_easy|nav_medium|nav_hard|exploration_easy|..._hard|production, then restart
./refbox.sh restart
./refbox.sh logs refbox            # or udp_forwarder, cyan_bridge, magenta_bridge, refbridge, mongodb
./refbox.sh instruct -p SETUP -s RUNNING   # rcll-refbox-instruct inside the refbox container
./refbox.sh stop
```
Frontend (guide section 4): open **http://localhost:8080** → `Ctrl+Alt+O` → **Connect** (Referee a game, `ws://localhost:1234`).
Per the rulebook, set `/llsfrb/globals/setup-time = 120` and `/llsfrb/globals/production-time = 600` in CONFIG before **Start Game**.
From another device on the LAN: `http://<this-machine-ip>:8080` (printed by `start`).

## How it maps to the guide (REFBOX_SETUP.md)
| Guide step (two VMs) | Here (one machine) |
|---|---|
| Server `raikmitl_comm.yaml`: public-peer = Server IP, cyan/magenta = Bridge IP | all `127.0.0.1` (everything is on this host) |
| Server `local_setup.sh` challenge lines | same file, or `./refbox.sh challenge <name>` |
| Server `udp_forwarder.py` DESTINATIONS = Bridge IP | `127.0.0.1:4500/4501` |
| `source setup.sh; rc_start` / `rc_stop` | `./refbox.sh start` / `stop` (also sets team names like `rc_start` did) |
| Server `cd ~/rcll-relay-server; docker compose up` | included in `./refbox.sh start` |
| Bridge `.env` RC_MQTT_REFBOX = Server IP | `172.30.0.1` (gateway of the bridge's Docker network = where the host-network refbox listens) |
| Bridge `mqtt_forward.py` TEAM_MAPPING CYAN = robot IP | **still to do when the robot is here** (see below) |
| Bridge `cd ~/thopen-refbox-bridge; docker compose up` | included in `./refbox.sh start` |

Every changed file has a `.orig` copy of the VM version next to it (`find . -name '*.orig'`). Changes, all because two machines became one:
1. `server/rcll-get-started/config/refbox/comm/raikmitl_comm.yaml`: peer hosts → 127.0.0.1
2. `server/rcll-relay-server/udp_forwarder.py`: destinations → 127.0.0.1
3. `server/rcll-get-started/local_setup.sh`: `RC_MQTT_START=false` (the server-side MQTT bridge needs a broker the Server VM never had; on one host it would grab the robot broker on :1883). Images pinned to `:ilc`.
4. `server/rcll-get-started/setup.sh`: quoted 3 paths (it broke on folder names with spaces)
5. `bridge/thopen-refbox-bridge/.env`: `RC_MQTT_REFBOX=172.30.0.1`, `MQTT_BRIDGE_TAG=ilc`
6. `bridge/thopen-refbox-bridge/docker-compose.yaml`: removed host UDP 4446/4447 mappings (the refbox itself receives on those ports; the bridges only send there), fixed subnet 172.30.0.0/24, mosquitto pinned to `:ilc`
7. `bridge/thopen-refbox-bridge/refbridge/mqtt_forward.py` (**functional fix, not single-host**, 2026-10-17): also forwards `<robot-ip>/machine_report` → `TEAM_CYAN/report` (or `TEAM_MAGENTA/report`). The VM version only forwarded poses, so Exploration reports from `ired_refbox` never reached the refbox. The topic and payload `{machine, x, y, yaw}` come from the rcll-mqtt-bridge 0.7 jar (`RefboxTeamHandler.reportMachineTopic`, `ReportMachineData`).

`refbox.sh` starts the relay and bridge with a **clean environment**. Otherwise the server's `setup.sh` exports (`RC_MQTT_REFBOX=localhost`, `MQTT_BRIDGE_TAG=master`) override the bridge `.env`, which silently breaks robot→refbox traffic.

## Ports
| Port | What |
|---|---|
| 8080/tcp | refbox frontend |
| 1234/tcp | refbox websocket (frontend connects here) |
| 4444/tcp | refbox controller port (`rcll-refbox-instruct`) |
| 4444/udp | udp_forwarder (refbox public peer sends here) |
| 4445-4447/udp | refbox receive (public / cyan / magenta) |
| 4500, 4501/udp | magenta / cyan bridge public input (from forwarder) |
| 4441, 4442/udp | cyan / magenta bridge private input (from refbox) |
| **1883/tcp** | **refbridge broker: the robot connects here** |
| 11883, 21883/tcp | magenta / cyan team brokers |
| 27017/tcp | MongoDB (game reports) |

## Connecting the robot (README-3 `ired_refbox`)
1. This machine and the robot on the same network. Note this machine's IP (printed by `./refbox.sh start`) and robot IP (`hostname -I` on the Pi).
2. `bridge/thopen-refbox-bridge/refbridge/mqtt_forward.py`: set `TEAM_MAPPING["CYAN"]` to the robot IP. **Also** `REFBRIDGE_TOPIC_PREFIX = "172.16.0."` must match the start of the robot IP (e.g. `"192.168.0."`), or pose messages are ignored. Then `./refbox.sh restart`.
3. On the robot (`~/ros_environment.bash`): `export REFBOX_BRIDGE_ADDRESS=<mac-ip>`, `export ROBOT_IP=<robot-ip>`; install `refbox_msgs` + `ired_refbox` (README-3), `ros2 run ired_refbox mqtt_refbox`.
4. Test without ROS first: on the robot, edit a copy of `robot_pub.py` with `BROKER_ADDRESS=<mac-ip>`, `ROBOT_IP=<robot-ip>`.
5. `ired_refbox` publishes the pose from `/amcl_pose` (Nav2 AMCL). Our odometry stack uses slam_toolbox; in localization mode it publishes `/pose`, not `/amcl_pose`. Either run Nav2 AMCL or remap.

## Robot interface: what the refbox actually does (tested 2026-10-17)
Tested by publishing exactly what `ired_refbox` (gitlab jazzy, 2026-09-14) publishes, on the robot broker as robot `172.16.0.211`:

| Topic (robot → broker :1883) | Payload | Refbox behaviour |
|---|---|---|
| `<ip>/pose` (1 Hz) | `{"x", "y", "yaw"}`: **x, y in field metres** (from `/amcl_pose`), yaw in degrees = `(270 − ros_yaw°) mod 360` | **Navigation:** a route zone counts after ~5 s of beacons inside it ("Visited zone C_Z21 of route 1 team CYAN"). **Any order** is accepted. Red zone C_Z32 is **not** checked by software (referees). |
| `<ip>/machine_report` | `{"machine": "C-BS", "x", "y", "yaw"}`: x, y in field metres (any point in the zone), yaw in degrees snapped to 45° | **Exploration:** zone and rotation judged separately ("Correct partial report: C-BS (zone C_Z14)", "Wrong partial report: C-CS1 (rotation 90) … should be 225"). Needs change 7 above. |

| Topic (broker → robot) | Content |
|---|---|
| `<ip>/game_state`, `<ip>/phase`, `<ip>/teamColor` | plain strings |
| `<ip>/private/navigation_routes` | `{"routes":[{"id", "route":[12 zones], "remaining":[…]}]}`; `remaining` shrinks as zones are confirmed |
| `<ip>/private/machine_info` | own machines; zone + rotation only in nav challenges (`send-mps-ground-truth: [PRODUCTION]`), hidden in exploration |

- `ired_refbox` turns `C_Z52` into `position.x = 5, y = 2` (**zone indices**). Zone C_Zxy centre = `(x − 0.5, y − 0.5)` m, as in the lab's `challenge_navigation_ex.py`.
- Point values in this 2025 refbox differ from the PDF: exploration gives +1 zone / +1 rotation / −1 wrong rotation (PDF: +3.5 / +2 / −2), and navigation points are not added live. Treat the local refbox as a test of the *logic*, not the score.
- Ground truth for checking reports: `grep -E "\(zone C_Z[0-9]+\) \(rotation" server/rcll-get-started/logs/refbox/refbox-debug_latest.log | tail`.
- Simulate the robot without ROS: `DOCKER_CONTEXT=orbstack docker exec refbridge_broker mosquitto_pub -t '172.16.0.211/pose' -m '{"x": 1.5, "y": 0.5, "yaw": 0}'` (repeat at 1 Hz for 6 s).

## Notes
- `./refbox.sh challenge` fixed 2026-10-17: it glued its block onto the last line of `local_setup.sh` when that file had no trailing newline, which broke `start`.
- The game state lives in MongoDB under `server/rcll-get-started/compose_files/data/` (game reports). Delete that folder for a completely fresh database.
- Logs: `server/rcll-get-started/logs/refbox/`.
- `refbridge` output is buffered (Python without `-u`), so its log stays mostly empty. Watch MQTT instead: `DOCKER_CONTEXT=orbstack docker exec refbridge_broker mosquitto_sub -t '#' -v`.
- The lab's bridge compose has `TEAM="TEAM_CYAN"` with literal quotes. Tested: harmless, the refbox receives beacons with team name `TEAM_CYAN`.
- At the competition the organizers run the refbox. What matters there is the bridge IP they give you (`REFBOX_BRIDGE_ADDRESS`) and the robot IP they register in `TEAM_MAPPING`.
