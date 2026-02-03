#!/bin/bash
echo $(date)

ROOT_DIR=${PUSHPATH}
SCRIPT_DIR=${ROOT_DIR}'/damai'


source ~/.bashrc
conda activate py39
cd ${SCRIPT_DIR}

python main.py -baobao -成都
sleep 10
python main.py -baobao -西安
