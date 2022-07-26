import statistics as stat
import networkx as nx
import logging
logger = logging.getLogger("Engine")

# Sample array from profiler includes only the node id integer. This class expands it to include additional timing data.
# node_idx provides an index into the nodes list within the profile class. 
class Sample:
    def __init__(self, node_idx: int, delta_to_last: int,  cum_ts: int, elapsed_time: int):
        self.node_idx = node_idx
        self.delta_to_last = delta_to_last
        self.cum_ts = cum_ts
        self.elapsed_time = elapsed_time

# Holds Node data. A Node represents a function/stack frame in the profile. 
class ProfileNode:
    def __init__(self, hit_count: int, call_frame: dict, children: list):
        self.hit_count = hit_count
        self.children = children
        self.power_measurements = []
        self.avg_watts = 0
        self.call_frame= {x: call_frame[x] for x in call_frame if x not in ["_id"]}
    
    def append_pwr_measurement(self, measurement):
        self.power_measurements.append(measurement)
        self.avg_watts = stat.mean(self.power_measurements)

# Holds all data structures related to a cpu profile. Generates addional analytic data upon construction given a profile dictonary pulled from the db
class CpuProfile:
    def __init__(self, prof_raw: dict):
        self.sample_timeline = []
        self.start_time = prof_raw["startTime"]
        self.end_time = prof_raw["endTime"]
        self.runtime = prof_raw["endTime"] - prof_raw["startTime"]
        self.compressed_timeline = None
        self.node_map  = None
        self.node_dir_graph = None
        
        #Excludes very large first delta from when profiler initializes
        self.delta_stats = {
            "avg": stat.mean(prof_raw["timeDeltas"]),
            "max": max(prof_raw["timeDeltas"]), #excludes first one which is always 
            "min": min(prof_raw["timeDeltas"]),
            }
        
        self._generate_timeline(prof_raw)
        self._build_maps(prof_raw)
        self._build_directed_node_graph()
        logger.debug("CPU profile processed.")


    def _generate_timeline(self, raw: dict) -> None:
        cum_ts = raw["startTime"] 
        elapsed_time = 0

        for i, s in enumerate(raw["samples"]):
            cum_ts += raw["timeDeltas"][i]
            elapsed_time += raw["timeDeltas"][i]
            self.sample_timeline.append(
                Sample(s, raw["timeDeltas"][i], int(cum_ts), elapsed_time)
        )

        self.runtime_from_deltas = elapsed_time

    # Puts profile nodes into a dictionary indexed by profilerId.
    def _build_maps(self, raw: dict) -> None:
        node_map = {}

        for node in raw["nodes"]:
            node_map[node["profilerId"]] = ProfileNode(node["hitCount"], node["callFrame"], node["children"]) 
        
        self.node_map = node_map

    # Graph nodes are only the profileId int, corresponding objects can be retrieved from node_map using the id
    # All nodes in the graph are reachable from node 1 (root), there are no cycles, and all nodes except node 1
    # have an in degree of 1 and a 0-N out degree.  
    def _build_directed_node_graph(self) -> None:
        node_graph = nx.DiGraph()
        node_graph.add_nodes_from(self.node_map.keys())
        for id,node in self.node_map.items():
            if len(node.children) > 0:
                node_graph.add_edges_from(([(id,child) for child in node.children]))
        
        self.node_dir_graph = node_graph


