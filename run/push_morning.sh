#!/bin/bash
echo $(date)

##################发送函数############
function send_group(){
    python main.py '-'$1
}

###################环境变量############
ROOT_DIR=${PUSHPATH}
SCRIPT_DIR=${ROOT_DIR}'/morning'
ISSEND=1

###################环境搭建############
source ~/.bashrc
conda activate py39
cd ${SCRIPT_DIR}

#################群组发送##############
list='baobao'
#list='me'
for i in ${list}
do
    echo ${i}
    if [ ${ISSEND} -eq 1 ];then
        send_group $i
    fi
done
