import json
import ast 
import os
import streamlit as st
import requests
import logging
from semantic_kernel import  Kernel
from semantic_kernel.skill_definition import sk_function, sk_function_context_parameter
from semantic_kernel.orchestration.sk_context import SKContext
from dotenv import load_dotenv
class FactSetAPI:
    @sk_function(
        description="Calls the Factset API to get street metric values",
        name="API",
        input_description="The stock ticker and the formula parameters",
    )
    @sk_function_context_parameter(
        name="ids_var",
        description="The stock ticker",
    )
    @sk_function_context_parameter(
        name="metrics",
        description="The Metric List",
    )
    @sk_function_context_parameter(
        name="metric_to_identifier",
        description="The mapping of the metrics to the formulas",
     )

    async def factset_api(self, context: SKContext) -> str:
        ids_var = context["ids_var"]

        metrics = context["metrics"]
        metriclist = metrics.split(',')

        # authorization_str = context["authorization"]
        # authorization = ast.literal_eval(authorization_str)
        USERNAME_SERIALNUMBER = os.environ['FACTSET_USER']
        API_KEY = os.environ['FACTSET_KEY']

        authorization = (USERNAME_SERIALNUMBER,API_KEY) #for factset 

        metric_to_identifier_str = context["metric_to_identifier"]
        logging.info("Printing metric to identifier mapping")
        logging.info(metric_to_identifier_str)
        metric_to_identifier = json.loads(metric_to_identifier_str)
        logging.info("Converstion of metric to identifier mapping to json")
        logging.info(metric_to_identifier)

        formulas = []
        for metric in metriclist:
            if metric in metric_to_identifier:
                formula = f'{metric_to_identifier[metric]}'
                formulas.append(formula)
                if f"{metric}cg" in metric_to_identifier:
                        cg_formula = metric_to_identifier[f"{metric}cg"]
                        formulas.append(cg_formula)
        
        logging.info("formula")
        logging.info(formulas)

        time_series_endpoint = 'https://api.factset.com/formula-api/v1/time-series'
        request = {
            "data": {
                "ids": [f'"{ids_var}"'],
                "formulas": formulas
            }
        }

        headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}

        post = json.dumps(request)
        response = requests.post(url=time_series_endpoint, data=post, auth=authorization, headers=headers, verify=False)
        logging.info("Output of formulas api")
        logging.info(response.text)
        data_dict = json.loads(response.text)
        logging.info("Conversion of output of formulas api to dict")
        logging.info(data_dict)
        # Reverse the mapping to go from identifier to metric name
        identifier_to_metric = {v: k.replace(" ", "") for k, v in metric_to_identifier.items()}

        # # Find the index of the latest date
        # latest_date_index = None
        # for item in data_dict['data']:
        #     dates = item['result']['dates']
        #     if dates:
        #         # Find the index of the latest date
        #         latest_date_index = dates.index(max(dates))

        variables_for_context = {}

        # # If a latest date was found, retrieve the corresponding values
        # if latest_date_index is not None:
        # for item in data_dict['data']:
#             formula = item['formula']
#             identifier = formula.split('(')[0]  # Get the identifier part of the formula
#             if identifier in identifier_to_metric:
#                 variable_name = identifier_to_metric[identifier]
#                 value = round(item['result']['values'][0])
#                 variables_for_context[variable_name] = value
#         variables_for_context_str = json.dumps(variables_for_context)
#         return variables_for_context_str
# 

        for item in data_dict['data']:
            formula = item['formula']
            metric = identifier_to_metric.get(formula, formula)  # If the formula is not found in the mapping, use the formula as is
            if isinstance(item['result'], dict) and 'values' in item['result']:
                value = item['result']['values'][0] if item['result']['values'] else 0
            else:
                value = item['result']  # Here, the result is a scalar value and not a dictionary
            variables_for_context[metric] = value
            variables_for_context_str = json.dumps(variables_for_context)
        return variables_for_context_str
    
        logging.info(variables_for_context_str)
        st.chat_message("assistant").markdown(variables_for_context_str)
        st.session_state.messages.append({"role": "assistant", "content": variables_for_context_str})
                                                                        