from datetime import datetime
import logging
from airflow import DAG
from airflow.providers.http.sensors.http import HttpSensor
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
import pandas as pd
from sqlalchemy import create_engine, VARCHAR
import json

def transform_data(task_instance):
     extracted_data= task_instance.xcom_pull(task_ids='extract_data')
     if extracted_data:
          transformed_data = [{'id': item['idServizio'], 'telaio': item['telaio']} for item in extracted_data]
          df_data = pd.DataFrame(transformed_data)
          dtypes = {'id': VARCHAR, 'telaio': VARCHAR}
          db = create_engine("postgresql://flnjdqme:gQeyQIGRJTOtzrwmqa78m7YqeBfeiWOz@dumbo.db.elephantsql.com/flnjdqme")
          df_data.to_sql('automezzo', db, if_exists='replace', dtype=dtypes)


def extract_id(task_instance):
     trans = task_instance.xcom_pull(task_ids='transform_data_task')
     if trans:
          first_dict = trans[0]
          id_value = first_dict.get('id')
          logging.info(f"Value extracted: {id_value}")
          return id_value
     else:
          return None
     
default_args = {
     'owner': 'airflow',
     'start_date': datetime(2023, 1, 8)
}

with DAG('api_dag',
     default_args=default_args,
     schedule="@daily",
     catchup=False) as dag:

     extract_data = SimpleHttpOperator(
     task_id='extract_data',
     http_conn_id='first_conn',
     endpoint='/owner/posizione/flotta/13127',
     method='POST',
     headers={
        'accept': 'application/json',
        'secret': '',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRF-TOKEN': '', 
     },
     log_response=True,
     response_filter=lambda response: json.loads(response.text) if response.text else None,
     )

     transform_load_data_task = PythonOperator(
          task_id='transform_data_task',
          python_callable=transform_data,
          provide_context=True
     )
     extract_data >> transform_load_data_task

