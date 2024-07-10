import requests

# URL of your Flask server
url = "http://127.0.0.1:5000/rewrite_description"  # Adjust if your server is running on a different port

# Placeholder text for testing
placeholder_text = "The problem is that those 160 mg rows are referred in the content plan, as it is stated on the Error page. I see that you inactivated them, but in this case you should have deleted the content plan parts before locking and publishing it. As the CP is already locked and published there is nothing we can do, inactivate the rows to show that they were not relevant."

# Data to be sent in the POST request
data = {
    "description": placeholder_text
}

try:
    # Send POST request
    response = requests.post(url, data=data)
    
    # Check if the request was successful
    if response.status_code == 200:
        result = response.json()
        if result["status"] == "success":
            print("Rewritten description:")
            print(result["rewritten_description"])
        else:
            print("Error:", result["message"])
    else:
        print(f"Error: Received status code {response.status_code}")
        print("Response content:", response.text)

except requests.RequestException as e:
    print(f"An error occurred while making the request: {e}")
