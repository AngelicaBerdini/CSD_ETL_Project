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
    csv1_path_file = './dags/record_italia.csv'
    csv2_path_file = './dags/report_can.csv'
    csv3_path_file = './dags/report20240224.csv'
    csv4_path_file = './dags/reportposition.csv'
    csv1_data = pd.read_csv(csv1_path_file)
    csv2_data = pd.read_csv(csv2_path_file)
    csv3_data = pd.read_csv(csv3_path_file, sep=';')
    csv4_data = pd.read_csv(csv4_path_file)
    return csv1_data, csv2_data, csv3_data, csv4_data

def convert_date_format(date_str, input_format, output_format):
    return datetime.strptime(date_str, input_format).strftime(output_format)

def transform_data(task_instance, ti):
     extracted_data = task_instance.xcom_pull(task_ids='extract_api_task')
     extracted_csv1, extracted_csv2, extracted_csv3, extracted_csv4 = ti.xcom_pull(task_ids='extract_csv_data_task')
     transformed_api = [{'idMezzo': item['idMezzo'], 'km_totali': item['km_totali']} for item in extracted_data]
     df_api = pd.DataFrame(transformed_api)
     df_api_transformed = df_api.rename(columns={'idMezzo': 'Mezzo', 'km_totali':'Km Totali (Km)'})
     df_csv1 = pd.DataFrame(extracted_csv1)
     df_csv1['Data'] = df_csv1['Data'].apply(
     lambda x: convert_date_format(x, '%d/%m/%Y', '%Y-%m-%d') if pd.notnull(x) else x
          )
     selected_csv1 = df_csv1.loc[:, ['Mezzo', 'Km Totali (Km)', 'Città','Data', 'Ora']].rename(columns={'Data' : 'Data (UTC+01:00)', 'Ora':'Ora (UTC+01:00)'})
     df_csv2 = pd.DataFrame(extracted_csv2)
     selected_csv2 = df_csv2.loc[:, ['Targa', 'Km (CAN)']].rename(columns={'Targa': 'Mezzo', 'Km (CAN)': 'Km Totali (Km)'})
     df_csv3 = pd.DataFrame(extracted_csv3)
     selected_csv3 = df_csv3.loc[:, ['Targa', 'km', 'Arrivo','Data (UTC+01:00)','Ora (UTC+01:00)']].rename(columns={'Targa': 'Mezzo', 'km': 'Km Totali (Km)','Arrivo':'Città'})
     df_csv4 = pd.DataFrame(extracted_csv4)
     df_csv4['Data (UTC+01:00) '] = df_csv4['Data (UTC+01:00) '].apply(
     lambda x: convert_date_format(x, '%d/%m/%Y', '%Y-%m-%d') if pd.notnull(x) else x
     )
     selected_csv4 = df_csv4.loc[:, ['Targa', 'km', 'Città','Data (UTC+01:00) ','Ora (UTC+01:00) ']].rename(columns={'Targa': 'Mezzo', 'km': 'Km Totali (Km)', 'Data (UTC+01:00) ': 'Data (UTC+01:00)', 'Ora (UTC+01:00) ': 'Ora (UTC+01:00)'})
     merged_data = pd.concat([selected_csv3, selected_csv4, selected_csv1, selected_csv2, df_api_transformed], ignore_index=True)
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
        'X-CSRF-TOKEN': '', 
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
     
