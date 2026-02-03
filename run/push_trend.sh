#!/bin/bash
echo $(date)

ROOT_DIR=${PUSHPATH}
SCRIPT_DIR=${ROOT_DIR}'/trend'


source ~/.bashrc
conda activate py39
cd ${SCRIPT_DIR}

python main.py
#python main.py -baobao
