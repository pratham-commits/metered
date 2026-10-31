import pytest
from rideshare.hashring import HashRing
from rideshare.zones import all_zones,center,zone_for,neighbors
from rideshare.fare import quote_cents,quote_between


def test_zones_round_trip_and_boundaries():
    for zone in all_zones():
        assert zone_for(*center(zone))==zone
        assert zone in neighbors(zone)
    assert zone_for(17.5,78.5)=='z33'
    assert len(neighbors('z00'))==4
    assert len(neighbors('z11'))==9


def test_ring_addition_only_moves_to_new_node():
    ring=HashRing(['p0','p1','p2','p3']);before=ring.ownership(all_zones())
    ring.add('p4');after=ring.ownership(all_zones())
    moved=[z for z in before if before[z]!=after[z]]
    assert 0<len(moved)<16
    assert all(after[z]=='p4' for z in moved)


@pytest.mark.parametrize('imbalance,surge',[(0,1),(1.49,1),(1.5,1.5),(3,2)])
def test_fare_thresholds(imbalance,surge):
    amount,actual,minutes=quote_cents(5,imbalance)
    assert actual==surge
    assert minutes==12
    assert amount==round(12400*surge)
    assert quote_between('z11','z11',imbalance)['distance_km']==0
