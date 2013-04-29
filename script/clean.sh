#!/bin/bash

rm -f *_flow.txt
rm -f *_counters.txt
find . -name \*\.pyc -exec rm {} \;
find . -name \*\.pyo -exec rm {} \;
