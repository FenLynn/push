#!/bin/bash
echo $(date)

ROOT_DIR=${PUSHPATH}
SCRIPT_DIR=${ROOT_DIR}'/finance'


source ~/.bashrc
conda activate py39
cd ${SCRIPT_DIR}

python main_margin.py -stock
