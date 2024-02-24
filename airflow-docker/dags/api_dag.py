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
import csv

def extract_csv_data():
    csv_path_file = './dags/record_italia.csv'
    csv_data = pd.read_csv(csv_path_file)
    print(csv_data.head)
    return csv_data

def transform_data(task_instance, ti):
     extracted_data = task_instance.xcom_pull(task_ids='extract_api_task')
     extracted_csv = ti.xcom_pull(task_ids='extract_csv_data_task')
     if extracted_data :
          transformed_api = [{'idMezzo': item['idMezzo']} for item in extracted_data]
          print(transformed_api)
          df_csv = pd.DataFrame(extracted_csv)
          print(df_csv)
          selected_csv = df_csv['Mezzo']
          print(selected_csv)
          df_api = pd.DataFrame(transformed_api)
          print(df_api)
          df_api_column = df_api['idMezzo'].rename('Mezzo')  # Rinomina la colonna per renderla compatibile
          # Concatena i due DataFrame lungo la colonna 'Mezzo'
          merged_data = pd.concat([selected_csv, df_api_column], ignore_index=True)
          #merged_data = pd.DataFrame({'Mezzo': selected_csv, 'idMezzo': df_api['idMezzo']})
          print(merged_data)
          dtypes = {'Mezzo': VARCHAR}
          db = create_engine("postgresql://flnjdqme:gQeyQIGRJTOtzrwmqa78m7YqeBfeiWOz@dumbo.db.elephantsql.com/flnjdqme")
          merged_data.to_sql('automezzo', db, if_exists='replace', dtype=dtypes)

default_args = {
     'owner': 'airflow',
     'start_date': datetime(2023, 1, 8)
}

with DAG('api_dag',
     default_args=default_args,
     schedule="@daily",
     catchup=False) as dag:

     extract_api_task = SimpleHttpOperator(
     task_id='extract_api_task',
     http_conn_id='first_conn',
     endpoint='/owner/posizione/flotta/13127',
     method='POST',
     headers={
        'accept': 'application/json',
        'secret': 'EtyoDBgNKSWMfKiQXeGioRP7L',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRF-TOKEN': 'EtyoDBgNKSWMfKiQXeGioRP7L', 
     },
     log_response=True,
     response_filter=lambda response: json.loads(response.text) if response.text else None,
     )
     extract_csv_data_task = PythonOperator(
        task_id='extract_csv_data_task',
        python_callable=extract_csv_data,
        provide_context=True,
    )
     transform_load_data_task = PythonOperator(
          task_id='transform_load_data_task',
          python_callable=transform_data,
          provide_context=True
     )
     extract_api_task >> extract_csv_data_task >> transform_load_data_task
     
