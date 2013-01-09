#!/bin/sh
REPO_ID="f17_x86_64"

DATE_STAMP=`date +%F_%H:%M`
OUTPUT="memory_data_started.${DATE_STAMP}"
MOD_WSGI_PID=`ps auxf | grep wsgi:pulp | grep -v grep | awk '{print $2}'`
PULP_CMD="pulp-admin rpm repo sync run --repo-id ${REPO_ID}"

echo "Writing output to: ${OUTPUT}"
echo "Will track memory usage of mod_wsgi PID: ${MOD_WSGI_PID}"
echo "Will track memory usage of mod_wsgi PID: ${MOD_WSGI_PID}" >> ${OUTPUT}
echo "Sync command: ${PULP_CMD}" >> ${OUTPUT}
pmap -d ${MOD_WSGI_PID} | tail -n 1 >> ${OUTPUT}

COUNTER=0
while [ 1 ]
do
    echo "run ${COUNTER} started at: `date +%H:%M:%S_%F`"
    echo "" >> ${OUTPUT}
    echo "run ${COUNTER} started at: `date +%H:%M:%S_%F`" >> ${OUTPUT}
    ps auxf | grep wsgi:pulp | grep -v grep >> ${OUTPUT}
    ${PULP_CMD}
    pmap -d ${MOD_WSGI_PID} | tail -n 1 
    pmap -d ${MOD_WSGI_PID} | tail -n 1 >> ${OUTPUT}
    sleep 1
    COUNTER=$(( $COUNTER + 1))
done

