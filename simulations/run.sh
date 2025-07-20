#!/bin/bash

set -e

DEFAULT_MAX_PARALLEL_JOBS=1
DEFAULT_NUM_RUNS=50
DEFAULT_SIZES=(247)
SCENARIO_NAME="GR"
DEFAULT_TOTAL_HOSTS=50
DEFAULT_RANGES=(120)

print_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  -j, --jobs NUM         Maximum number of parallel jobs (default: $DEFAULT_MAX_PARALLEL_JOBS)"
    echo "  -n, --num NUM          Number of runs per size (default: $DEFAULT_NUM_RUNS)"
    echo "  -r, --ranges RANGE...  Space-separated list of ranges (default: ${DEFAULT_RANGES[*]})"
    echo "  -s, --sizes SIZE...    Space-separated list of message sizes (default: ${DEFAULT_SIZES[*]})"
    echo "  -t, --total-hosts NUM  Total number of nodes in the simulation (default: $DEFAULT_TOTAL_HOSTS)"
    echo "  -h, --help             Show this help message"
    echo ""
    echo "This script generates random stationary nodes for simulations."
    echo ""
    echo "Example:"
    echo "  $0 --name GR --jobs 32 --num 25 --sizes 100 1000 10000 --total-hosts 50 --range 12 120"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        -j|--jobs)
            MAX_PARALLEL_JOBS="$2"
            shift 2
            ;;
        -n|--num)
            NUM_RUNS="$2"
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
        -t|--total-hosts)
            TOTAL_HOSTS="$2"
            shift 2
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
TOTAL_HOSTS=${TOTAL_HOSTS:-$DEFAULT_TOTAL_HOSTS}
echo "Configuration:"
echo "  Maximum parallel jobs: $MAX_PARALLEL_JOBS"
echo "  Number of runs: $NUM_RUNS"
echo "  Total number of hosts: $TOTAL_HOSTS"
echo "  Message sizes: [$(IFS=', '; echo "${SIZES[*]}")]"
echo "  Interface ranges: [$(IFS=', '; echo "${RANGES[*]}")]"
echo "  Scenario name: $SCENARIO_NAME"

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
    local job_id="${size}_${run}_${range}"
    
    echo "[$(date '+%H:%M:%S')] Starting simulation ${job_id}"

    cd the-one
    ./one.sh -b 1 \
        "$SCENARIO_NAME-settings-${size}-${run}-${range}.txt" \
        "$SCENARIO_NAME-comms-settings-${size}-${range}.txt"
    rm "$SCENARIO_NAME-settings-${size}-${run}-${range}.txt" \
        "$SCENARIO_NAME-comms-settings-${size}-${range}.txt"
    cd -
    
    echo "[$(date '+%H:%M:%S')] Completed simulation ${job_id}"
}

wait_for_jobs() {
    local max_jobs=$1
    while [ $(jobs -r | wc -l) -ge $max_jobs ]; do
        sleep 1
    done
}

prepare_config_files() {
    echo "Preparing configuration files..."

    sed -i -e "s/Events1.hosts = .*/Events1.hosts = 0,$TOTAL_HOSTS/" \
            -e "s/Events1.toHosts = .*/Events1.toHosts = 0,$TOTAL_HOSTS/" \
                the-one/$SCENARIO_NAME-comms-settings.txt
    sed -i -e "s/Group1.nrofHosts = .*/Group1.nrofHosts = $TOTAL_HOSTS/" \
                the-one/$SCENARIO_NAME-settings.txt
    for size in "${SIZES[@]}"; do
        for run in $(seq 1 $NUM_RUNS); do
            for range in "${RANGES[@]}"; do
                RANDOM_SEED=$((size+run*100+range*1000))
                sed -e "s/Scenario.name = .*/Scenario.name = ${SCENARIO_NAME}_${size}_run${run}_range${range}/" \
                    -e "s/MovementModel.rngSeed = .*/MovementModel.rngSeed = ${RANDOM_SEED}/" \
                    the-one/$SCENARIO_NAME-settings.txt > "the-one/$SCENARIO_NAME-settings-${size}-${run}-${range}.txt"
            done
        done

        for range in "${RANGES[@]}"; do
            sed -e "s/Events1.size = .*/Events1.size = $size/" \
                -e "s/bluetoothInterface.transmitRange = .*/bluetoothInterface.transmitRange = $range/" \
                    the-one/$SCENARIO_NAME-comms-settings.txt > "the-one/$SCENARIO_NAME-comms-settings-${size}-${range}.txt"
        done
    done

    python room/main.py --hosts $TOTAL_HOSTS --name hall --x_offset 50 --y_offset 50
}

run_simulations() {
    local NUMBER_OF_SIZES=${#SIZES[@]}
    local NUMBER_OF_RANGES=${#RANGES[@]}
    local TOTAL_SIMULATIONS=$((NUMBER_OF_SIZES * NUMBER_OF_RANGES * NUM_RUNS))

    echo "Starting parallel simulations with up to $MAX_PARALLEL_JOBS concurrent jobs..."
    echo "Total simulations to run: $TOTAL_SIMULATIONS"
    start_timestamp=$(date +%s)
    echo "Start time: $(date)"

    total_jobs=0
    for size in "${SIZES[@]}"; do
        for range in "${RANGES[@]}"; do
            echo "Scheduling simulations for message size: $size, communication radius: $range"
            for run in $(seq 1 $NUM_RUNS); do
                wait_for_jobs $MAX_PARALLEL_JOBS
                run_simulation $size $run $range &

                total_jobs=$((total_jobs + 1))
                echo "Scheduled job $total_jobs/$TOTAL_SIMULATIONS: size=$size, run=$run, range=$range"   
                
                sleep 0.1
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