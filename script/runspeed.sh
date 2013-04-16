#!/bin/bash

export PYTHONPATH=.:../pox:$PYTHONPATH
python -OO fs.py -s42 -i1 -t600 conf/simple_speed.json
