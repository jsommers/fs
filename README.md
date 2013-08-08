# FS: a network flow record generator

FS is a network flow record generator.  It contains a discrete event
simulation core to generate the flow records, and relies on existing 
TCP throughput models to drive the simulation.

FS is made available under terms of the GPLv2.

Note: the originally released version of fs (as described in the INFOCOM '11)
research paper is on branch fs-orig.  The master branch is completely revamped
and includes the fs-sdn code as described in a forthcoming HotSDN paper (fs-sdn).


## Running fs

FS is implemented in Python and has a few external module dependencies:

To use fs, you need the following Python packages:
 * ipaddr 
 * networkx 
 * pydot 
 * pyparsing 
 * pytricia (py-radix is no longer supported)

To install all the above, see the requirements.txt file here and use pip:

    $ pip install -r requirements.txt

I'd recommend using virtualenv, then installing the packages inside
the venv.  See http://pypi.python.org/pypi/virtualenv.

fs runs fastest using pypy (http://pypy.org) but also works well under the
standard CPython implementation.  

## Examples

There are a number of example configuration files in the `conf/` directory.  To run a couple of the example configuration files for 600 simulated seconds, you might do something like:

    $ python -OO fs.py -t 600 conf/ex1.dot
    $ python -OO fs.py -t 600 conf/testconf1.json

`fs` supports a DOT configuration file syntax as well as a (basically equivalent) JSON syntax.  For now, config file syntax is undocumented; take a look at the examples and our 2011 INFOCOM paper: http://dx.doi.org/10.1109/INFCOM.2011.5935055

To use the OpenFlow extensions (aka fs-sdn), you'll need to clone the POX git repository and point your PYTHONPATH to it.  `fs` currently is only tested with the betta branch (currently default branch) of POX.  Once you've done those things, there are two example configurations in the `conf` folder that should work out-of-the-box:

    $ git clone git://github.com/noxrepo/pox.git ../pox
    $ export PYTHONPATH=`pwd`/../pox
    $ python -OO fs.py -t 60 conf/openflow_small_cbr.dot
    $ python -OO fs.py -t 60 conf/openflow_small_harpoon.dot

The first few lines of output from fs when running one of the above example (OpenFlow) configurations should be:

    0.0000 fslib.config INFO     Reading config for graph test.
    0.0000 fslib.config INFO     Running measurements on these nodes: <a,c,b,controller>
        POX 0.1.0 (betta) / Copyright 2011-2013 James McCauley, et al.
    0.0000 fs           INFO     Monkeypatching POX for integration with fs
    0.0000 core         INFO     POX 0.1.0 (betta) is up.
    0.0000 fs.core      INFO     simulation completion: 0.00
    0.0600 openflow.of_01 INFO     [00-02-e4-0d-b1-e0 1] connected
    0.0600 openflow.of_01 INFO     [00-02-f3-4f-f4-e2 2] connected
    0.0600 openflow.of_01 INFO     [00-02-eb-ae-d3-63 3] connected


## Acknowledgments

This software is based up on work supported by the National Science Foundation under Grant No. CNS-1054985.  Any opinions, findings, and conclusions or recommendations expressed in this material are those of the author(s) and do not necessarily reflect the views of the National Science Foundation.

----------

Copyright 2011-2013  Joel Sommers.  All rights reserved.

This file is part of fs, a network flow record generation tool.

fs is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

fs is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with fs; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

