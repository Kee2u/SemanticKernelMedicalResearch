#Importing dependencies
import streamlit as st
import PyPDF2
import requests
from bs4 import BeautifulSoup
import semantic_kernel as sk
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
import asyncio
import pandas as pd
import json
from plugins.OrchestratorPlugin.Orchestrator import Orchestrator
from azure.identity import ClientSecretCredential
from azure.keyvault.secrets import SecretClient
from dotenv import load_dotenv
import os
import re
from io import BytesIO
import logging
import xml.etree.ElementTree as ET
import urllib.request


#=====================Setting up Logging ============================================================================
logging.basicConfig(filename='app.log', level=logging.INFO, 
                    format='%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
#=====================Demo Functions=========================================================================
def get_pmc_data(id=None, from_date=None, until=None, format=None, resumption_token=None):
    base_url = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"
    params = {}

    if id:
        params['id'] = id
    if from_date:
        params['from'] = from_date
    if until:
        params['until'] = until
    if format:
        params['format'] = format
    if resumption_token:
        params['resumptionToken'] = resumption_token

    response = requests.get(base_url, params=params)
    
    if response.status_code == 200:
        root = ET.fromstring(response.text)

        # Get response date
        response_date = root.find('responseDate').text
        print(f"Response Date: {response_date}")

        # Get request id
        request_id = root.find('request').attrib['id']
        print(f"Request ID: {request_id}")

        # Get record details
        for record in root.iter('record'):
            record_id = record.attrib['id']
            citation = record.attrib['citation']
            license = record.attrib['license']
            retracted = record.attrib['retracted']

            # Get link details
            for link in record.iter('link'):
                format = link.attrib['format']
                updated = link.attrib['updated']
                href = link.attrib['href']
        return href
    else:
        return None
    
def scrape_text_from_pdf_url(url):
    response = urllib.request.urlopen(url)
    file = BytesIO(response.read())
    reader = PyPDF2.PdfReader(file)
    text = ''
    for page in reader.pages:
        text += page.extract_text()
    return text
#=====================PDF Functions on url  =========================================================================


def scrape_pdf_text_url(url):
    # Check if the URL contains "/viewpdf.aspx"
        # Set a custom User-Agent header to make the request appear more like a regular browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        # Send a GET request to the PDF URL with custom headers and get the content
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for unsuccessful responses

        # Create a PDF file object from the content
        pdf_file =  PyPDF2.PdfReader(BytesIO(response.content))

        # Initialize a variable to store the extracted text
        text = ""
        for page in pdf_file.pages:
            text += page.extract_text()
        return text


#=====================PDF Functions on streamlit =========================================================================

def scrape_pdf_text(file):

        pdf_reader = PyPDF2.PdfReader(file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text


#=====================isPDF or Website=========================================================================
def is_pdf_or_website(url):
    # Send an HTTP GET request to the URL
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    # Send a GET request to the PDF URL with custom headers and get the content
    response = requests.get(url, headers=headers)

    # Check if the response status code indicates success (2xx)
    if response.status_code // 100 == 2:
        # Check the Content-Type header to see if it's a PDF
        content_type = response.headers.get('Content-Type', '').lower()
        if 'pdf' in content_type:
            # If it's a PDF, trigger the PDF scraping function
            return scrape_pdf_text_url(url)
        else:
            # If it's a website, trigger the webpage scraping function
            return scrape_text_without_tables_cision(url) + scrape_text_with_tables_cision(url)



#=====================factset name retrival (you need the ticker and stock exchange ) =========================================================================

def most_recent_ec(ids_var):
    time_series_endpoint = 'https://api.factset.com/formula-api/v1/time-series'

    request = {
        "data": {
            "ids": [f'"{ids_var}"'],
            "formulas": [
                "CS_PRESS_LINK_N(\"E\",0)",
                "CS_PRESS_LINK_N(\"E\",-1)",
                "PROPER_NAME"
            ]
        }
    }

    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}

    post = json.dumps(request)
    
    response = requests.post(url=time_series_endpoint, data=post, auth=authorization, headers=headers, verify=False)
    data_dict = json.loads(response.text)
    value = None
    for item in data_dict["data"]:
        if "result" in item and isinstance(item["result"], dict):
            formula = item.get("formula", "")
            values = item["result"].get("values", [])
            if values:
                cleaned_value = str(values[0]).replace("'", "").replace('"', '')  # Remove single and double quotes
                if 'CS_PRESS_LINK_N("E",0)' in formula:
                    latest_url = cleaned_value
                elif 'CS_PRESS_LINK_N("E",-1)' in formula:
                    previous_url = cleaned_value
    if latest_url is not None and previous_url is not None:
        return latest_url, previous_url
    else:
        return None
#=====================factset call detail retrival (you need the ticker and stock exchange ) =========================================================================
    
def call_details(ids_var):
    time_series_endpoint = 'https://api.factset.com/formula-api/v1/time-series'

    request = {
        "data": {
            "ids": [f'"{ids_var}"'],
            "formulas": [
                "CS_PRESS_LINK_N(\"E\",0)",
                "PROPER_NAME",
                "CS_PHONE_LIVE_N(\"\",0)",
                "CS_URL_LIVE_C(\"\",0,\"ASC\")",
                "CS_PASSWD_LIVE_R(\"\",0)",
                "CS_PHONE_LIVE_R(\"\",0)"
            ]
        }
    }

    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}

    post = json.dumps(request)
    
    response = requests.post(url=time_series_endpoint, data=post, auth=authorization, headers=headers, verify=False)
    logging.info("Response from FactSet API")
    logging.info(response.text)
    data_dict = json.loads(response.text)
    logging.info("Conversion to dict of response from FactSet API")
    logging.info(data_dict)
    
    value = None
    for item in data_dict["data"]:
        if "result" in item and isinstance(item["result"], dict):
            values = item["result"].get("values", [])
            if values:
                value = str(values[0]).replace("'", "").replace('"', '')  # Remove single and double quotes
                break  # We found a value, no need to continue checking
    
    if value is not None:
        return value
    else:
        return None

#=====================Webscraping Functions=========================================================================
#---------------------Yahoo Finance---------------------------------------------------------------------------------
def scrape_text_without_tables_yahoo(url):
    #URL = 'https://finance.yahoo.com/news/blackline-safety-reports-fiscal-second-111700272.html'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Extracting the main content
    content_paragraphs = soup.find('div', class_='caas-body').find_all('p')
    content = ' '.join([p.get_text() for p in content_paragraphs])
    return content


def scrape_text_with_tables_yahoo(url):
    #URL = 'https://finance.yahoo.com/news/blackline-safety-reports-fiscal-second-111700272.html'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Extracting tables
    tables = soup.find_all('table')
    table_data = []

    for table in tables:
        rows = table.find_all('tr')
        table_content = []
        for row in rows:
            cells = row.find_all(['td', 'th'])
            cell_data = [cell.get_text().strip() for cell in cells]
            table_content.append(cell_data)
        table_data.append(table_content)

    # Convert to JSON
    table_json = json.dumps(table_data, indent=4)
    logging.info("Response from yahoo to scrape tables")
    logging.info(table_json)
    obj = json.loads(table_json)
    logging.info("Converstion of response from yahoo to scrape tables to json")
    logging.info(obj)        
            # Serialize the object back to a JSON string with no whitespace
    compact_json_string = json.dumps(obj, separators=(',', ':'))
    return compact_json_string
#---------------------CISION--------------------------------------------------------------------------------
def scrape_text_without_tables_cision(url):
    #URL = 'https://finance.yahoo.com/news/blackline-safety-reports-fiscal-second-111700272.html'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Extracting the main content
    content_paragraphs = soup.find_all(['p', 'li']) 
    content = ' '.join([p.get_text() for p in content_paragraphs])
    return content


def scrape_text_with_tables_cision(url):
    #URL = 'https://finance.yahoo.com/news/blackline-safety-reports-fiscal-second-111700272.html'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Extracting tables
    tables = soup.find_all('table')
    table_data = []

    for table in tables:
        rows = table.find_all('tr')
        table_content = []
        for row in rows:
            cells = row.find_all(['td', 'th'])
            cell_data = [cell.get_text().strip() for cell in cells]
            table_content.append(cell_data)
        table_data.append(table_content)

    # Convert to JSON
    table_json = json.dumps(table_data, indent=4)
    logging.info("Converstion of response from cision to scrape tables to json")
    logging.info(table_json)  
    obj = json.loads(table_json)
    logging.info("Converstion of response from cision to scrape tables to json")
    logging.info(obj)          
            # Serialize the object back to a JSON string with no whitespace
    compact_json_string = json.dumps(obj, separators=(',', ':'))
    cleaned_text = compact_json_string.replace('\u00a0', ' ')
    return cleaned_text


#=====================Retrieving code from Keyvault=====================================================================
load_dotenv()

# retrieve the secret value from key vault
deployment = os.environ['AZURE_OPENAI_DEPLOYMENT_NAME']
api_key  = os.environ['AZURE_OPENAI_API_KEY']
endpoint = os.environ['AZURE_OPENAI_ENDPOINT']

#Starting the Kernel
kernel = sk.Kernel()
kernel.add_text_completion_service("azureopenai", AzureChatCompletion(deployment, endpoint, api_key))

#=====================Chatbot variable initialization=================================================================
if "messages" not in st.session_state:
    st.session_state.messages = []

if "chatcontext" not in st.session_state:
    st.session_state.chatcontext = kernel.create_new_context()

pluginsDirectory = "./plugins"
pluginBT = kernel.import_semantic_skill_from_directory(pluginsDirectory, "SummarizeFlashcard");
my_context = kernel.create_new_context()
#======================Streamlit=======================================================================================

st.title("Medical Research Summarizer")
st.sidebar.title("Settings")

# Define a dictionary of industries and their respective metrics
industry_metrics = {

    "Oncology": ["Abstract", "Introduction", "Methodology", "Results", "Conclusion"] ,
    "Cardiology": ["Abstract","Introduction", "Study Design","Results", "Conclusion"] ,
    #"Consumer": ["Revenue", "Gross Profit", "Gross Margins (GM)", "Operating Profit", "Operating Margins (EBIT)", "EBIT", "Adj EBITDA", "Adj EBITDA margin", "Net Income", "EPS", "Adj EPS", "Operating Cash Flow", "Free Cash Flow", "Net Debt", "Tangible Book Value", "PEG Ratio", "Annual Recurring Revenue (ARR)", "Net Dollar Retention (NDR)"],
    # "Financials": ["Revenue", "Net Income", "EPS", "Adj EPS", "Cash EPS", "EPS growth", "Operating Cash Flow", "Free Cash Flow", "Net Debt", "PCL ratio", "NIM", "Non-Interest Income"],
    # "Industrials": ["Revenue", "Gross Profit", "Gross Margins (GM)", "Operating Profit", "Operating Margins", "EBIT", "Adj EBITDA", "Adj EBITDA margin", "Net Income", "EPS", "Adj EPS", "Operating Cash Flow", "Free Cash Flow", "Net Debt"],
    # "Real Estate": ["Revenue", "Operating Profit", "Operating Margins", "EBITDA", "Net Income", "Adjusted Funds from Operations (AFFO)", "Funds from Operations (FFO)", "AFFO"],
    # "Cannabis": ["Revenue", "Gross Profit", "Gross Margins (GM)", "Operating Profit", "Operating Margins", "Adj EBITDA", "Adj EBITDA margin", "Net Income", "EPS", "Adj EPS", "Operating Cash Flow", "Free Cash Flow", "Net Debt"],
    # "Mining": ["Revenue", "Production", "Cash Cost", "All in Sustaining cost (AISC)", "Operating Profit", "Operating Margins (EBIT)", "EBITDA", "CapEx (Capital Expenditures)", "Net Income", "EPS", "Adj EPS", "Operating Cash Flow (OCF)", "Free Cash Flow (FCF)", "Cash flow per share (CFPS)", "Net Debt"],
    # "Energy": ["Revenue", "Production (BOE/d)", "Operating Profit (EBIT)", "Operating Margins (EBIT)", "EBITDA Margin (%)", "CapEx (Capital Expenditures)", "Net Income", "EPS", "Adj EPS", "Operating Cash Flow", "Free Cash Flow", "Cash flow per share", "Net Debt"],
    # "AllMetrics": ["Revenue", "Gross Profit", "Gross Margins (GM)", "Operating Profit", "Operating Margins (EBIT)", "EBIT", "Adj EBITDA", "Adj EBITDA margin", "Net Income", "EPS", "Adj EPS", "Operating Cash Flow", "Free Cash Flow", "Net Debt", "Tangible Book Value", "PEG Ratio", "Annual Recurring Revenue (ARR)", "Net Dollar Retention (NDR)", "Cash EPS", "EPS growth", "PCL ratio", "NIM", "Non-Interest Income", "Production", "Cash Cost", "All in Sustaining Cost (AISC)", "EBITDA", "CapEx (Capital Expenditures)", "EBITDA Margin (%)", "Cash flow per share (CFPS)", "Production (BOE/d)"]

}




# Let users select an industry
selected_industry = st.sidebar.selectbox("Select Field of Medicine", list(industry_metrics.keys()))

# Transforming the metric list from the frontend to a format that can be passed as a variable to the orchestrator
st.sidebar.header("Select Metrics")
metrics_selected = {}
for metric in industry_metrics[selected_industry]:
    metrics_selected[metric] = st.sidebar.checkbox(metric, value=True)
selected_metrics_list = [re.sub(r'[^a-zA-Z0-9]', '', key) for key, value in metrics_selected.items() if value]
metricstring = ','.join(selected_metrics_list)




genre = st.sidebar.radio(
        "Where is your Research Paper?",
    ["Research Database", "URL", "PDF", "User Input"])
file = None  # Initialize file as None

# Display the selected emoji + save in context var 
slider_value = st.sidebar.slider("Slide to choose your sentiment:", 1, 5, value=3)

# Define emojis for bear and bull
emoji_mapping = {
    1: "😖 Very Negative",  # Bear emoji
    2: "😔 Negative",  # Another bear emoji
    3: "😐 Neutral Tone",  # Neutral emoji
    4: "😊 Positive",  # Bull emoji
    5: "😁 Very Positive"   # Another bull emoji
} 

def extract_text_without_specific_emojis(s):
    # Remove specified emoji characters
    emoji_pattern = re.compile(r"[\😖\😔\😐\😊\😁]")
    
    return emoji_pattern.sub(r'', s).strip()



#Display the selected emoji + save in context var 
variables = sk.ContextVariables()
selected_emoji = emoji_mapping[slider_value]
variables["options"] = selected_emoji
st.sidebar.write(f"Selected Sentiment: {selected_emoji}")

selected_text = extract_text_without_specific_emojis(selected_emoji)

if genre == 'Research Database':
    PMC = st.text_input('Enter PMC id of the Research Paper')
    run = st.button('go')
    # Display chat messages from history on app rerun

if genre == 'Research Database'  and run :
    website =  get_pmc_data(PMC) 
    if website is not None:
        st.chat_message("user").markdown( "Here is a link to the research article pdf: " + website)
        st.session_state.messages.append({"role": "user", "content": website})    
        text_URL = scrape_text_from_pdf_url(website)
        orchestrator_plugin = kernel.import_skill(Orchestrator(kernel), skill_name="OrchestratorPlugin")
        
        variables = sk.ContextVariables()
        variables["article"] = text_URL
        variables["metrics"] = metricstring
        variables["tone"] = selected_text


        # Run the Multiply function with the context.
        result = asyncio.run(kernel.run_async(
            orchestrator_plugin["RouteRequest"],
            input_vars=variables,
        ))
        result_str = str(result)
        result_str = result_str.replace('$', '&#36;')
        response = f"{result_str}"  
        response = response
        
        #st.session_state.messages.append({"role": "assistant", "content": variables_for_context_str}) #proxy for future table 
        #session_state.messages.append({"role": "assistant", "content": valuationmetricstring})

        st.chat_message("assistant").markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.session_state.chatcontext['original'] =  text_URL
        st.session_state.chatcontext['summary'] = response
    else:
        print("Press Release not found - Please try another ticker(add - region if needed)")  # Print a message if the website is not found
        st.chat_message("user").markdown("Press Release not found - Please try another ticker")

if genre == 'PDF':
    stock = st.text_input('Enter Stock Ticker - Stock Market (Eg. CF-CA)')
    targetprice = st.text_input('Enter Target Price (Eg. $25.00)')
    pdf_up = st.file_uploader("Upload a PDF file of the latest press release", type="pdf")
    previous_pdf_up = st.file_uploader("Upload a PDF file of the previous press release (optional)", type="pdf")
    context = st.text_input("Do you have any prepared commentary? Enter it here")

    run = st.button('go')
    
if genre == 'PDF'  and run:
    st.chat_message("user").markdown("The PDF you uploaded was called: " + pdf_up.name)
    st.session_state.messages.append({"role": "user", "content": file})
    text_URL = scrape_pdf_text(pdf_up)
    previous_text_URL = scrape_pdf_text(pdf_up)
    orchestrator_plugin = kernel.import_skill(Orchestrator(kernel), skill_name="OrchestratorPlugin")

    variables = sk.ContextVariables()
    variables["article"] = text_URL
    variables["previousarticle"] = previous_text_URL
    variables["metrics"] = metricstring
    variables["Valuationmetrics"] = valuationmetricstring
    variables["tone"] = selected_text
    variables["stock"] = stock
    variables["targetprice"] = targetprice
    variables["metric_to_identifier"] = json.dumps(metric_to_identifier)
    variables["valuation_metric_to_identifier"] = json.dumps(valuation_metric_to_identifier)
    variables["context"] = context
    

    # Run the Multiply function with the context.
    result = asyncio.run(kernel.run_async(
        orchestrator_plugin["RouteRequest"],
        input_vars=variables,
    ))
    result_str = str(result)
    result_str = result_str.replace('$', '&#36;')
    response = f"{result_str}"  
    response = (f"Your Factsheet: \n\n {response}")
    st.chat_message("assistant").markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.session_state.chatcontext['original'] =  text_URL
    st.session_state.chatcontext['summary'] = response


if genre == 'URL':
    stock = st.text_input('Enter Stock Ticker - Stock Market ')
    targetprice = st.text_input('Enter Target Price (Eg. $25.00)')
    source = st.selectbox('Choose the source', ['Yahoo', 'Cision','Other'])  # Dropdown to choose source
    file = st.text_input('Enter URL for latest Press Release Document')
    previous_file = st.text_input('Enter URL for previous Press Release Document (optional)')
    context = st.text_input("Do you have any prepared commentary? Enter it here")

    #stock = st.sidebar.text_input('Enter Stock Ticker')
    run = st.button('go')

if genre == 'URL'  and run :
    st.chat_message("user").markdown(file)
    st.session_state.messages.append({"role": "user", "content": file})
    if source == 'Yahoo':
        text_URL = scrape_text_without_tables_yahoo(file) + scrape_text_with_tables_yahoo(file)
        previous_text_URL = scrape_text_without_tables_yahoo(previous_file) + scrape_text_with_tables_yahoo(previous_file)
    elif source == 'Cision':
        text_URL = scrape_text_without_tables_cision(file) + scrape_text_with_tables_cision(file)
        previous_text_URL = scrape_text_without_tables_cision(previous_file) + scrape_text_with_tables_cision(previous_file)
    elif source == 'Other':
        text_URL = is_pdf_or_website(file)
        previous_text_URL = is_pdf_or_website(previous_file)

    orchestrator_plugin = kernel.import_skill(Orchestrator(kernel), skill_name="OrchestratorPlugin")

    variables = sk.ContextVariables()
    variables["article"] = text_URL
    variables["previousarticle"] = previous_text_URL
    variables["metrics"] = metricstring
    variables["Valuationmetrics"] = valuationmetricstring
    variables["tone"] = selected_text
    variables["stock"] = stock
    variables["targetprice"] = targetprice
    variables["metric_to_identifier"] = json.dumps(metric_to_identifier)
    variables["valuation_metric_to_identifier"] = json.dumps(valuation_metric_to_identifier)
    variables["context"] = context


    # Run the Multiply function with the context.
    result = asyncio.run(kernel.run_async(
        orchestrator_plugin["RouteRequest"],
        input_vars=variables,
    ))
    # Clean the content
    result_str = str(result)
    result_str = result_str.replace('$', '&#36;')
    response = f"Your Factsheet: \n\n {result_str}"  
    st.chat_message("assistant").markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.session_state.chatcontext['original'] =  text_URL
    st.session_state.chatcontext['summary'] = response


if genre == "User Input":
    stock = st.text_input('Enter Stock Ticker - Stock Market ')
    targetprice = st.text_input('Enter Target Price (Eg. $25.00)')
    user_query = st.text_input("Enter Latest Press Release Document Text Here")
    previous_user_query = st.text_input("Enter Previous Press Release Document Text Here (optional)")
    context = st.text_input("Do you have any prepared commentary? Enter it here")

    run = st.button("Go")
if genre == "User Input" and run :    
    #summary_result = asyncio.run(kernel.run_async(summary_function, input_str=user_query))
    #st.write(f"OpenAI Says\n\n {summary_result}")

    st.chat_message("user").markdown("Text Entered")
    st.session_state.messages.append({"role": "user", "content": file})

    orchestrator_plugin = kernel.import_skill(Orchestrator(kernel), skill_name="OrchestratorPlugin")

    variables = sk.ContextVariables()
    variables["article"] = user_query
    variables["previousarticle"] = previous_user_query
    variables["metrics"] = metricstring
    variables["Valuationmetrics"] = valuationmetricstring
    variables["tone"] = selected_text
    variables["stock"] = stock
    variables["targetprice"] = targetprice
    variables["metric_to_identifier"] = json.dumps(metric_to_identifier)
    variables["valuation_metric_to_identifier"] = json.dumps(valuation_metric_to_identifier)
    variables["context"] = context

    # Run the Multiply function with the context.
    result = asyncio.run(kernel.run_async(
        orchestrator_plugin["RouteRequest"],
        input_vars=variables,
    ))
    result_str = str(result)
    result_str = result_str.replace('$', '&#36;')
    response = f"Your Factsheet: \n\n {result_str}"  
    st.chat_message("assistant").markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.session_state.chatcontext['original'] =  text_URL
    st.session_state.chatcontext['summary'] = response

#-------------------Chat Portion ---------------------------------

if prompts := st.chat_input("Enter text here", key="factset"):
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    st.session_state.messages.append({"role": "user", "content": prompts})
    with st.chat_message("user"):
        st.markdown(prompts)
        st.session_state.chatcontext['user_input'] = prompts
    with st.chat_message("assistant"):    # Add assistant response to chat history
        full_response = asyncio.run(kernel.run_async(pluginBT["chat"], input_context=st.session_state.chatcontext))
        full_response = str(full_response)
        full_response = full_response.replace('$', '&#36;')
        st.markdown(full_response)
    st.session_state.messages.append({"role": "assistant", "content": full_response})
    st.session_state.chatcontext['summary'] += f"\nUser: {prompts}\n {full_response}\n"
