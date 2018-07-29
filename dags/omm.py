import airflow
import airflow.settings
import logging
import json
import time
import re

from airflow.contrib.kubernetes.volume_mount import VolumeMount
from airflow.contrib.kubernetes.volume import Volume
from airflow.operators.python_operator import PythonOperator
from airflow.operators.bash_operator import BashOperator
from airflow.contrib.operators.kubernetes_pod_operator import KubernetesPodOperator
from airflow.operators.dummy_operator import DummyOperator
from airflow.models import DAG, Variable

from datetime import datetime, timedelta
from urllib.parse import urlparse

# FIXME: How to inject a new File URI?  Dynamically create these DAG scripts?
INPUT_FILE = Variable.get('omm_input_file_uri')
parsed_url = urlparse(INPUT_FILE)
file_pattern = re.compile('ad:OMM/(.*)\.fits.gz', re.IGNORECASE)
file_pattern_match = file_pattern.match(INPUT_FILE)
PARENT_DAG_NAME = 'omm_dag_{}'.format(file_pattern_match.group(1).replace('+', '_').replace('/', '__'))

config = {'working_directory': '/root/airflow',
          'resource_id': 'ivo://cadc.nrc.ca/sc2repo',
          'use_local_files': False,
          'logging_level': 'DEBUG',
          'task_types': 'TaskType.INGEST'}
docker_image_tag = 'client5'

default_args = {
    'owner': 'airflow',
    'start_date': airflow.utils.dates.days_ago(1),
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 0,
    'retry_delay': timedelta(minutes=5),
    'provide_context': True
}

dags_volume_mount = VolumeMount('airflow-dags',
                                mount_path='/root/airflow/dags',
                                sub_path=None,
                                read_only=True)
dags_volume_config = {
    'persistentVolumeClaim':
        {
            'claimName': 'airflow-dags'
        }
}
dags_volume = Volume(name='airflow-dags', configs=dags_volume_config)

logs_volume_mount = VolumeMount('airflow-logs',
                                mount_path='/root/airflow/logs',
                                sub_path=None,
                                read_only=True)
logs_volume_config = {
    'persistentVolumeClaim':
        {
            'claimName': 'airflow-logs'
        }
}
logs_volume = Volume(name='airflow-logs', configs=logs_volume_config)

dag = DAG(dag_id='{}.{}'.format(PARENT_DAG_NAME, default_args['start_date'].strftime(
    "%Y-%m-%d_%H_%M_%S")), catchup=True, default_args=default_args, schedule_interval=None)

with dag:
    start_op = DummyOperator(task_id='omm_start_dag', dag=dag)

    science_file_op = KubernetesPodOperator(
                namespace='default',
                task_id='omm_transform_science_file',
                image='ubuntu:18.10',
                in_cluster=True,
                get_logs=True,
                cmds=['echo'],
                arguments=['science_file_{}'.format(INPUT_FILE)],
                volume_mounts=[dags_volume_mount, logs_volume_mount],
                volumes=[dags_volume, logs_volume],
                name='airflow-omm_science_file-pod',
                dag=dag)

    preview_op = KubernetesPodOperator(
                namespace='default',
                task_id='omm_transform_preview',
                image='ubuntu:18.10',
                in_cluster=True,
                get_logs=True,
                cmds=['echo'],
                arguments=['preview_{}'.format(INPUT_FILE)],
                volume_mounts=[dags_volume_mount, logs_volume_mount],
                volumes=[dags_volume, logs_volume],
                name='airflow-omm_preview-pod',
                dag=dag)

    thumbnail_op = KubernetesPodOperator(
                namespace='default',
                task_id='omm_transform_thumbnail',
                image='ubuntu:18.10',
                in_cluster=True,
                get_logs=True,
                cmds=['echo'],
                arguments=['thumbnail_{}'.format(INPUT_FILE)],
                volume_mounts=[dags_volume_mount, logs_volume_mount],
                volumes=[dags_volume, logs_volume],
                name='airflow-omm_thumbnail-pod',
                dag=dag)                

    complete_op = DummyOperator(task_id='omm_complete_dag', dag=dag)

    science_file_op.set_upstream(start_op)

    preview_op.set_upstream(science_file_op)
    thumbnail_op.set_upstream(science_file_op)

    preview_op.set_downstream(complete_op)
    thumbnail_op.set_downstream(complete_op)
