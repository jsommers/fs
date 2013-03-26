#!/bin/bash 

export PYTHONPATH=.:../pox
for tfile in spec/*spec.py
do
    echo "** Running tests in ${tfile} **"
    python ${tfile}
done

