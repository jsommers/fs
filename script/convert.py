import sys
from networkx import read_gml, write_dot,MultiGraph
from os.path import splitext, basename
import math
import random
import ipaddr

def distance(lon1, lat1, lon2, lat2, sol=2.0e8):
    R = 40003.2/(math.pi*2) * 1000 # meters
    # R = 3963.1 # miles

    lon1 = math.radians(lon1)
    lat1 = math.radians(lat1)
    lon2 = math.radians(lon2)
    lat2 = math.radians(lat2)
    
    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = (math.sin(dlat/2))**2 + math.cos(lat1) * math.cos(lat2) * (math.sin(dlon/2))**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    d = R * c
    return '{:.3f}ms'.format(d/sol*1000)

def add_traffic(graph, pairs=8):
    subnet = ipaddr.IPv4Network('10.0.0.0/8')
    numsubnets = int(math.log(pairs,2) + 1)
    subiter = subnet.iter_subnets(numsubnets)
    added = 0
    while True:
        a, b = random.sample(graph.nodes(),2)
        try:
            srcnet = next(subiter)
            dstnet = next(subiter)
        except StopIteration:
            break
        added += 1
        adict = graph.node[a]
        bdict = graph.node[b]
        if 'ipdests' in graph.node[a]:
            graph.node[a]['ipdests'] = '{} {}'.format(graph.node[a]['ipdests'], srcnet)
        else:
            graph.node[a]['ipdests'] = srcnet 

        if 'ipdests' in graph.node[b]:
            graph.node[b]['ipdests'] = '{} {}'.format(graph.node[b]['ipdests'], dstnet)
        else:
            graph.node[b]['ipdests'] = dstnet
        graph.node[a]['traffic'] = 'm1'
        graph.node[a]['m1'] = "modulator start=0.0 generator=s1 profile=((3600,),(1,))"
        graph.node[a]['s1'] = 'harpoon ipsrc={} ipdst={} $harpoonsubspec'.format(srcnet, dstnet)
    print "Added {} src/dst traffic generation pairs".format(added)

def add_measurement(graph, numnodes=1):
    mnodes = random.sample(graph.nodes(), numnodes)
    return ' '.join([str(x) for x in mnodes])

if len(sys.argv) != 2:
    print >>sys.stderr,"Error: need a gml graph name"
    sys.exit()

outname = splitext(sys.argv[1])[0] + '.dot'
basename = splitext(basename(sys.argv[1]))[0]
random.seed(1)

print "Reading {}, writing {}".format(sys.argv[1], outname)

graph = read_gml(sys.argv[1])
hsubspec = "flowsize=exponential(1/10000.0) flowstart=exponential(100) ipproto=randomchoice(6) sport=randomchoice(22,80,443) dport=randomunifint(1025,65535) lossrate=randomchoice(0.001)"

mnodes = add_measurement(graph)

newgraph = MultiGraph(name=basename, 
                      counterexportfile=basename+"_counters", 
                      flowexport="text",
                      flowsampling=1.0,
                      pktsampling=1.0,
                      exportcycle=60,
                      counterexport=True,
                      counterexportinterval=1,
                      longflowtmo=60,
                      flowinactivetmo=60,
                      harpoonsubspec=hsubspec,
                      measurementnodes=mnodes)

def get_cap(label):
    if 'OC192/STM64' in label:
        return '10Gb'
    elif 'OC3' in label:
        return '155Mb'
    elif 'OC12' in label:
        return '622Mb'
    elif 'OC48' in label:
        return '2.4Gb'
    else:
        return '1Gb'

for n1,n2,ed in graph.edges_iter(data=True):
    # print n1, n2, ed
    n1d = graph.node[n1]
    n2d = graph.node[n2]
    # print n1d,n2d
    dist = distance(n1d['Longitude'],n1d['Latitude'],n2d['Longitude'],n2d['Latitude'])
    # print dist
    loc1 = '{}, {}'.format(n1d['label'], n1d['Country'])
    loc2 = '{}, {}'.format(n2d['label'], n2d['Country'])
    span = '{} to {}'.format(loc1, loc2)
    newgraph.add_node(n1, autoack='False', location=loc1)
    newgraph.add_node(n2, autoack='False', location=loc2)
    cap = get_cap(ed['LinkLabel'])
    newgraph.add_edge(n1, n2, weight=1, capacity=cap, delay=dist, span=span)

add_measurement(newgraph)
add_traffic(newgraph)
write_dot(newgraph, outname)
