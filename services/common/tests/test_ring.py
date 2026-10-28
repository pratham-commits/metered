# Person 2. Run before Matching is written. No AWS needed.
#
# PYTHONPATH=services/common pytest services/common/tests/test_ring.py
# Same nodes and zones always return the same owner.
# HashRing of p0-p3 versus p0-p4: at least one zone stays, at least one zone moves.
# Owners of the second ring are only those five names.
