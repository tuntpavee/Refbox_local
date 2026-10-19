export REFBOX_COMPOSE_COMMAND="docker compose"

# Navigation Challenge
# export REFBOX_ARGS="--cfg-challenges /etc/rcll-refbox/challenges/thopen/nav_easy.yaml --cfg-comm /etc/rcll-refbox/comm/raikmitl_comm.yaml"
# export REFBOX_ARGS="--cfg-challenges /etc/rcll-refbox/challenges/thopen/nav_medium.yaml --cfg-comm /etc/rcll-refbox/comm/raikmitl_comm.yaml"
# export REFBOX_ARGS="--cfg-challenges /etc/rcll-refbox/challenges/thopen/nav_hard.yaml --cfg-comm /etc/rcll-refbox/comm/raikmitl_comm.yaml"

# Exploration Challenge
# export REFBOX_ARGS="--cfg-challenges /etc/rcll-refbox/challenges/exp/exploration_easy.yaml --cfg-comm /etc/rcll-refbox/comm/raikmitl_comm.yaml"

# Production Challenge
# export REFBOX_ARGS="--cfg-challenges /etc/rcll-refbox/challenges/thopen/production.yaml --cfg-comm /etc/rcll-refbox/comm/raikmitl_comm.yaml"

export MONGODB_TAG=4.4
export RC_MQTT_TEAM=TEAM_MAGENTA
export RC_MAGENTA=TEAM_MAGENTA
export RC_CYAN=TEAM_CYAN
# single-host (Mac/OrbStack): the server-side MQTT bridge needs a broker the Server VM never ran;
# on one host it would attach to the robot broker on :1883 by mistake. The Bridge stack does this job.
export RC_MQTT_START=false

# pinned to the exact images found in the ILC VMs (tagged locally as :ilc by refbox.sh)
export REFBOX_TAG=ilc
export REFBOX_FRONTEND_TAG=ilc

function rc_game_pre() {
    docker exec refbox rcll-refbox-instruct -p PRE_GAME -s RUNNING
}

function rc_game_production() {
    docker exec refbox rcll-refbox-instruct -p PRODUCTION -s RUNNING
}

# >>> active challenge (set by refbox.sh challenge)
export REFBOX_ARGS="--cfg-challenges /etc/rcll-refbox/challenges/thopen/nav_hard.yaml --cfg-comm /etc/rcll-refbox/comm/raikmitl_comm.yaml"
# <<< active challenge
