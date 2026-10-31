from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

import grpc
import pytest
from fastapi.testclient import TestClient
from psycopg.errors import UniqueViolation


def db_mock(monkeypatch, module, row=None, error=None):
    conn=MagicMock()
    conn.execute.return_value.fetchone.return_value=row
    if error:
        conn.execute.side_effect=error
    @contextmanager
    def connection():
        yield conn
    monkeypatch.setattr(module,'connection',connection)
    return conn


@pytest.mark.parametrize('service',['rider','driver'])
def test_register(apps,monkeypatch,service):
    module=apps[service]
    conn=db_mock(monkeypatch,module)
    result=TestClient(module.app).post('/'+service+'s',json={'name':'Test','phone':'9999999999'})
    assert result.status_code==201
    assert result.json()['id']
    assert 'INSERT INTO' in conn.execute.call_args_list[-1].args[0]


@pytest.mark.parametrize('service',['rider','driver'])
@pytest.mark.parametrize('race',[False,True])
def test_duplicate_phone(apps,monkeypatch,service,race):
    module=apps[service]
    db_mock(monkeypatch,module,row=None if race else ('id',),error=UniqueViolation() if race else None)
    result=TestClient(module.app).post('/'+service+'s',json={'name':'Test','phone':'9999999999'})
    assert result.status_code==409


@pytest.mark.parametrize('service',['rider','driver'])
def test_missing_and_malformed_profile(apps,monkeypatch,service):
    module=apps[service];db_mock(monkeypatch,module)
    client=TestClient(module.app)
    assert client.get('/'+service+'s/'+str(uuid4())).status_code==404
    assert client.get('/'+service+'s/not-a-uuid').status_code==422
    assert client.post('/'+service+'s',json={'name':'','phone':'1'}).status_code==422
    assert client.get('/healthz').status_code==200


def test_presence_and_real_grpc(apps,monkeypatch,store):
    module=apps['driver'];driver_id=str(uuid4())
    db_mock(monkeypatch,module,row=(driver_id,))
    monkeypatch.setattr(module,'get_store',lambda:store)
    monkeypatch.setattr(store,'publish',lambda event:True)
    with TestClient(module.app) as client:
        response=client.post(f'/drivers/{driver_id}/presence',json={'status':'ONLINE','lat':17.375,'lng':78.375})
        assert response.status_code==200,response.text
        result=response.json();assert result['zone']=='z11'
        from ride.v1 import driver_pb2,driver_pb2_grpc
        with grpc.insecure_channel('127.0.0.1:9002') as channel:
            candidates=driver_pb2_grpc.DriverLookupStub(channel).GetCandidates(driver_pb2.CandidateRequest(partition_id=result['partition_id'],pickup_zone='z11'),timeout=5)
            assert candidates.candidates[0].driver_id==driver_id
        assert store.assign(result['partition_id'],driver_id,'ride-A')
        response=client.post(f'/drivers/{driver_id}/presence',json={'status':'ONLINE','lat':17.375,'lng':78.375})
        assert response.status_code==409


def test_presence_validation(apps,monkeypatch,store):
    module=apps['driver'];db_mock(monkeypatch,module)
    monkeypatch.setattr(module,'get_store',lambda:store)
    client=TestClient(module.app);url=f'/drivers/{uuid4()}/presence'
    body={'status':'ONLINE','lat':17.375,'lng':78.375}
    assert client.post(url,json=body).status_code==404
    assert client.post(url,json=dict(body,status='BUSY')).status_code==400
    assert client.post(url,json=dict(body,zone='z00')).status_code==400
    assert client.post(url,json=dict(body,lat=200)).status_code==422
