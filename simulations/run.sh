#!/bin/bash

set -e

DEFAULT_MAX_PARALLEL_JOBS=1
DEFAULT_NUM_RUNS=50
DEFAULT_SIZES=(100 1000 10000 100000 1000000 5000000)
DEFAULT_SCENARIO_NAME="ER"  # $SCENARIO_NAME
DEFAULT_TOTAL_HOSTS=50

while [[ $# -gt 0 ]]; do
    case $1 in
        -j|--jobs)
            MAX_PARALLEL_JOBS="$2"
            shift 2
            ;;
        -r|--runs)
            NUM_RUNS="$2"
            shift 2
            ;;
        -s|--sizes)
            SIZES="$2"
            shift 2
            ;;
        -n|--name)
            SCENARIO_NAME="$2"
            shift 2
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
SIZES=("${SIZES[@]:-${DEFAULT_SIZES[@]}}")
SCENARIO_NAME=${SCENARIO_NAME:-$DEFAULT_SCENARIO_NAME}
TOTAL_HOSTS=${TOTAL_HOSTS:-$DEFAULT_TOTAL_HOSTS}
TOTAL_NUMBER_HOSTS=$TOTAL_HOSTS
echo "Configuration:"
echo "  Maximum parallel jobs: $MAX_PARALLEL_JOBS"
echo "  Number of runs: $NUM_RUNS"
echo "  Total number of hosts: $TOTAL_NUMBER_HOSTS"
echo "  Message sizes: [$(IFS=', '; echo "${SIZES[*]}")]"
echo "  Scenario name: $SCENARIO_NAME"

print_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "Options:"
    echo "  -j, --jobs NUM       Maximum number of parallel jobs (default: $DEFAULT_MAX_PARALLEL_JOBS)"
    echo "  -r, --runs NUM       Number of runs per size (default: $DEFAULT_NUM_RUNS)"
    echo "  -s, --sizes \"LIST\" Space-separated list of message sizes (default: \"$DEFAULT_SIZES\")"
    echo "  -n, --name STRING    Name of the scenario to use (default: \"$DEFAULT_SCENARIO_NAME\")"
    echo "  -t, --total-hosts NUM Total number of nodes in the simulation (default: $DEFAULT_TOTAL_HOSTS)"
    echo "  -h, --help           Show this help message"
    echo ""
    echo "This script generates random stationary nodes for simulations."
    echo ""
    echo "Example:"
    echo "  $0 --name ER --jobs 16 --runs 50 --sizes \"100 1000 10000\" --total-hosts 100"
}

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
    local job_id="${size}_${run}"
    
    echo "[$(date '+%H:%M:%S')] Starting simulation ${job_id}"
    
    # Create temporary config file with unique scenario name for each run
    sed -e "s/Scenario.name = .*/Scenario.name = ER_${size}_run${run}/" \
        the-one/$SCENARIO_NAME-settings.txt > "the-one/$SCENARIO_NAME-settings-${size}-${run}.txt"

    cd the-one
    ./one.sh \
        "$SCENARIO_NAME-settings-${size}-${run}.txt" \
        "$SCENARIO_NAME-comms-settings-${size}.txt"
    cd -
    
    # Clean up temporary config file
    rm -f "the-one/$SCENARIO_NAME-settings-${size}-${run}.txt"
    
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
    sed -i '' -e "s/Events1.hosts = .*/Events1.hosts = 1,$TOTAL_NUMBER_HOSTS/" \
        -e "s/Events1.toHosts = .*/Events1.toHosts = 1,$TOTAL_NUMBER_HOSTS/" \
                the-one/$SCENARIO_NAME-comms-settings.txt
    for size in "${SIZES[@]}"; do
        sed -e "s/Events1.size = .*/Events1.size = $size/" \
                the-one/$SCENARIO_NAME-comms-settings.txt > "the-one/$SCENARIO_NAME-comms-settings-${size}.txt"
    done

    python room/main.py --hosts $TOTAL_NUMBER_HOSTS --name hall --x_offset 50 --y_offset 50
}

run_simulations() {
    local NUMBER_OF_SIZES=${#SIZES[@]}
    local TOTAL_SIMULATIONS=$((NUMBER_OF_SIZES * NUM_RUNS))

    echo "Starting parallel simulations with up to $MAX_PARALLEL_JOBS concurrent jobs..."
    echo "Total simulations to run: $TOTAL_SIMULATIONS"
    start_timestamp=$(date +%s)
    echo "Start time: $(date)"

    total_jobs=0
    for size in "${SIZES[@]}"; do
        echo "Scheduling simulations for message size: $size"
        for run in $(seq 1 $NUM_RUNS); do
            wait_for_jobs $MAX_PARALLEL_JOBS
            run_simulation $size $run &
            
            total_jobs=$((total_jobs + 1))
            echo "Scheduled job $total_jobs/$TOTAL_SIMULATIONS: size=$size, run=$run"
            
            sleep 0.1
        done
    done

    end_timestamp=$(date +%s)
    duration=$((end_timestamp-start_timestamp))

    echo "Waiting for all simulations to complete..."
    wait

    echo "All simulations completed!"
    echo "End time: $(date)"
    echo "Took $duration seconds" 
    
    ls -la the-one/reports_data/ | grep "ER_" | wc -l | xargs echo "Total report files:"
    echo "The resulting reports data can be found under the the-one/reports_data/ directory"
}

compile
prepare_config_files
run_simulations