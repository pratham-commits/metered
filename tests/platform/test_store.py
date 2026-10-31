import json
import pytest
from botocore.stub import Stubber


def test_assignment_is_exclusive_and_retry_safe(store, driver_item):
    store.put_driver(driver_item)
    assert store.assign('p0','driver-1','ride-A')
    assert store.assign('p0','driver-1','ride-A')
    assert not store.assign('p0','driver-1','ride-B')
    assert not store.assign('p0','missing','ride-A')
    assert store.query_available('p0',['z11']) == []
    store.release('p0','driver-1')
    assert store.assign('p0','driver-1','ride-B')


def test_presence_cannot_reset_assignment(store, driver_item):
    store.put_driver(driver_item)
    store.assign('p0','driver-1','ride-A')
    with pytest.raises(ValueError, match='assigned'):
        store.set_presence(driver_item,['p0','p1'])
    assert not store.assign('p0','driver-1','ride-B')


def test_presence_move_is_atomic_and_removes_old_partition(store, driver_item):
    store.put_driver(driver_item)
    moved = dict(driver_item, partition_id='p1',zone='z22')
    store.set_presence(moved,['p0','p1'])
    assert store.query_available('p0',['z11']) == []
    assert store.query_available('p1',['z22'])[0]['driver_id']=='driver-1'
    assert not store.assign('p0','driver-1','ride-A')


def test_assigned_driver_cannot_move(store, driver_item):
    store.put_driver(driver_item)
    store.assign('p0','driver-1','ride-A')
    with pytest.raises(ValueError):
        store.set_presence(dict(driver_item,partition_id='p1'),['p0','p1'])
    assert store.query_available('p1',['z11']) == []


def test_query_paginates(store, driver_item):
    raw = {k:{'N' if k in ['lat','lng'] else 'S':str(v)} for k,v in driver_item.items()}
    key={'partition_id':{'S':'p0'},'driver_id':{'S':'driver-1'}}
    with Stubber(store.ddb) as stub:
        stub.add_response('query',{'Items':[], 'LastEvaluatedKey':key})
        stub.add_response('query',{'Items':[raw]})
        assert len(store.query_available('p0',['z11']))==1
        stub.assert_no_pending_responses()


def test_demand_latest_window(store):
    store.put_demand({'zone':'z11','window_start':'2026-10-29T00:00:00Z','imbalance':1})
    store.put_demand({'zone':'z11','window_start':'2026-10-29T00:01:00Z','imbalance':3})
    assert store.latest_demand('z11')['imbalance']=='3'
    assert store.latest_demand('z22') is None
    assert len(store.latest_all())==1


def test_queue_and_object_round_trip(store):
    assert store.send_job({'ride_id':'ride-A'})
    receipt, body=store.receive_jobs(1)[0]
    assert body['ride_id']=='ride-A'
    store.delete_job(receipt)
    store.put_object('completions/ride-A.json',json.dumps(body).encode())
    assert json.loads(store.s3.get_object(Bucket=store.bucket,Key='completions/ride-A.json')['Body'].read())==body


def test_no_broker_is_reported(store):
    assert store.publish({'event_type':'DRIVER_STATUS'}) is False
