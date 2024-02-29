import requests
import json
from datetime import datetime, timedelta
import boto3
import os
from dotenv import load_dotenv
import yaml 

load_dotenv()

#Git-Hub access token
TOKEN = os.getenv("GIT_HUB_TOKEN")

#Project node ID
PROJECT_NODE_ID = os.getenv("PROJECT_NODE_ID")

def get_current_iteration_id():

    query = f'''
    query {{
      node(id:"{PROJECT_NODE_ID}") {{
        ... on ProjectV2 {{
          fields(first: 20) {{
            nodes {{
              ... on ProjectV2IterationField {{
                id
                name
                configuration {{
                  iterations {{
                    startDate
                    id
                  }}
                }}
              }}
            }}
          }}
        }}
      }}
    }}
    '''

    headers = {
        'Authorization': f'Bearer {TOKEN}',
        'Content-Type': 'application/json',
    }

    payload = {'query': query}

    try:
     
        response = requests.post('https://api.github.com/graphql', headers=headers, json=payload)
        response.raise_for_status()  # Raise an exception for HTTP errors
        data = response.json()

        print("Raw GraphQL response:")
        print(json.dumps(data, indent=2))

        iterations = data['data']['node']['fields']['nodes']

        current_date = datetime.now()

        # Find the current iteration
        for iteration in iterations:
            if 'configuration' in iteration and 'iterations' in iteration['configuration']:
                for current_iteration in iteration['configuration']['iterations']:
                    start_date = datetime.strptime(current_iteration['startDate'], "%Y-%m-%d")
                    
                    # Calculate the end date (2 weeks after the start date)
                    end_date = start_date + timedelta(weeks=2)

                    # Check if the current date is within the iteration
                    if start_date <= current_date <= end_date:
                        print(current_iteration['id'])
                        return current_iteration['id']
                        
    except requests.RequestException as e:
        print(f"Error making GraphQL request: {e}")
    except KeyError as e:
        print(f"Error extracting data from GraphQL response: {e}")

    return None

def run_query():
    try:
        query = '''
        query {
          node(id:"'''+PROJECT_NODE_ID+'''") {
            ... on ProjectV2 {
              items(last: 100) {
                nodes {
                  id
                  fieldValues(first: 8) {
                    nodes {
                      ... on ProjectV2ItemFieldTextValue {
                        text
                        field {
                          ... on ProjectV2FieldCommon {
                            name
                          }
                        }
                      }
                      ... on ProjectV2ItemFieldDateValue {
                        date
                        field {
                          ... on ProjectV2FieldCommon {
                            name
                          }
                        }
                      }
                      ... on ProjectV2ItemFieldSingleSelectValue {
                        name
                        field {
                          ... on ProjectV2FieldCommon {
                            name
                          }
                        }
                      }
                      ... on ProjectV2ItemFieldIterationValue {
                        iterationId
                        field {
                          ... on ProjectV2FieldCommon {
                            name
                          }
                        }
                      }
                    }
                  }
                  content {
                    ... on Issue {
                      id
                      title
                      state
                      assignees(first: 10) {
                        nodes {
                          login
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        '''
        
        headers = {
            'Authorization': f'Bearer {TOKEN}',
            'Content-Type': 'application/json',
        }

        payload = {
            'query': query,
        }


        response = requests.post('https://api.github.com/graphql', headers=headers, json=payload)
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Print raw response for debugging
        print("Raw GraphQL response:")
        print(response.text)

        # Parse the JSON response
        return json.loads(response.text)
    except requests.RequestException as e:
        print(f"Error making GraphQL request: {e}")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")

    return None

def get_field_value(item, field_name):
    field_values = item.get('fieldValues', {}).get('nodes', [])

    for field in field_values:
        field_id = field.get('field', {}).get('name', '')
        if field_id == field_name:
            if 'text' in field:
                return field['text']
            elif 'name' in field:
                return field['name']
            elif 'iterationId' in field:
                return field['iterationId']

    return ''


def convert_to_json(tasks_by_assignee):
    # Get the current date in the format YYYY-MM-DD
    current_date = datetime.now().strftime("%Y-%m-%d")

    # Create a dictionary with the desired structure
    result_dict = {
        "date": current_date,
        "assignees_task_progress": [{"assignee": assignee, "tasks": {
            "todo": [{"title": task} for task in tasks["todo"]],
            "in-progress": [{"title": task} for task in tasks["in-progress"]],
            "Under-Review": [{"title": task} for task in tasks["Under-Review"]]
        }} for assignee, tasks in tasks_by_assignee.items()]
    }

    # Convert the dictionary to JSON string
    json_data = json.dumps(result_dict, indent=2)

    return json_data

def create_iteration_data(project_data, current_iterationID):
    iteration_data = {}

    try:
        nodes = project_data.get('data', {}).get('node', {}).get('items', {}).get('nodes', [])

        if not nodes:
            print("No nodes found in the YAML data.")
            return iteration_data

        for node in nodes:
            content = node.get('content', {})
            assignees = content.get('assignees', {}).get('nodes', [])

            if assignees:
                assignee = assignees[0]['login']
                task_title = content.get('title', '')
                task_status = get_field_value(node, 'Status')
                task_iteration_id = get_field_value(node, 'DT24-')

                # Check if the task belongs to the current iteration
                if task_iteration_id == current_iterationID:
                    print(f"Assignee: {assignee}, Title: {task_title}, Status: {task_status}, Iteration ID: {task_iteration_id}")

                    if assignee not in iteration_data:
                        iteration_data[assignee] = {'todo': [], 'in-progress': [], 'Under-Review': []}

                    if task_status == 'Spring Todo':
                        iteration_data[assignee]['todo'].append({'title': task_title, 'iteration_id': task_iteration_id})
                    elif task_status == 'In Progress':
                        iteration_data[assignee]['in-progress'].append({'title': task_title, 'iteration_id': task_iteration_id})
                    elif task_status == 'Under Review':
                        iteration_data[assignee]['Under-Review'].append({'title': task_title, 'iteration_id': task_iteration_id})

        print("Iteration Data:", iteration_data)
    except KeyError as e:
        print(f"Error accessing data in YAML data: {e}")

    return iteration_data

def print_iteration_data(result):
    for assignee, tasks in result.items():
        print(f"{assignee}:")

        print("Spring Todo:")
        for task in tasks['todo']:
            print(f"  - {task['title']} (Iteration ID: {task['iteration_id']})")

        print("\nIn Progress:")
        for task in tasks['in-progress']:
            print(f"  - {task['title']} (Iteration ID: {task['iteration_id']})")

        print("\nUnder Review:")
        for task in tasks['Under-Review']:
            print(f"  - {task['title']} (Iteration ID: {task['iteration_id']})")

        print("\n" + "-"*20 + "\n")

def load_assignee_emails():
    with open('AssigneesEmail.yaml', 'r') as file:
        assignee_emails = yaml.safe_load(file)
    return assignee_emails

def send_email(assignee_name, tasks_progress, date):
    
    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    region_name = os.getenv("AWS_REGION")
    
    #loading email from yaml files
    assignee_emails = load_assignee_emails()
    
    #getting sender's emial froomo yaml
    sender_email = assignee_emails.get("SENDER_MAIL", '')
    #getting email from yaml 
    to_email = assignee_emails.get(assignee_name, '')

    subject = 'Task Progress Update(TEST)'

    # Generate email body
    body = f"Hello {assignee_name},\n\nHere is your task progress update for {date}:\n\n"

    for status, tasks_list in tasks_progress.items():
        body += f"{status.capitalize()}:\n"
        for task in tasks_list:
            title = task['title']['title']
            body += f"- {title}\n"
        body += "\n"

    ses_client = boto3.client('ses', aws_access_key_id=aws_access_key_id,
                              aws_secret_access_key=aws_secret_access_key,
                              region_name=region_name)
    try:
          response = ses_client.send_email(
            
              Source=sender_email,
              Destination={
                  'ToAddresses': [to_email],
              },
              Message={
                  'Subject': {
                      'Data': subject,
                  },
                  'Body': {
                      'Text': {
                          'Data': body,
                      },
                  },
              }
          )
          print(f"Email sent to {assignee_name} successfully. Message ID: {response}")
    except Exception as e:
        print(f"Error sending email to {assignee_name}: {str(e)}")


def main():
    # Run the GraphQL query
    project_data = run_query()

    if project_data:
        current_iterationID = get_current_iteration_id()

        if current_iterationID:
            result = create_iteration_data(project_data, current_iterationID)
            print_iteration_data(result)
            json_data_issues = convert_to_json(result)
            print(json_data_issues)
            data = json.loads(json_data_issues)
            date = data.get("date", "")

            #Iterate through assignees and send emails
            for assignee_progress in data.get("assignees_task_progress", []):
                assignee_name = assignee_progress.get("assignee", "")
                tasks_progress = assignee_progress.get("tasks", {})
                
                if assignee_name and tasks_progress:
                    send_email(assignee_name, tasks_progress, date)
                else:
                    print(f"Error: Unable to send email for {assignee_name}.")
        else:
            print("No active iteration found.")
    else:
        print("Error in fetching project data.")

if __name__ == "__main__":
    main()
