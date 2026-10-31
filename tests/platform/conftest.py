import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/common'))

@pytest.fixture(scope='session')
def apps(tmp_path_factory):
    output = tmp_path_factory.mktemp('proto')
    subprocess.run([sys.executable, '-m', 'grpc_tools.protoc', '-I', str(ROOT/'proto'),
                    '--python_out='+str(output), '--grpc_python_out='+str(output),
                    str(ROOT/'proto/ride/v1/driver.proto'), str(ROOT/'proto/ride/v1/dispatch.proto')], check=True)
    sys.path.insert(0, str(output))
    result = {}
    for service in ['rider', 'driver']:
        spec = importlib.util.spec_from_file_location(service+'_app', ROOT/f'services/{service}/app.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        result[service] = module
    return result

@pytest.fixture
def store(monkeypatch):
    from moto import mock_aws
    from rideshare.aws import Store
    for key,value in {'AWS_ACCESS_KEY_ID':'testing','AWS_SECRET_ACCESS_KEY':'testing',
                      'AWS_REGION':'ap-south-1','AWS_DEFAULT_REGION':'ap-south-1',
                      'DRIVER_TABLE':'rideshare_driver_live','DEMAND_TABLE':'rideshare_demand_windows',
                      'TRIP_BUCKET':'rideshare-trip-files-local'}.items():
        monkeypatch.setenv(key,value)
    monkeypatch.delenv('AWS_ENDPOINT_URL', raising=False)
    monkeypatch.delenv('KAFKA_BOOTSTRAP', raising=False)
    with mock_aws():
        client=Store()
        for table,pk,sk in [(client.driver_table,'partition_id','driver_id'),(client.demand_table,'zone','window_start')]:
            client.ddb.create_table(TableName=table,KeySchema=[{'AttributeName':pk,'KeyType':'HASH'},{'AttributeName':sk,'KeyType':'RANGE'}],AttributeDefinitions=[{'AttributeName':pk,'AttributeType':'S'},{'AttributeName':sk,'AttributeType':'S'}],BillingMode='PAY_PER_REQUEST')
        client.s3.create_bucket(Bucket=client.bucket,CreateBucketConfiguration={'LocationConstraint':'ap-south-1'})
        client.queue_url=client.sqs.create_queue(QueueName='rideshare-match-jobs')['QueueUrl']
        yield client

@pytest.fixture
def driver_item():
    return dict(partition_id='p0',driver_id='driver-1',zone='z11',status='AVAILABLE',lat=17.375,lng=78.375,updated_at='2026-10-29T00:00:00Z',assigned_ride_id='')
