import airflow
import airflow.settings
import logging
import json
import time
import re
import redis

from airflow.contrib.kubernetes.volume_mount import VolumeMount
from airflow.contrib.kubernetes.volume import Volume
from airflow.contrib.kubernetes.secret import Secret
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator
from airflow.contrib.sensors.redis_key_sensor import RedisKeySensor
from airflow.contrib.operators.kubernetes_pod_operator import KubernetesPodOperator
from airflow.operators.dummy_operator import DummyOperator
from airflow.models import DAG, Variable, Connection

from datetime import datetime, timedelta


# FIXME: How to inject a new File URIs?  Dynamically create these DAG scripts?
INPUT_FILE = Variable.get('vlass_input_file_name')
NOISE_FILE = Variable.get('vlass_noise_file_name')
X509_CERT_STRING = Variable.get('vlass_cert')

file_pattern = re.compile('VLASS1\.(.*)-.*', re.IGNORECASE)
file_pattern_match = file_pattern.match(INPUT_FILE)
PARENT_DAG_NAME = 'vlass_dag_{}'.format(file_pattern_match.group(1).replace('+', '_').replace('/', '__'))

config = {'working_directory': '/root/airflow',
          'resource_id': 'ivo://cadc.nrc.ca/sc2repo',
          'use_local_files': False,
          'logging_level': 'DEBUG',
          'task_types': 'TaskType.INGEST'}

args={
    'start_date': datetime.utcnow(),
    'owner': 'airflow',
}

dag = DAG(
    dag_id='vlass_execute',
    default_args=args,
    schedule_interval=None)

sensor = RedisKeySensor(
    task_id='check_task',
    redis_conn_id='redis_default',
    dag=dag,
    key='test_key')

start_task = DummyOperator(task_id='start_task', dag=dag)
end_task = DummyOperator(task_id='end_task', dag=dag)


def get_file_names():
    redis_conn = redis.StrictRedis()
    results = redis_conn.get('test_key')
    if results is not None:
        file_name_list = results.decode('utf-8').split()[1:]
        return file_name_list
    else:
        return []


conn = Connection('test_netrc')

def get_caom_command(file_name, count):
    return KubernetesPodOperator(
                namespace='default',
                task_id='vlass-transform-{}'.format(count),
                image='bucket.canfar.net/vlass2caom2',
                in_cluster=True,
                get_logs=True,
                cmds=['vlass_run_single'],
                arguments=[file_name, conn.extra],
                name='airflow-vlass-transform-pod',
                dag=dag)


counter = 0
for ii in get_file_names():
    x = get_caom_command(ii, counter)
    counter += 1
    start_task >> x >> end_task
