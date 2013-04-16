#!/usr/bin/env python

import sys
import os
import time

outf = open("script/speed_out.txt", "a")
begin = time.time()
os.system("./script/runspeed.sh")
end = time.time()
print "total time:",end-begin

#os.system("diff a_counters.txt ./script/a_counters.txt")
#os.system("diff b_counters.txt ./script/b_counters.txt")
#os.system("diff a_flow.txt ./script/a_flow.txt")
#os.system("diff b_flow.txt ./script/b_flow.txt")

outf.write("** {}: {} {} {:.3f}\n".format(str(time.asctime()).strip(), sys.version.strip().replace('\n',''), ':'.join(os.uname()), end-begin))
outf.close()
