#!/bin/bash
echo $(date)

_PWD=$(pwd)

ROOT_DIR='/work/push/report/'
PY_DIR=${ROOT_DIR}'py'
TEX_DIR=${ROOT_DIR}'tex'


source ~/.bashrc
conda activate py39
cd ${PY_DIR}
python gen_tex.py


cd ${TEX_DIR}
xelatex main.tex
xelatex main.tex


cd ${PY_DIR}
python auto_send.py

cd ${_PWD}
