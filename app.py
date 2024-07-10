import os
import csv
import io
import logging
import requests
import json
import random
import string
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from requests_toolbelt.multipart.encoder import MultipartEncoder
from dotenv import load_dotenv
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from prompts import REWRITE_DESCRIPTION_PROMPT

# Initialize Flask app
app = Flask(__name__)

# Logging
logging.basicConfig(level=logging.DEBUG)
app.logger.setLevel(logging.DEBUG)
# Check if API key exists before logging
api_key = os.getenv('GOOGLE_API_KEY')
if api_key:
    app.logger.debug(f"API Key: {api_key[:5]}...") # Log first 5 chars for security
else:
    app.logger.warning("GOOGLE_API_KEY is not set in the environment variables")

# Load environment variables
load_dotenv()

# Load configuration
with open('config.json', encoding='utf-8') as config_file:
    config = json.load(config_file)
    
safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE"
    },
]
    
# Configure Gemini
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

# API configuration
api_info = config["api_info"]
vault_domain = api_info["vault_domain"]
api_version = api_info["api_version"]

# Construct API endpoints
auth_endpoint = f"{vault_domain}/api/{api_version}/auth"
loader_endpoint = f"{vault_domain}/api/{api_version}/services/loader/load"
file_staging_endpoint = f"{vault_domain}/api/{api_version}/services/file_staging/items"
object_endpoint = f"{vault_domain}/api/{api_version}/vobjects/user_task__v"

# List of assignees
ASSIGNEES = ["Bernadett Forró", "János Földvárszki", "Ildikó Nagy", "Károly Kürti"]

# Set up logging
log_stream = io.StringIO()
logging.basicConfig(stream=log_stream, level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Utility functions
def generate_task_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def authenticate():
    username = os.getenv("VAULT_USERNAME")
    password = os.getenv("VAULT_PASSWORD")
    
    logging.debug(f"Attempting to authenticate with username: {username}")
    
    if not username or not password:
        raise Exception("VAULT_USERNAME or VAULT_PASSWORD environment variables are not set")
    
    auth_data = {
        "username": username,
        "password": password
    }
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    response = requests.post(auth_endpoint, data=auth_data, headers=headers)
    logging.debug(f"Authentication response status code: {response.status_code}")
    logging.debug(f"Authentication response content: {response.text}")

    response_json = response.json()
    if response.status_code == 200 and response_json.get("responseStatus") == "SUCCESS":
        session_id = response_json.get("sessionId")
        if session_id:
            logging.debug("Authentication successful. Received session ID.")
            return session_id
        else:
            logging.error("Authentication response did not contain a session ID")
            raise Exception("Authentication response did not contain a session ID")
    else:
        error_message = response_json.get("responseMessage", "Unknown authentication error")
        logging.error(f"Authentication failed. Error: {error_message}")
        raise Exception(f"Authentication failed: {error_message}")

def upload_data_to_staging(csv_data, filename, session_id):
    headers = {
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Authorization": session_id,
        "Accept": "application/json",
        "X-VaultAPI-DescribeResponse": "true"
    }
    
    multipart_data = MultipartEncoder(
        fields={
            'file': (filename, csv_data.encode('utf-8'), 'text/csv; charset=utf-8'),
            'kind': 'file',
            'path': f'{config["vault_settings"]["upload_path"]}{filename}'
        }
    )
    
    headers['Content-Type'] = multipart_data.content_type
    
    logging.debug(f"Uploading file with headers: {headers}")
    response = requests.post(file_staging_endpoint, headers=headers, data=multipart_data)
    
    logging.debug(f"File upload response status code: {response.status_code}")
    logging.debug(f"File upload response content: {response.text}")
    
    if response.status_code == 200:
        response_json = response.json()
        if response_json.get("responseStatus") == "SUCCESS":
            logging.debug(f"File {filename} uploaded successfully.")
            return f"{config['vault_settings']['upload_path']}{filename}"
        else:
            raise Exception(f"Failed to upload file: {response_json}")
    else:
        raise Exception(f"Failed to upload file: {response.text}")

def create_loader_job(file_name, object_type, session_id):
    headers = {
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Authorization": session_id,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = [
        {
            "object_type": "vobjects__v",
            "object": object_type,
            "action": "create",
            "file": f"/{config['vault_settings']['upload_path']}{file_name}",
            "recordmigrationmode": True,
            "order": 1
        }
    ]
    logging.debug(f"Creating loader job with headers: {headers}")
    response = requests.post(loader_endpoint, headers=headers, data=json.dumps(payload))
    logging.debug(f"Loader job response status code: {response.status_code}")
    logging.debug(f"Loader job response content: {response.text}")
    if response.status_code == 200:
        response_json = response.json()
        if response_json.get("responseStatus") == "SUCCESS":
            logging.debug("Loader job created successfully.")
        else:
            raise Exception(f"Failed to create loader job: {response_json}")
    else:
        raise Exception(f"Failed to create loader job: {response.text}")

def get_object_id(session_id, task_name):
    logging.debug(f"Attempting to retrieve object ID for task name: {task_name}")
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Authorization": session_id,
        "Accept": "application/json"
    }
    
    logging.debug(f"Sending GET request to: {object_endpoint}")
    logging.debug(f"Headers: {headers}")
    
    try:
        response = requests.get(object_endpoint, headers=headers)
        
        logging.debug(f"Response status code: {response.status_code}")
        logging.debug(f"Response content: {response.text[:1000]}...")  # Log first 1000 characters of response
        
        response.raise_for_status()  # This will raise an HTTPError for bad responses (4xx or 5xx)
        
        data = response.json()
        if data.get("responseStatus") == "SUCCESS":
            records = data.get("data", [])
            logging.debug(f"Number of records received: {len(records)}")
            matching_records = [record for record in records if task_name.lower() in record.get("name__v", "").lower()]
            
            logging.debug(f"Number of matching records: {len(matching_records)}")
            
            if matching_records:
                results = []
                for record in matching_records:
                    results.append({
                        "id": record.get("id"),
                        "name": record.get("name__v")
                    })
                logging.debug(f"Matching records: {results}")
                return results
            else:
                logging.warning(f"No matching records found for task name: {task_name}")
        else:
            logging.error(f"API response status is not SUCCESS: {data.get('responseStatus')}")
    except requests.exceptions.RequestException as e:
        logging.error(f"An error occurred while making the API request: {str(e)}")
    except json.JSONDecodeError:
        logging.error("Failed to parse the API response as JSON")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {str(e)}")
    
    return []

# Routes
@app.route('/')
def index():
    return render_template('index.html', assignees=ASSIGNEES)

@app.route('/submit_task', methods=['POST'])
def submit_task():
    try:
        task_id = generate_task_id()
        original_name = request.form['name']
        name = f"TASK_ID: {task_id} - {original_name}"
        assigned_to = request.form['assignedTo']
        category = request.form['category']
        due_date = request.form['dueDate']
        description = request.form['description']
        
        logging.debug(f"Task ID: {task_id}, Name: {name}")
        
        csv_data = io.StringIO()
        csv_writer = csv.writer(csv_data)
        csv_writer.writerow(['name__v', 'assigned_to__v.name__v', 'category__c', 'due_date__v', 'description__v'])
        csv_writer.writerow([name, assigned_to, category, due_date, description])
        
        logging.debug(f"CSV data: {csv_data.getvalue()}")
        
        session_id = authenticate()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"task_{timestamp}.csv"
        
        logging.debug(f"Uploading data as file: {filename}")
        vault_file_path = upload_data_to_staging(csv_data.getvalue(), filename, session_id)
        
        logging.debug(f"Creating loader job for file: {filename}")
        create_loader_job(filename, config['vault_settings']['object_type'], session_id)
        
        log_contents = log_stream.getvalue()
        return jsonify({
            "status": "success",
            "message": "Task submitted successfully.",
            "taskId": task_id,
            "taskName": name,
            "log": log_contents
        })
    except Exception as e:
        logging.exception("An error occurred")
        log_contents = log_stream.getvalue()
        return jsonify({
            "status": "error",
            "message": str(e),
            "taskId": task_id if 'task_id' in locals() else None,
            "taskName": name if 'name' in locals() else None,
            "log": log_contents
        }), 500
    finally:
        log_stream.truncate(0)
        log_stream.seek(0)

@app.route('/check_status/<task_id>')
def check_status(task_id):
    try:
        session_id = authenticate()
        matching_records = get_object_id(session_id, f"TASK_ID: {task_id}")
        
        if matching_records:
            record = matching_records[0]
            message = f"Object ID: {record['id']}\nName: {record['name']}"
        else:
            message = f"Unable to retrieve record for Task ID: {task_id}. The record may still be processing or may not have been created successfully."
        
        return jsonify({"status": "success", "message": message})
    except Exception as e:
        logging.exception("An error occurred while checking status")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/get_object_id', methods=['POST'])
def retrieve_object_id():
    try:
        task_name = request.form['taskName']
        logging.info(f"Received request to retrieve object ID for task name: {task_name}")
        
        session_id = authenticate()
        logging.debug(f"Authentication successful. Session ID: {session_id[:10]}...")  # Log first 10 characters of session ID
        
        matching_records = get_object_id(session_id, task_name)
        
        if matching_records:
            message = "Matching records:\n"
            for record in matching_records:
                message += f"Object ID: {record['id']}, Name: {record['name']}\n"
            logging.info(f"Found matching records: {message}")
        else:
            message = f"No records found containing '{task_name}'. The record may not exist or there might be an issue with the retrieval process."
            logging.warning(message)
        
        log_contents = log_stream.getvalue()
        return jsonify({"status": "success", "message": message, "log": log_contents})
    except Exception as e:
        logging.exception("An error occurred while retrieving the object ID")
        log_contents = log_stream.getvalue()
        return jsonify({"status": "error", "message": str(e), "log": log_contents}), 500
    finally:
        log_stream.truncate(0)
        log_stream.seek(0)
        
@app.route('/rewrite_description', methods=['POST'])
def rewrite_description():
    try:
        description = request.form.get('description')
        if not description:
            return jsonify({"status": "error", "message": "No description provided"}), 400

        prompt = REWRITE_DESCRIPTION_PROMPT.format(description=description)

        response = model.generate_content(prompt, safety_settings=safety_settings)
        
        if response.prompt_feedback.block_reason:
            return jsonify({"status": "error", "message": f"Content blocked: {response.prompt_feedback.block_reason}"}), 400

        rewritten_description = response.text
        return jsonify({"status": "success", "rewritten_description": rewritten_description})

    except Exception as e:
        app.logger.error(f"An error occurred: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)