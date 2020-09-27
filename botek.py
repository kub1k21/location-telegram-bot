import telebot
from pymongo import MongoClient
from _collections import defaultdict
import math

token = '1303515875:AAFmEzFwQp1pjkkW2MyprkHx_5aQE9vBiCg'

bot = telebot.TeleBot(token)

client = MongoClient("mongodb://localhost:27017/")
db = client["user_data"]
locations = db["locations"]

START, LOCATION, PLACE_NAME, PHOTO_CONFIRMATION, PHOTO = range(5)
SEND_REQUEST, GET_PLACE_NAME = range(2)
USER_STATE = defaultdict(lambda: START)
GET_LOCATION_STATE = defaultdict(lambda: SEND_REQUEST)
user_data = defaultdict(lambda: {})
commands = ['/add', '/list', '/reset', '/find_closest_place']


def get_distance(lat_1, lng_1, lat_2, lng_2):
    d_lat = lat_2 - lat_1
    d_lng = lng_2 - lng_1

    temp = (
         math.sin(d_lat / 2) ** 2
       + math.cos(lat_1)
       * math.cos(lat_2)
       * math.sin(d_lng / 2) ** 2
    )

    return 6373.0 * (2 * math.atan2(math.sqrt(temp), math.sqrt(1 - temp)))


def get_state(message):
    return USER_STATE[message.chat.id]


def update_state(message, state):
    USER_STATE[message.chat.id] = state


def get_location_state(message):
    return GET_LOCATION_STATE[message.chat.id]


def update_location_state(message, state):
    GET_LOCATION_STATE[message.chat.id] = state


def update_user_data(user_id, key, value):
    user_data[user_id][key] = value

#
# @bot.message_handler(func=lambda message: get_state(message) == START and message.text not in commands)
# def random_mes_handler(message):
#     bot.send_message(message.chat.id, text='Ooops, wrong input or command')


@bot.message_handler(func=lambda message: get_state(message) == START, commands=['add'])
def start_handler(message):
    update_user_data(str(message.chat.id), 'user_id', str(message.chat.id))
    bot.send_message(message.chat.id, text='Please, send your location')
    update_state(message, LOCATION)


@bot.message_handler(func=lambda message: get_state(message) == LOCATION, content_types=['location'])
def location_handler(message):
    update_user_data(str(message.chat.id), 'latitude', message.location.latitude)
    update_user_data(str(message.chat.id), 'longitude', message.location.longitude)
    bot.send_message(message.chat.id, text="Please, send place name")
    update_state(message, PLACE_NAME)


@bot.message_handler(func=lambda message: get_state(message) == PLACE_NAME, content_types=['text'])
def place_name_handler(message):
    update_user_data(str(message.chat.id), 'place_name', message.text)
    bot.send_message(message.chat.id, text="Please, print YES to confirm or NO to refute photo sending")
    update_state(message, PHOTO_CONFIRMATION)


@bot.message_handler(func=lambda message: get_state(message) == PHOTO_CONFIRMATION, content_types=['text'])
def photo_confirm_handler(message):
    if message.text.lower() == 'no':
        x = locations.insert_one(user_data[str(message.chat.id)])
        bot.send_message(message.chat.id, text='Data was saved')
        user_data[str(message.chat.id)].clear()
        update_state(message, START)
    elif message.text.lower() == 'yes':
        bot.send_message(message.chat.id, text='Please, send photo')
        update_state(message, PHOTO)
    else:
        bot.send_message(message.chat.id, text="Wrong answer, won't save photo into database")
        x = locations.insert_one(user_data[str(message.chat.id)])
        bot.send_message(message.chat.id, text='Data was saved')
        user_data[str(message.chat.id)].clear()
        update_state(message, START)


@bot.message_handler(func=lambda message: get_state(message) == PHOTO, content_types=['photo'])
def photo_handler(message):
    fileID = message.photo[-1].file_id
    file_info = bot.get_file(fileID)
    downloaded_file = bot.download_file(file_info.file_path)
    update_user_data(str(message.chat.id), 'photo', downloaded_file)
    x = locations.insert_one(user_data[str(message.chat.id)])
    bot.send_message(message.chat.id, text='Data was saved')
    user_data[str(message.chat.id)].clear()
    update_state(message, START)


@bot.message_handler(commands=['list'])
def display_list_handler(message):
    location_list = ''
    i = 1
    for x in locations.find({'user_id': str(message.chat.id)}).sort('_id', -1):
        location_list += f'{i}. Place name: {x["place_name"]}; Latitude equals {x["latitude"]}; Longitude equals ' \
                         f'{x["longitude"]}' + '\n'
        i += 1
        if i > 10:
            break
    if i == 1:
        location_list = "There aren't any location in your data"
    bot.send_message(message.chat.id, text=location_list)


@bot.message_handler(commands=['reset'])
def reset_handler(message):
    result = locations.delete_many({'user_id': str(message.chat.id)})
    bot.send_message(message.chat.id, text='Your data was cleared')


@bot.message_handler(func=lambda message: get_location_state(message) == SEND_REQUEST,
                     commands=['find_closest_place'])
def find_closest_place_handler(message):
    bot.send_message(message.chat.id, text='Please, send your location')
    update_location_state(message, GET_PLACE_NAME)


@bot.message_handler(func=lambda message: get_location_state(message) == GET_PLACE_NAME, content_types=['location'])
def get_closest_place_handler(message):
    cur_lat, cur_lon = message.location.latitude, message.location.longitude
    find_cur_user_loc = locations.find({'user_id': str(message.chat.id)})
    prob_min_distance = get_distance(cur_lat, cur_lon, find_cur_user_loc[0]['latitude'], find_cur_user_loc[0]['longitude'])
    closest_place = (find_cur_user_loc[0]["place_name"], prob_min_distance, find_cur_user_loc[0]["latitude"], find_cur_user_loc[0]["longitude"])
    for x in locations.find({'user_id': str(message.chat.id)}):
        distance = get_distance(cur_lat, cur_lon, x['latitude'], x['longitude'])
        if distance < closest_place[1]:
            closest_place = (x["place_name"], distance, x['latitude'], x['longitude'])
    bot.send_message(message.chat.id, text=f'Closest place is {closest_place[0]}; Distance equals {float("{:.3f}".format(closest_place[1]))}')
    bot.send_location(message.chat.id, latitude=closest_place[2], longitude=closest_place[3])
    update_location_state(message, SEND_REQUEST)


bot.polling()
