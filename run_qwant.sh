#! /bin/bash
##################################################################
# 2 args
# * name of the test
# api-url
#
# Create a logs and results file in a results_${NAME} directory
#
# Note: it's better to run this test with `time`
##################################################################

if [ "$#" -ne 2 ]; then
    echo "you should provide the name of the test and the api-url"
    exit 1
fi


NAME=$1
API_URL=$2

OUTPUT_DIR="results_${NAME}"
mkdir -p $OUTPUT_DIR
GLOBAL_LOG="$OUTPUT_DIR/run.log"

rm -f $GLOBAL_LOG
echo "testing $NAME on $API_URL" | tee -a $GLOBAL_LOG

call_pytest() {
    local TEST_NAME="$1"
    local DIR="$2"
    local SELECTOR="$3"
    local LOG_FILE="$OUTPUT_DIR/$TEST_NAME.log"

    pytest $DIR --api-url ${API_URL} -k "$SELECTOR" --loose-compare --save-report=$OUTPUT_DIR/$TEST_NAME.txt --tb=short > $LOG_FILE

    echo -e "summary for $TEST_NAME " $(grep '=======' $LOG_FILE | grep seconds) | tee -a $GLOBAL_LOG
}

call_all() {
    for COUNTRY in "france" "italy" "germany" ; do

        for TEST in "autre" "fautes"; do
            if [ "$TEST" = "fautes" ]; then
                SELECTOR="fuzzy"
            else
                SELECTOR="not fuzzy"
            fi
            echo "running test ${COUNTRY}_$TEST" | tee -a $GLOBAL_LOG
            call_pytest "${COUNTRY}_$TEST" "geocoder_tester/world/$COUNTRY/" "$SELECTOR"
        done
    done
}

call_all
