#!/bin/bash

export PYTHONPATH=.:../pox:$PYTHONPATH
# python -O fs.py -i1 -t60 conf/openflow1.dot 
# python -O fs.py -i1 -t600 conf/ex_simple.dot
# python -O fs.py -i1 -t600 conf/ex_pareto.dot

# python -O fs.py -i1 -t600 conf/openflow_spf_small_harpoon.dot
# python -O fs.py -i1 -t60 conf/openflow_spf_small_cbr.dot

python -O fs.py -i1 -t60 conf/test.conf
