#!/bin/bash

set -e

DEFAULT_MAX_PARALLEL_JOBS=1
DEFAULT_NUM_RUNS=50
DEFAULT_SIZES=(247)
SCENARIO_NAME="GR"
DEFAULT_RANGES=(120)
DEFAULT_START=1
DEFAULT_MAXIMUM_NODE_DEGREES=(1 2 3 4 5 6 7 8 9 10)
DEFAULT_MODE=1

print_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  -m, --mode MODE        Cluster communication mode: 0 to allow only intra-cluster communication, 1 to also allow inter-cluster communication (default: $DEFAULT_MODE)"
    echo "  -j, --jobs NUM         Maximum number of parallel jobs (default: $DEFAULT_MAX_PARALLEL_JOBS)"
    echo "  -n, --num NUM          Number of runs per size (default: $DEFAULT_NUM_RUNS)"
    echo "  -start NUM             Run number to start from (default: $DEFAULT_START)"
    echo "  -r, --ranges RANGE...  Space-separated list of ranges (default: ${DEFAULT_RANGES[*]})"
    echo "  -s, --sizes SIZE...    Space-separated list of message sizes (default: ${DEFAULT_SIZES[*]})"
    echo "  -max-node-degrees NUM...   Space-separated list of maximum node degree (default: ${DEFAULT_MAXIMUM_NODE_DEGREES[*]})"
    echo "  -h, --help             Show this help message"
    echo ""
    echo "This script generates random stationary nodes for simulations."
    echo ""
    echo "Example:"
    echo "  $0 --name GR --jobs 32 --num 25 --sizes 100 1000 10000 --range 12 120"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        -j|--jobs)
            MAX_PARALLEL_JOBS="$2"
            shift 2
            ;;
        -m|--mode)
            MODE="$2"
            shift 2
            ;;
        -n|--num)
            NUM_RUNS="$2"
            shift 2
            ;;
        -start)
            START_RUN="$2"
            shift 2
            ;;
        -s|--sizes)
            SIZES=()
            shift
            while [[ $# -gt 0 && ! "$1" =~ ^- ]]; do
                SIZES+=("$1")
                shift
            done
            ;;
        -r|--ranges)
            RANGES=()
            shift
            while [[ $# -gt 0 && ! "$1" =~ ^- ]]; do
                RANGES+=("$1")
                shift
            done
            ;;
        -max-node-degrees)
            MAX_NODE_DEGREES=()
            shift
            while [[ $# -gt 0 && ! "$1" =~ ^- ]]; do
                MAX_NODE_DEGREES+=("$1")
                shift
            done
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            print_usage
            exit 1
            ;;
    esac
done

MAX_PARALLEL_JOBS=${MAX_PARALLEL_JOBS:-$DEFAULT_MAX_PARALLEL_JOBS}
NUM_RUNS=${NUM_RUNS:-$DEFAULT_NUM_RUNS}
if [ ${#SIZES[@]} -eq 0 ]; then
    SIZES=("${DEFAULT_SIZES[@]}")
fi
if [ ${#RANGES[@]} -eq 0 ]; then
    RANGES=("${DEFAULT_RANGES[@]}")
fi
if [ ${#MAX_NODE_DEGREES[@]} -eq 0 ]; then
    MAX_NODE_DEGREES=("${DEFAULT_MAXIMUM_NODE_DEGREES[@]}")
fi
if [ -z "$MODE" ]; then
    MODE=$DEFAULT_MODE
elif [[ "$MODE" != 0 && "$MODE" != 1 ]]; then
    echo "Invalid mode: $MODE. Allowed values are 0 (intra) or 1 (inter)."
    exit 1
fi
START_RUN=${START_RUN:-$DEFAULT_START}

echo "Configuration:"
echo "  Communication mode: $MODE"
echo "  Maximum parallel jobs: $MAX_PARALLEL_JOBS"
echo "  Number of runs: $NUM_RUNS"
echo "  Starting run number: $START_RUN"
echo "  Message sizes: [$(IFS=', '; echo "${SIZES[*]}")]"
echo "  Interface ranges: [$(IFS=', '; echo "${RANGES[*]}")]"
echo "  Scenario name: $SCENARIO_NAME"
echo "  Max node degrees: [$(IFS=', '; echo "${MAX_NODE_DEGREES[*]}")]"

compile() {
    cd the-one
    echo "Compiling the-one..."
    ./compile.sh
    echo "Compiled successfully"
    cd ..
}

run_simulation() {
    local size=$1
    local run=$2
    local range=$3
    local mode=$4
    local max_node_degree=$5
    local job_id="size${size}_run${run}_range${range}_mode${mode}_maxdeg${max_node_degree}"

    start_timestamp=$(date +%s)
    echo "[$(date '+%H:%M:%S')] Starting simulation ${job_id}"

    cd the-one
    ./one.sh -b 1  \
        "$SCENARIO_NAME-settings-size${size}-run${run}-range${range}-mode${mode}.txt" \
        "$SCENARIO_NAME-comms-settings-mode${mode}-maxdeg${max_node_degree}.txt"
    cd -
    end_timestamp=$(date +%s)
    duration=$((end_timestamp-start_timestamp))
    
    echo "[$(date '+%H:%M:%S')] Completed simulation ${job_id} in ${duration} seconds"
}

wait_for_jobs() {
    local max_jobs=$1
    while [ $(jobs -r | wc -l) -ge $max_jobs ]; do
        sleep 1
    done
}

prepare_config_files() {
    echo "Preparing configuration files..."

    # 0 for intra-cluster communication, 1 for inter-cluster communication
    for mode in 0 1; do
        for max_node_degree in "${MAX_NODE_DEGREES[@]}"; do
        sed -e "s/Events1.mode = .*/Events1.mode = $mode/" \
            -e "s/bluetoothInterface.communicationMode = .*/bluetoothInterface.communicationMode = $mode/" \
                -e "s/bluetoothInterface.maxDegree = .*/bluetoothInterface.maxDegree = $max_node_degree/" \
                the-one/$SCENARIO_NAME-comms-settings.txt > "the-one/$SCENARIO_NAME-comms-settings-mode${mode}-maxdeg${max_node_degree}.txt"
        done
        for size in "${SIZES[@]}"; do
            for run in $(seq $START_RUN $NUM_RUNS); do
                for range in "${RANGES[@]}"; do
                    RANDOM_SEED=$((size+range*1000))
                    sed -e "s/Scenario.name = .*/Scenario.name = ${SCENARIO_NAME}_size${size}_run${run}_range${range}_mode${mode}/" \
                        -e "s/MovementModel.rngSeed = .*/MovementModel.rngSeed = ${RANDOM_SEED}/" \
                        -e "s/Events1.size = .*/Events1.size = $size/" \
                        -e "s/bluetoothInterface.transmitRange = .*/bluetoothInterface.transmitRange = $range/" \
                        -e "s/Events1.binSize = .*/Events1.binSize = $((mode == 0 ? INTRA_CLUSTER_BIN_SIZE : INTER_CLUSTER_BIN_SIZE))/" \
                        the-one/$SCENARIO_NAME-settings.txt > "the-one/$SCENARIO_NAME-settings-size${size}-run${run}-range${range}-mode${mode}.txt"
                done
            done
        done
    done

    # Create WKT file and png map
    python room/main.py --name hall --x_offset 50 --y_offset 50
}

run_simulations() {
    local NUMBER_OF_SIZES=${#SIZES[@]}
    local NUMBER_OF_RANGES=${#RANGES[@]}
    local NUMBER_OF_MODES=$((MODE+1)) # mode is 0 or 1, so add 1 to get count
    local NUMBER_OF_MAX_DEGREES=${#MAX_NODE_DEGREES[@]}
    local TOTAL_SIMULATIONS=$((NUMBER_OF_SIZES * NUMBER_OF_RANGES * NUM_RUNS * NUMBER_OF_MODES * NUMBER_OF_MAX_DEGREES))

    echo "Starting parallel simulations with up to $MAX_PARALLEL_JOBS concurrent jobs..."
    echo "Total simulations to run: $TOTAL_SIMULATIONS"
    total_max_duration=$((TOTAL_SIMULATIONS * 30000 / MAX_PARALLEL_JOBS)) # assuming each simulation takes at most 30000 seconds
    echo "Estimated total duration with $MAX_PARALLEL_JOBS parallel jobs: ~${total_max_duration} seconds (~$((total_max_duration / 3600)) hours)"
    start_timestamp=$(date +%s)
    echo "Start time: $(date)"

    total_jobs=0
    for max_degree in "${MAX_NODE_DEGREES[@]}"; do
    for mode in $(seq 0 $MODE); do
        for size in "${SIZES[@]}"; do
            for range in "${RANGES[@]}"; do
                    echo "Scheduling simulations for message size: $size, communication radius: $range, mode: $mode, max node degree: $max_degree"
                for run in $(seq $START_RUN $NUM_RUNS); do
                    wait_for_jobs $MAX_PARALLEL_JOBS
                        run_simulation $size $run $range $mode $max_degree &

                    total_jobs=$((total_jobs + 1))
                        echo "Scheduled job $total_jobs/$TOTAL_SIMULATIONS: size=$size, run=$run, range=$range, mode=$mode, max_node_degree=$max_degree"

                    sleep 0.1
                done
            done
        done
    done

    echo "Waiting for all simulations to complete..."
    wait

    end_timestamp=$(date +%s)
    duration=$((end_timestamp-start_timestamp))

    echo "All simulations completed!"
    echo "Took $duration seconds" 
    
    ls -la the-one/reports_data/ | grep "$SCENARIO_NAME" | wc -l | xargs echo "Total report files:"
    echo "The resulting reports data can be found under the the-one/reports_data/ directory"
}

compile
prepare_config_files
run_simulations