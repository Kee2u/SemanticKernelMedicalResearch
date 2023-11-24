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
class ValuationAPI:
    @sk_function(
        description="Calls the Factset API to get street valuation values",
        name="ValuationAPI",
        input_description="The stock ticker and the formula parameters",
    )
    @sk_function_context_parameter(
        name="ids_var",
        description="The stock ticker",
    )
    @sk_function_context_parameter(
        name="metrics",
        description="The Valuation Metric List",
    )
    @sk_function_context_parameter(
        name="timeperiod",
        description="The timeperiod for the API",
     )
    async def factset_api(self, context: SKContext) -> str:
        #Reading the stock ticker
        ids_var = context["ids_var"]

        #Reading the Valuation Metrics and Converting it to list
        metrics = context["metrics"]
        metriclist = metrics.split(',')

        #Reading the timeperiod
        timeperiod = context["timeperiod"]

        # Reading facset authorization from environment file
        USERNAME_SERIALNUMBER = os.environ['FACTSET_USER']
        API_KEY = os.environ['FACTSET_KEY']
        authorization = (USERNAME_SERIALNUMBER,API_KEY) 

        
        formulas = []   
        for metric in metriclist:
            formula = f"FE_VALUATION({metric},MEAN,{timeperiod},+1,NOW,,,'')"
            formulas.append(formula)

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
        #     for item in data_dict['data']:
        #         formula = item['formula']
        #         identifier = formula.split('(')[0]  # Get the identifier part of the formula
        #         if identifier in identifier_to_metric:
        #             variable_name = identifier_to_metric[identifier]
        #             value = round(item['result']['values'][latest_date_index],1)
        #             variables_for_context[variable_name] = value
        #     variables_for_context_str = json.dumps(variables_for_context)
        #     return variables_for_context_str

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
                                                                        