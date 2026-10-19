#!/usr/bin/env bash
# ILC Refbox (Server + Bridge) on one machine, in Docker. Replaces the two VirtualBox VMs.
# Works on macOS (OrbStack preferred, used automatically when installed) and Linux (Docker Engine).
#
#   ./refbox.sh start        # server (mongodb, refbox, frontend, udp_forwarder) + bridge (brokers, mqtt bridges, refbridge)
#   ./refbox.sh stop         # stop everything
#   ./refbox.sh status       # containers + listening ports
#   ./refbox.sh logs [name]  # follow logs (refbox, udp_forwarder, cyan_bridge, magenta_bridge, refbridge, ...)
#   ./refbox.sh challenge <nav_easy|nav_medium|nav_hard|exploration_easy|exploration_medium|exploration_hard|production>
#   ./refbox.sh instruct <args>   # docker exec refbox rcll-refbox-instruct <args>, e.g. -p SETUP -s RUNNING
#
# Frontend: http://localhost:8080  (Ctrl+Alt+O → referee config → Connect)
set -euo pipefail
# Mac: use OrbStack's engine when it exists, without changing the user's default docker context.
# Set DOCKER_CONTEXT yourself to override (e.g. DOCKER_CONTEXT=desktop-linux ./refbox.sh start).
if [ -z "${DOCKER_CONTEXT:-}" ] && docker context inspect orbstack >/dev/null 2>&1; then
  export DOCKER_CONTEXT=orbstack
fi
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RGS="$HERE/server/rcll-get-started"
RELAY="$HERE/server/rcll-relay-server"
BRIDGE="$HERE/bridge/thopen-refbox-bridge"

# Exact images found in the ILC VMs' docker storage (Sep 2025), tagged locally as :ilc
pin_images() {
  local pairs=(
    "quay.io/robocup-logistics/rcll-refbox@sha256:dd414ad27b6b2266d49a630390fee3634e302578e3d42f1c1fe82fcf0d2bfb5b quay.io/robocup-logistics/rcll-refbox:ilc"
    "quay.io/robocup-logistics/rcll-refbox-frontend@sha256:a1b54b3ab07236a0c0a1ca3c69038a563a328eb179aa893ae9044227665af43d quay.io/robocup-logistics/rcll-refbox-frontend:ilc"
    "ghcr.io/robocup-logistics/rcll-mqtt-bridge@sha256:4d5cde8dad1c46957cd0a02028c6cf140d13c4c29bfaeafbe012a83ca13c1bce ghcr.io/robocup-logistics/rcll-mqtt-bridge:ilc"
    "mongo@sha256:52c42cbab240b3c5b1748582cc13ef46d521ddacae002bbbda645cebed270ec0 mongo:4.4"
    "eclipse-mosquitto@sha256:d219d3a72847f3aed6a1d66975972d3b17f86e39e8f6f6b86b4088b879c1a2d6 eclipse-mosquitto:ilc"
  )
  for p in "${pairs[@]}"; do
    set -- $p
    docker image inspect "$2" >/dev/null 2>&1 && continue
    docker image inspect "$1" >/dev/null 2>&1 || docker pull "$1"
    docker tag "$1" "$2"
  done
}

load_env() {
  # setup.sh is bash and sources local_setup.sh (challenge selection, team names)
  # shellcheck disable=SC1091
  set +u; cd "$RGS" && source ./setup.sh >/dev/null; set -u
}

compose_server() { (load_env; cd "$RGS/compose_files" && docker compose -p ilc-server -f "$1.yaml" "${@:2}"); }
# Relay and Bridge were separate VMs: start them with a clean environment so the server's
# setup.sh exports (RC_MQTT_REFBOX=localhost, MQTT_BRIDGE_TAG=master, ...) can't override their .env
compose_clean() {
  local keep=(HOME="$HOME" PATH="$PATH")
  [ -n "${DOCKER_CONTEXT:-}" ] && keep+=(DOCKER_CONTEXT="$DOCKER_CONTEXT")
  [ -n "${DOCKER_HOST:-}" ] && keep+=(DOCKER_HOST="$DOCKER_HOST")
  (cd "$1" && env -i "${keep[@]}" docker compose -p "$2" "${@:3}")
}

# LAN address other devices (robot, browser) use to reach this machine
host_ip() {
  ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null \
    || hostname -I 2>/dev/null | awk '{print $1}' || echo '<this-machine-ip>'
}

# sed -i differs between GNU (Linux) and BSD (macOS)
sed_i() { if sed --version >/dev/null 2>&1; then sed -i "$@"; else sed -i '' "$@"; fi; }

wait_refbox() {
  for _ in $(seq 60); do
    docker exec refbox true 2>/dev/null && (exec 3<>/dev/tcp/127.0.0.1/4444) 2>/dev/null && return 0
    sleep 1
  done
  echo "refbox did not come up; see ./refbox.sh logs refbox" >&2; return 1
}

start() {
  if [ "$(uname)" = Darwin ] && [ "${DOCKER_CONTEXT:-}" = orbstack ]; then open -ga OrbStack; fi
  for _ in $(seq 30); do docker info >/dev/null 2>&1 && break; sleep 2; done
  docker info >/dev/null 2>&1 || { echo "Docker is not running (or this user cannot use it)." >&2; exit 1; }
  # bind-mounted folders git does not keep; created here so Docker does not create them as root
  mkdir -p "$RGS/logs/refbox" "$RGS/compose_files/data" \
    "$BRIDGE"/{refbridge_broker,cyan,magenta}/mosquitto/{data,log}
  pin_images
  (load_env; echo "Challenge: ${REFBOX_ARGS}")
  echo "== Server: mongodb"; compose_server mongodb up -d
  echo "== Server: refbox + frontend"; compose_server refbox up -d
  wait_refbox
  # what rc_start did with RC_AUTO_SETUP: set team names
  (load_env
   if [ -n "${RC_CYAN:-}" ]; then docker exec refbox rcll-refbox-instruct -c"$RC_CYAN" >/dev/null && echo "CYAN    = $RC_CYAN"; fi
   if [ -n "${RC_MAGENTA:-}" ]; then docker exec refbox rcll-refbox-instruct -m"$RC_MAGENTA" >/dev/null && echo "MAGENTA = $RC_MAGENTA"; fi)
  echo "== Server: udp_forwarder"; compose_clean "$RELAY" ilc-relay up -d --build --quiet-pull 2>&1 | grep -vE "^ *(#|=>)" || true
  echo "== Bridge: brokers, mqtt bridges, refbridge"; compose_clean "$BRIDGE" ilc-bridge up -d --build --quiet-pull 2>&1 | grep -vE "^ *(#|=>)" || true
  echo
  echo "Frontend:     http://localhost:8080   (LAN: http://$(host_ip):8080)"
  echo "Robot broker: $(host_ip):1883  (REFBOX_BRIDGE_ADDRESS for ired_refbox)"
}

stop() {
  compose_clean "$BRIDGE" ilc-bridge down || true
  compose_clean "$RELAY" ilc-relay down || true
  compose_server refbox down || true
  compose_server mongodb down || true
}

status() {
  docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'NAMES|refbox|mongodb|forwarder|broker|bridge|refbridge' || true
}

challenge() {
  local f
  case "${1:-}" in
    nav_easy|nav_medium|nav_hard) f="thopen/$1.yaml" ;;
    exploration_easy|exploration_medium|exploration_hard) f="exp/$1.yaml" ;;
    production) f="thopen/production.yaml" ;;
    *) echo "usage: $0 challenge <nav_easy|nav_medium|nav_hard|exploration_easy|exploration_medium|exploration_hard|production>"; exit 1 ;;
  esac
  [ -f "$RGS/config/refbox/challenges/$f" ] || { echo "missing config/refbox/challenges/$f"; exit 1; }
  # comment out every REFBOX_ARGS line, then append the chosen one
  sed_i -E 's/^export REFBOX_ARGS=/# export REFBOX_ARGS=/' "$RGS/local_setup.sh"
  sed_i '/^# >>> active challenge/,/^# <<< active challenge/d' "$RGS/local_setup.sh"
  # the file may not end in a newline; without one the block glues onto the last line
  if [ -n "$(tail -c 1 "$RGS/local_setup.sh")" ]; then echo >> "$RGS/local_setup.sh"; fi
  printf '# >>> active challenge (set by refbox.sh challenge)\nexport REFBOX_ARGS="--cfg-challenges /etc/rcll-refbox/challenges/%s --cfg-comm /etc/rcll-refbox/comm/raikmitl_comm.yaml"\n# <<< active challenge\n' "$f" >> "$RGS/local_setup.sh"
  echo "Challenge set to $f. Restart the refbox to apply: ./refbox.sh stop && ./refbox.sh start"
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) status ;;
  logs) docker logs -f --tail 100 "${2:-refbox}" ;;
  challenge) challenge "${2:-}" ;;
  instruct) shift; docker exec refbox rcll-refbox-instruct "$@" ;;
  *) sed -n '2,12p' "$0"; exit 1 ;;
esac
