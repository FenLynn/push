#!/bin/bash
echo $(date)

ROOT_DIR=${PUSHPATH}
SCRIPT_DIR=${ROOT_DIR}'/reminder'


source ~/.bashrc
conda activate py39
cd ${SCRIPT_DIR}

python main.py -paper
#python main.py
