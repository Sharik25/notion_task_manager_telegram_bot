from flask import request
from flask import Response
import requests
import datetime
import re
import os
import json
import time

from flask import Flask

app = Flask(__name__)
TOKEN = "your_token" 
notion_secret_token = 'your_secret_token'
notion_database_id = "your_database_id"

# Store user states (for simplicity, using an in-memory dictionary)
user_states = {}

#NOTION FUNCTIONS START
def download_tasks_and_comments_from_db():
    token = notion_secret_token
    databaseId = notion_database_id
    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    readUrl = f"https://api.notion.com/v1/databases/{databaseId}/query"

    res = requests.request("POST", readUrl, headers=headers)
    data = res.json()

    final_list_with_tasks = []
    if(len(data['results']) != 0):
      for object_ in res.json()['results']:
        print(object_)
        task_id = object_['id']
        task_name = object_['properties']['Name']['title'][0]['text']['content']
        task_status = object_['properties']['Status']['status']['name']
        task_deadline = object_['properties']['Deadline']['date']['start']
        task_url = object_['url']
        final_list_with_tasks.append({"task_id":task_id, "task_name":task_name, "task_status":task_status, "task_deadline":task_deadline, "task_url":task_url})

        for item in final_list_with_tasks:
          taskId = item['task_url'].split('-')[-1]
          GetCommentsUrl = f"https://api.notion.com/v1/comments?block_id={taskId}"

          res = requests.request("GET", GetCommentsUrl, headers=headers)
          commentsData = res.json()

          comments_list = []
          has_more_flag = commentsData['has_more']
          if(has_more_flag == True):
            while has_more_flag != False:
              next_corsor = commentsData['next_cursor']
              GetCommentsUrl = f"https://api.notion.com/v1/comments?block_id={taskId}?start_cursor={next_corsor}"
              commentsData = requests.request("GET", GetCommentsUrl, headers=headers)
              next_corsor = commentsData['next_cursor']
              has_more_flag = commentsData['has_more']
              for comment in commentsData['results']:
                comments_list.append({"comment_user_id":comment["created_by"]["id"],"discussion_id":comment['discussion_id'], "parent_id":comment['parent']['page_id'], "comment_text":comment['rich_text'][0]['text']['content']})
          else:
            has_more_flag = False
            for comment in commentsData['results']:
                comments_list.append({"comment_user_id":comment["created_by"]["id"], "discussion_id":comment['discussion_id'], "parent_id":comment['parent']['page_id'], "comment_text":comment['rich_text'][0]['text']['content']})

          item['task_comments'] = comments_list

    return final_list_with_tasks

def add_comment(user_comment, discussion_id_from_state):
    token = notion_secret_token
    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    add_comment_url = 'https://api.notion.com/v1/comments'
    data = {
        "discussion_id":discussion_id_from_state,
        "rich_text": [
          {
            "text": {
              "content": user_comment
            }
          }
        ]
    }

    data_json = json.dumps(data)

    res = requests.request("POST", add_comment_url, headers = headers, data = data_json)
    AddNewComment = res.json()
    return f'Comment # {user_comment} # added succesfully'

def create_task(new_task_name):
    token = notion_secret_token
    databaseId = notion_database_id

    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    properties_for_new_task = {'Description': {'type': 'rich_text', 'rich_text': []},
     'Deadline': {'id': 'IM_Z',
      'type': 'date',
      'date': {'start': '2050-01-01', 'end': None, 'time_zone': None}},
     'Status': {
      'id':'Qbqg',
      'type': 'status',
      'status': {
       'name': 'Not started',
       'color': 'default'}},
     'Assign': {'type': 'people', 'people': []},
     'Name': {'id': 'title',
      'type': 'title',
      'title': [{'type': 'text',
        'text': {'content': new_task_name, 'link': None},
        'annotations': {'bold': False,
         'italic': False,
         'strikethrough': False,
         'underline': False,
         'code': False,
         'color': 'default'},
        'plain_text': new_task_name,
        'href': None}]}}

    create_url = "https://api.notion.com/v1/pages"
    payload = {"parent": {"database_id": databaseId}, "properties": properties_for_new_task}
    data_json = json.dumps(payload)

    res = requests.request("POST", create_url, headers=headers, data=data_json)
    data = res.json()
    return f"New task # {new_task_name} # created succesfully!"

def onboarding_function():
    response_text =  """
            How to Start Working in Notion:

            Open Notion on your device.
            Navigate to the workspace assigned to your team or project.
            Familiarize yourself with the layout and sections available.

            How to Open a Task in Notion:

            In your workspace, locate the 'Tasks' database or page.
            Click on the task you want to open. This will bring up the detailed view of the task.
            Review the task details, including the description, due date, and any attached files or comments.

            How to Change the Status of a Task in Notion:

            Open the task you want to update.
            Find the status property (usually a dropdown or select field).
            Change the status to the appropriate option (e.g., 'To Do', 'In Progress', 'Completed').

            How to Interact with Your Team in Notion:

            Assign Tasks: Assign tasks to specific team members by selecting their name from the assignee dropdown.
            Comments: Add comments to tasks to provide updates, ask questions, or share information. Mention team members using '@' followed by their name to notify them.
            Shared Pages: Collaborate on shared pages by editing content together in real-time. Use the 'Comments' feature to discuss specific sections.
            Team Spaces: Utilize team spaces to share resources, documents, and updates relevant to your project or department.

            Additional Tips for Managing Tasks in Notion:

            Use tags or labels to categorize tasks for better organization.
            Set due dates and reminders to ensure timely completion of tasks.
            Add notes to provide additional context or updates on the task.
        """
    return response_text

#NOTION FUNCTIONS END


#FLASK BOT FUNCTIONS START

def parse_message(message):
    print("message-->", message)
    chat_id = message['message']['chat']['id']
    try:
        media_group_id = message['message']['media_group_id']
    except:
        media_group_id = 'None'
    try:
        txt = message['message']['text']
    except:
        txt = 'None'
    return chat_id, txt, media_group_id


async def tel_send_message(chat_id, text):
    # url = 'https://api.telegram.org/bot5708399216:AAEsS-8QXWLzZbKgRcfK34PNwMLLF59mFug/sendMessage'
    url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
    payload = {
        'chat_id': chat_id,
        'text': text
    }

    r = requests.post(url, json=payload)
    return r

async def default_message_with_commands(chat_id):
    response_text_default = """
        Available commands:

        /onBoarding - Notion onboarding
        /CreateTask - Create new task
        /InProgress - Get tasks with "in progress" status
        /NotStarted - Get tasks with "not started" status
        """
    await tel_send_message(chat_id, response_text_default)
    return "Commands sent succesfully"


#FLASK BOT FUNCTIONS END


@app.route('/', methods=['GET', 'POST'])
async def index():

    msg = request.get_json()
    print(msg)
    chat_id = parse_message(msg)[0]
    text = parse_message(msg)[1]
    media_group_id = parse_message(msg)[2]


    if(text == '/start'):
        user_states[chat_id] = 'START'
        response_text = """
        The bot commands:
        /onBoarding - Notion onboarding
        /CreateTask - Create new task
        /InProgress - Get tasks with "in progress" status
        /NotStarted - Get tasks with "not started" status
        """
        await tel_send_message(chat_id, response_text)
        await tel_send_message(chat_id, user_states)

    elif(text == '/onBoarding'):
        user_states[chat_id] = 'INSIDE_ONBOARDING'
        await tel_send_message(chat_id, user_states)
        await tel_send_message(chat_id, onboarding_function())

        await default_message_with_commands(chat_id)

    elif(text == '/InProgress'):
        user_states[chat_id] = 'INSIDE_IN_PROGRESS'
        await tel_send_message(chat_id, user_states)
        tasks_and_comments = download_tasks_and_comments_from_db()
        task_name = ''
        for task in tasks_and_comments:
            full_task_description = ''
            full_task_description += "Name: " + task['task_name'] + '\n'
            task_name = task['task_name']
            full_task_description += "Status: " + task['task_status'] + '\n'
            full_task_description += "Deadline: " + task['task_deadline'] + '\n'
            full_task_description += "Link: " + task['task_url'] + '\n'

            comments_for_message = ''
            discussion_id = ''
            for comment_item in task['task_comments']:
                comments_for_message += comment_item['comment_text'] + '\n'
                discussion_id = comment_item['discussion_id']
            discussion_id_modified = discussion_id.replace("-", "")
            task_name_modified = task_name.replace(' ', '')
            if(task['task_status'] == 'In progress'):
                timedelta = datetime.datetime.strptime(task['task_deadline'], "%Y-%m-%d").date() - datetime.datetime.now().date()
                if(timedelta.days > 0):
                  full_task_description += f'Days to deadline: {timedelta.days}' + '\n\n'
                  full_task_description += "Comments:" + '\n'
                  full_task_description += comments_for_message + '\n\n'
                  full_task_description += '/AddComment_' + task_name_modified + '_' + discussion_id_modified
                  await tel_send_message(chat_id, full_task_description)
                else:
                  full_task_description += f'Deadline is overdue: {timedelta.days}' + '\n\n'
                  full_task_description += "Comments:" + '\n'
                  full_task_description += comments_for_message + '\n\n'
                  full_task_description += '/AddComment_' + task_name_modified + '_' + discussion_id_modified
                  await tel_send_message(chat_id, full_task_description)
            else:
                pass

        await default_message_with_commands(chat_id)

    elif(text == '/NotStarted'):
        user_states[chat_id] = 'INSIDE_NOT_STARTED'
        await tel_send_message(chat_id, user_states)
        tasks_and_comments = download_tasks_and_comments_from_db()

        task_name = ''
        for task in tasks_and_comments:
            full_task_description = ''
            full_task_description += "Name: " + task['task_name'] + '\n'
            task_name = task['task_name']
            full_task_description += "Status: " + task['task_status'] + '\n'
            full_task_description += "Deadline: " + task['task_deadline'] + '\n'
            full_task_description += "Link: " + task['task_url'] + '\n'

            comments_for_message = ''
            discussion_id = ''
            for comment_item in task['task_comments']:
                comments_for_message += comment_item['comment_text'] + '\n'
                discussion_id = comment_item['discussion_id']
            discussion_id_modified = discussion_id.replace("-", "")
            task_name_modified = task_name.replace(' ', '')
            if(task['task_status'] == 'Not started'):
                timedelta = datetime.datetime.strptime(task['task_deadline'], "%Y-%m-%d").date() - datetime.datetime.now().date()
                if(timedelta.days > 0):
                  full_task_description += f'Days to deadline: {timedelta.days}' + '\n\n'
                  full_task_description += "Comments:" + '\n'
                  full_task_description += comments_for_message + '\n\n'
                  full_task_description += '/AddComment_' + task_name_modified + '_' + discussion_id_modified
                  await tel_send_message(chat_id, full_task_description)
                else:
                  full_task_description += f'Deadline is overdue: {timedelta.days}' + '\n\n'
                  full_task_description += "Comments:" + '\n'
                  full_task_description += comments_for_message + '\n\n'
                  full_task_description += '/AddComment_' + task_name_modified + '_' + discussion_id_modified
                  await tel_send_message(chat_id, full_task_description)
            else:
                pass

        await default_message_with_commands(chat_id)

    elif(text == '/CreateTask'):
        user_states[chat_id] = 'INSIDE_CREATE_TASK'
        await tel_send_message(chat_id, user_states)
        user_states[chat_id] = 'AWAITING_TASK_NAME'
        await tel_send_message(chat_id, user_states)
    elif('AWAITING_TASK_NAME' in user_states[chat_id] and len(text) > 0):
        new_task_name = text
        create_task_result = create_task(new_task_name)
        await tel_send_message(chat_id, f"{create_task_result}")

        await default_message_with_commands(chat_id)
    elif('/AddComment_' in text):
        user_states[chat_id] = 'INSIDE_ADD_COMMENT'
        await tel_send_message(chat_id, user_states)
        discussion_id_modified = text.split("_")[-1]
        task_id_modified = text.split("_")[-2]
        discussion_id_original = discussion_id_modified[0:8] + '-' + discussion_id_modified[8:12] + '-' + discussion_id_modified[12:16] + '-' + discussion_id_modified[16:20] + '-' + discussion_id_modified[20:32]
        # await tel_send_message(chat_id, f"Enter the comment for discussion_id: {discussion_id_original}")
        user_states[chat_id] = 'AWAITING_INPUT_ADD_COMMENT_' + task_id_modified + '_' + discussion_id_original
        await tel_send_message(chat_id, user_states)
    elif('AWAITING_INPUT_ADD_COMMENT_' in user_states[chat_id] and len(text) > 0):
        user_comment = text
        discussion_id_from_state = user_states[chat_id].split("_")[-1]
        task_name_from_state = user_states[chat_id].split("_")[-2]
        add_comment_result = add_comment(user_comment, discussion_id_from_state)
        user_states[chat_id] = 'COMMENT_ADDED'
        # await tel_send_message(chat_id, user_states)
        await tel_send_message(chat_id, f"{add_comment_result} to the task: {task_name_from_state}")

        await default_message_with_commands(chat_id)
    else:
        user_states[chat_id] = 'INSIDE_ERROR_BLOCK'
        response_text = """
        Wrong command!
        Available commands:

        /onBoarding - Notion onboarding
        /CreateTask - Create new task
        /InProgress - Get tasks with "in progress" status
        /NotStarted - Get tasks with "not started" status
        """
        await tel_send_message(chat_id, user_states)
        await tel_send_message(chat_id, response_text)
    return Response('ok', status=200)
# else:
#     return "<h1>Welcome!</h1>"

if __name__ == '__main__':
        # pass
        app.run(host=os.getenv('IP', '0.0.0.0'), port=int(os.getenv('PORT', 4444)))