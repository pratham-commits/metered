# Person 2 owns this algorithm. Person 1 calls it when a driver goes online.
#
# Class HashRing(nodes, vnodes=100). Position is MD5 of the key, first node clockwise.
# Virtual node label is "{node}#{i}".
# Methods: add, owner, ownership(keys) -> {key: node}.
# nodes_from_env(raw) splits HASH_NODES on commas.
# Do not use Python's built-in hash(). It changes per process.
# Test: services/common/tests/test_ring.py must pass. Adding p4 must move some zones and leave some put.
