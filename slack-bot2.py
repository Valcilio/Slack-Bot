from slack import WebClient
from dotenv import load_dotenv
import os
from pathlib import Path
from flask import Flask, request, Response
from slackeventsapi import SlackEventAdapter
import string
from datetime import datetime, timedelta
import time

# puxando dados confidenciais do enviroment
env_path = Path('.env')
load_dotenv(dotenv_path=env_path)

# obtendo autorização para leitura de eventos
app = Flask(__name__)
slack_event_adapter = SlackEventAdapter(
    os.environ['SIGNING_SECRET_'], '/slack/events', app)

# conectando ao bot através do token
client = WebClient(token=os.environ['SLACK_TOKEN_'])
BOT_ID = client.api_call("auth.test")['user_id']

# criando variável de contagem
message_counts = {}
welcome_messages = {}

# palavras a serem respondidas
BAD_WORDS = ['hmm', 'no', 'val']

SCHEDULED_MESSAGES = [
    {'text': 'Primeira Mensagem!', 'post_at': int((
                                                          datetime.now() + timedelta(seconds=30)).timestamp()),
     'channel': 'C02HXJ6JWSZ'},
    {'text': 'Segunda Mensagem!', 'post_at': int((
                                                         datetime.now() + timedelta(seconds=50)).timestamp()),
     'channel': 'C02HXJ6JWSZ'}
]


# definindo a classe de mensagem de boas-vindas!
class WelcomeMessage:
    # definindo texto de boas-vindas!
    START_TEXT = {
        'type': 'section',
        'text': {
            'type': 'mrkdwn',
            'text': (
                'Seja bem vindo a esse canal, aqui você poderá colaborar com uma galera legal! \n\n'
                '*Get started by completing the tasks!*'
            )
        }
    }

    DIVIDER = {'type': 'divider'}

    # iniciando a classe
    def __init__(self, channel, user):
        self.channel = channel
        self.user = user
        self.icon_emoji = ':robot_face:'
        self.timestamp = ''
        self.completed = False

    # obtendo mensagem para mandar posteriormente
    def get_message(self):
        return {
            'ts': self.timestamp,
            'channel': self.channel,
            'username': 'Welcome Robot!',
            'icon_emoji': self.icon_emoji,
            'blocks': [
                self.START_TEXT,
                self.DIVIDER,
                self._get_reaction_task()
            ]
        }

    # pedindo reação a mensagem de boas vindas
    def _get_reaction_task(self):
        checkmark = ':white_check_mark:'
        if not self.completed:
            checkmark = ':white_large_square:'

        text = f'{checkmark} *React to this message!*'

        return {'type': 'section', 'text': {'type': 'mrkdwn', 'text': text}}


# mandando mensagem de boas vindas
def send_welcome_message(channel, user):
    if channel not in welcome_messages:
        welcome_messages[channel] = {}

    if user in welcome_messages[channel]:
        return

    welcome = WelcomeMessage(channel, user)
    message = welcome.get_message()
    response = client.chat_postMessage(**message)
    welcome.timestamp = response['ts']

    if channel not in welcome_messages:
        welcome_messages[channel] = {}
    welcome_messages[channel][user] = welcome


def list_scheduled_messages(channel):
    response = client.chat_scheduledMessages_list(channel=channel)
    messages = response.data.get('scheduled_messages')
    ids = []
    for msg in messages:
        ids.append(msg.get('id'))
    return ids

def schedule_messages(messages):
    ids = []
    for msg in messages:
        response = client.chat_scheduleMessage(
            channel=msg['channel'], text=msg['text'], post_at=msg['post_at']).data
        id_ = response.get('schedule_message_id')
        ids.append(id_)
    return ids

def delete_scheduled_message(ids, channel):
    for _id in ids:
        try:
            client.chat_deleteScheduledMessage(
                channel=channel, scheduled_message_id=_id)
        except Exception as e:
            print(e)

# definindo função de checagem se os caracteres especiais são disfarces para "bad words".
def check_if_bad_words(message):
    msg = message.lower()
    msg = msg.translate(str.maketrans('', '', string.punctuation))

    return any(word in msg for word in BAD_WORDS)


# definindo a rota das mensagens
@slack_event_adapter.on('message')
# fazendo o bot repetir o que for dito
def message(payload):
    # obtendo dados
    event = payload.get('event', {})
    channel_id = event.get('channel')
    user_id = event.get('user')
    text = event.get('text')

    # contando as mensagens de usuários
    if user_id != None and BOT_ID != user_id:
        if user_id in message_counts:
            message_counts[user_id] += 1
        else:
            message_counts[user_id] = 1

        if text.lower() == 'start':
            send_welcome_message(f'@{user_id}', user_id)
        elif check_if_bad_words(text):
            ts = event.get('ts')
            client.chat_postMessage(
                channel=channel_id, thread_ts=ts, text="ESSA PALAVRA NÃO PODE SER DITA!!!")


# criando rota para reação às reações
@slack_event_adapter.on('reaction_added')
# definindo função para reagir
def reaction(payload):
    event = payload.get('event', {})
    channel_id = event.get('item', {}).get('channel')
    user_id = event.get('user')

    if f'@{user_id}' not in welcome_messages:
        return

    # definindo confirmação da reação
    welcome = welcome_messages[f'@{user_id}'][user_id]
    welcome.completed = True
    welcome.channel = channel_id
    message = welcome.get_message()
    updated_message = client.chat_update(**message)
    welcome.timestamp = updated_message['ts']


# definindo a rota do slash command
@app.route('/message-count', methods=['POST'])
# contando mensagens
def message_count():
    data = request.form
    user_id = data.get('user_id')
    channel_id = data.get('channel_id')
    message_count = message_counts.get(user_id, 0)

    client.chat_postMessage(
        channel=channel_id, text=f'Message: {message_count}')
    return Response(), 200


# rodando o bot
if __name__ == "__main__":
    ids = schedule_messages(SCHEDULED_MESSAGES)
    list_scheduled_messages('C02HXJ6JWSZ')
    delete_scheduled_message(ids, 'C02HXJ6JWSZ')
    app.run(debug=True)
