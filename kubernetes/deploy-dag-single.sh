#!/bin/bash
#
#  Licensed to the Apache Software Foundation (ASF) under one   *
#  or more contributor license agreements.  See the NOTICE file *
#  distributed with this work for additional information        *
#  regarding copyright ownership.  The ASF licenses this file   *
#  to you under the Apache License, Version 2.0 (the            *
#  "License"); you may not use this file except in compliance   *
#  with the License.  You may obtain a copy of the License at   *
#                                                               *
#    http://www.apache.org/licenses/LICENSE-2.0                 *
#                                                               *
#  Unless required by applicable law or agreed to in writing,   *
#  software distributed under the License is distributed on an  *
#  "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY       *
#  KIND, either express or implied.  See the License for the    *
#  specific language governing permissions and limitations      *
#  under the License.                                           *

INPUT_FILE=${1}

if [ "${INPUT_FILE}" == "" ];
then
  echo "No input file provided."
  echo "Usage: deploy-dag-single.sh my-dag-file.py"
  exit -1
else
  echo "Deploying ${INPUT_FILE}."
fi

AIRFLOW_POD=$(kubectl get pods | grep ^airflow | awk '{print $1}')

kubectl cp ${INPUT_FILE} ${AIRFLOW_POD}:/root/airflow/dags -c scheduler -v 6
