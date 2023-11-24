import json
import streamlit as st
import semantic_kernel as sk
from semantic_kernel import  Kernel
from semantic_kernel.skill_definition import (
    sk_function,
    sk_function_context_parameter,
)
import logging
from semantic_kernel.orchestration.sk_context import SKContext
from plugins.FactsetPlugin.FactSetAPI import FactSetAPI
from plugins.FactsetPlugin.ValuationAPI import ValuationAPI
from dotenv import load_dotenv

class Orchestrator:
    def __init__(self, kernel: Kernel):
        self._kernel = kernel
       
    @sk_function(
        description="Routes the request to the appropriate function",
        name="RouteRequest",
    )
    @sk_function_context_parameter(
        name="article",
        description="The input article",
    )
    @sk_function_context_parameter(
        name="metrics",
        description="The input list",
    )
    @sk_function_context_parameter(
        name="tone",
        description="The tone of the output",
    )
    async def route(self, context: SKContext) -> str:
        #Initializing semantic kernel functions and native functions
        pluginsDirectory = "./plugins"
        pluginBT = self._kernel.import_semantic_skill_from_directory(pluginsDirectory, "SummarizeFlashcard")

        #Intializing to store result of summaries for each metric in a dict. Revenue: Summary of Revenue
        metric_summaries = {}

        #Converting string of metrics and valuation metrics to list. Note that semantic functions only work with string inputs and can only out strings
        metricstring = context["metrics"]
        metriclist = metricstring.split(',')
        #Creating new semantic context
        my_context = self._kernel.create_new_context()  
        
        #Initializing status bars
        metric_progress_text ="**Extracting Metrics..**"
        metric_success_text ="**Metrics Extracted :white_check_mark:**"
        summary_progress_text = "**Writing Summary..**"
        summary_success_text ="**Summary written :white_check_mark:**"

        metric_bar = st.progress(0, text=metric_progress_text)
  
        for metric in metriclist:
            #Removing whitespaces in the metriclist so they can match the variables defined in the semantic and native functions
            metric_name = metric.replace(" ", "")  # This assumes the folder names are like "Revenue", "GrossMargin" etc.
            #Adding metric names to semantic context to pass into the Aggregate Prompt semantic function
            my_context[metric_name] = metric_name 

        #Calling the Aggregated Prompt Semantic plugin to summarize the metrics 
        my_context['input'] = context["article"]
        aggregated_prompt_folder = "AggregatedPrompt"  
        #Updating status bar
        metric_bar.progress(50, text=metric_progress_text)
        result = await self._kernel.run_async(pluginBT[aggregated_prompt_folder], input_context=my_context)
        metric_summaries = json.loads(str(result))

        # Update the context with the summarized metrics from AggregatedPrompt
        for k, v in metric_summaries.items():
            my_context[k.replace(" ", "")] = k + ": " + v
        my_context['tone'] = context["tone"] 
        #Updating status bar
        metric_bar.progress(100, text=metric_success_text)

        #Initializing status bar
        summary_bar = st.progress(0, text=summary_progress_text)
        # Run the kernel with the updated context
        # Updating status bar
        summary_bar.progress(50, text=summary_progress_text)
        summarize_result = await self._kernel.run_async(pluginBT["Summarize"], input_context=my_context)
        summarize_str = str(summarize_result) 
        # Updating status bar
        summary_bar.progress(100, text=summary_success_text)
           
        #Making all status bars disappear
        metric_bar.empty()
        summary_bar.empty()
        return summarize_str

