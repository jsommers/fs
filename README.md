# FS: a network flow record generator

FS is a network flow record generator.  It contains a discrete event
simulation core to generate the flow records, and relies on existing 
TCP throughput models to drive the simulation.

FS is made available under terms of the GPLv2.

Note: the originally released version of fs (as described in the INFOCOM '11)
research paper is on branch fs-orig.  The master branch is completely revamped
and includes the fs-sdn code as described in a forthcoming HotSDN paper (fs-sdn).
Better (any) documentation is coming.

# Running fs

FS is implemented in Python and has a few external module dependencies:

To use fs, you need the following Python packages:
 * ipaddr 
 * networkx 
 * pydot 
 * pyparsing 
 * pytricia (py-radix is no longer supported)

To install all the above, see the requirements.txt file here and use pip:

    pip install -r requirements.txt

I'd recommend using virtualenv, then installing the packages inside
the venv.  See http://pypi.python.org/pypi/virtualenv.

fs runs fastest using pypy (http://pypy.org) but also works well under the
standard CPython implementation.  

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

