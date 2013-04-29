import cProfile
import random
import sys

random.seed(42)

sys.path.append(".")
sys.path.append("./traffic_generators")
sys.path.append("./tcpmodels")
sys.path.append("./flowexport")

import fs
sim = fs.FsCore(1, 10, debug=False)

p = cProfile.Profile()
p.run("sim.run('conf/simple_speed.json', configonly=False)")
p.print_stats(sort=1)

