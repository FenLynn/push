#!/bin/bash
echo $(date)

ROOT_DIR=${PUSHPATH}
SCRIPT_DIR=${ROOT_DIR}'/hot'


source ~/.bashrc
conda activate py39

cd ${SCRIPT_DIR}/weibo/
python spider.py
#python analysis.py


cd ${SCRIPT_DIR}/zhihu
python main.py



_IDLE=`tr -cd '0-9' </dev/urandom | head -c 3`
echo ${_IDLE}
sleep ${_IDLE}

cd ${SCRIPT_DIR}
python main.py -baobao 
