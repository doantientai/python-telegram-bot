#!/usr/bin/env python
# pylint: disable=unused-argument
# This program is dedicated to the public domain under the CC0 license.

"""
First, a few callback functions are defined. Then, those functions are passed to
the Application and registered at their respective places.
Then, the bot is started and runs until we press Ctrl-C on the command line.

Usage:
Example of a bot-user conversation using ConversationHandler.
Send /start to initiate the conversation.
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.
"""

import logging
from typing import Dict
import json
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    PicklePersistence,
    filters,
)
import re
import pymysql

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

CHOOSING_CATEGORY, CHOOSING_EXERCISE, DOING_EXERCISE, ADDING_EXERCISE = range(4)

pseudo_database = {
    "collective": ["steps", "pilates"],
    "muscleupper": ["benchpress", "shoulderpress"],
    "musclelower": ["squat", "deadlift"],
    "cardio": ["running", "cycle"],
}

reply_keyboard = [
    ["Age", "Favourite colour"],
    ["Number of siblings", "Something else..."],
    ["Done"],
]

log_guide = {
    "collective": ["duration"],
    "muscleupper": ["weight", "reps"],
    "musclelower": ["weight", "reps"],
    "cardio": ["duration", "distance"],
}

markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

def connect_to_database():
    # Create a new connection
    host = db_info["host"]
    user = db_info["user"]
    password = db_info["password"]
    db = db_info["db"]
    conn = pymysql.connect(host=host, user=user, password=password, db=db)
    return conn

def execute_query(query: str):
    conn = connect_to_database()
    cursor = conn.cursor()
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.commit()
    cursor.close()
    conn.close()
    return rows

def get_list_exercises_in_category(category: str) -> list[str]:
    """Helper function for getting the list of exercises."""
    # category = category.replace("/", "")
    # return [[x] for x in pseudo_database[category]] + [["New exercise"]]

    # QUERY DATABASE
    query = f"SELECT exercise.full_name FROM exercise INNER JOIN category ON exercise.category_id = category.id  WHERE category.short_name = '{category}'"
    rows = execute_query(query)

    # add "New"
    rows = (("New",),) + rows

    return rows

def update_exercises_filter(context: ContextTypes.DEFAULT_TYPE) -> list[str]:
    """Helper function for getting the list of exercises."""
    exercises = []
    for category in pseudo_database:
        exercises += get_list_exercises_in_category(category)
    exercises_filter = "^(" + "|".join(exercises) + ")$"

    context.user_data.setdefault("all_exercises", exercises_filter)

def facts_to_str(user_data: Dict[str, str]) -> str:
    """Helper function for formatting the gathered user info."""
    facts = [f"{key} - {value}" for key, value in user_data.items()]
    return "\n".join(facts).join(["\n", "\n"])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation, tell them to click on the menu to choose the excercise type."""

    # remove user data if exists
    if "category" in context.user_data:
        context.user_data.pop("category")
    if "exercise" in context.user_data:
        context.user_data.pop("exercise")

    reply_text = "Welcome! Let's do some workout! \n👇 "
    # reply_keyboard = [["Collective", "Muscle Upper", "Muscle Lower", "Cardio"]]
    await update.message.reply_text(
        reply_text, 
        # reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )
    return CHOOSING_CATEGORY

async def choosing_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """You have just chosen a category, now showing the exercises."""
    category = update.message.text
    category = category.lower().replace(" ", "").removeprefix("/")

    # remove user data
    if "category" in context.user_data:
        context.user_data.pop("category")
    if "exercise" in context.user_data:
        context.user_data.pop("exercise")
    
    context.user_data.setdefault("category", category)

    # ask user to choose an exercise
    exercises = get_list_exercises_in_category(category)
    reply_text = "Choose an exercise: "
    reply_markup = ReplyKeyboardMarkup(exercises, one_time_keyboard=True)
    await update.message.reply_text(reply_text, reply_markup=reply_markup)

    return CHOOSING_EXERCISE


async def choosing_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """You have just chosen an exercise, now log it."""

    exercise_name = update.message.text
    context.user_data.setdefault("exercise", exercise_name)
    
    # get category
    category = context.user_data.get("category")
    match category:
        case "collective":
            reply_message = "Type the *_duration_* in minutes"
        case "muscleupper":
            reply_message = "Log the exercise: \n*_weight_* x *_reps_*"
        case "musclelower":
            reply_message = "Log the exercise: \n*_weight_* x *_reps_*"
        case "cardio":
            reply_message = "Log the exercise: \n*_duration_* x *_distance_*"
        case _:
            reply_message = f"Log the exercise: \n*_duration_*\nBy the way, never heard of this category {category}"

    reply_keyboard = ReplyKeyboardMarkup(
        [["Done"]], one_time_keyboard=True
    )
    #TODO showing the last session logs of the same exercise as a reference

    await update.message.reply_text(
        reply_message,
        reply_markup=reply_keyboard,
        parse_mode="MarkdownV2",)

    return DOING_EXERCISE

async def pressed_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask the user for a description of a custom category."""
    await update.message.reply_text("What is the name of the exercise?")

    return ADDING_EXERCISE

async def adding_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Getting the new name, add to the table exercise."""

    exercise_name = update.message.text
    category = context.user_data.get("category")
    context.user_data.setdefault("exercise", exercise_name)


    # get the category_id given category, then add the exercise to the table exercise with category_id
    query = f"SELECT id FROM category WHERE short_name = '{category}'"
    rows = execute_query(query)
    category_id = rows[0][0]
    query = f"INSERT INTO exercise (full_name, short_name, category_id) VALUES ('{exercise_name}', '{exercise_name.lower().replace(' ', '')}', {category_id})"

    execute_query(query)

    # ask user to choose an exercise
    exercises = get_list_exercises_in_category(category)
    reply_text = "Exercise added. Now you can choose it:"
    reply_markup = ReplyKeyboardMarkup(exercises, one_time_keyboard=True)
    await update.message.reply_text(reply_text, reply_markup=reply_markup)

    return CHOOSING_EXERCISE

async def logging_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store info provided by user and ask for the next category."""
    log_text = update.message.text
    exercise_name = context.user_data.get('exercise')
    exercise_name = exercise_name.lower().replace(" ", "")

    # get the category of the exercise from the database
    query = f"SELECT c.short_name FROM category c INNER JOIN exercise e ON c.id = e.category_id WHERE e.short_name = '{exercise_name}'"
    rows = execute_query( query)
    
    category = rows
    while len(category) == 1:
        category = category[0]

    match category:
        case "collective": # only log the duration (a decimal or float number)
            pattern = r'(\d+([.,]?\d*)?)'
            match = re.search(pattern, log_text)
            duration = match.group(1).replace(",", ".")
            #TODO : add user id to the log
            query = f"INSERT INTO log (exercise_id, duration, created_at) VALUES ((SELECT id FROM exercise WHERE short_name = '{exercise_name}'), {duration}, CURRENT_TIMESTAMP)"
            reply_message = f"Got it, done {exercise_name} for {duration} minutes"
        case "cardio": # log the distance (a decimal or float number) duration (a decimal or float number)
            # pattern: a decimal or float number, a comma, then a decimal or float number
            pattern = r'(\d+([.,]?\d*)?)\s*x\s*(\d+([.,]?\d*)?)\s*'
            match = re.search(pattern, log_text)       
            distance = match.group(1).replace(",", ".")
            duration = match.group(3).replace(",", ".")
            query = f"INSERT INTO log (exercise_id, distance, duration, created_at) VALUES ((SELECT id FROM exercise WHERE short_name = '{exercise_name}'), {distance}, {duration}, CURRENT_TIMESTAMP)"
            reply_message = f"Got it, done *{exercise_name}* for *{distance}* m, during *{duration}* minutes"
        case "muscleupper" | "musclelower": # log the weight and reps
            pattern = r'(\d+([.,]?\d*)?)\s*x\s*(\d+)'
            match = re.search(pattern, log_text)
            weight = match.group(1).replace(",", ".")
            reps = match.group(3)
            query = f"INSERT INTO log (exercise_id, weight, rep, created_at) VALUES ((SELECT id FROM exercise WHERE short_name = '{exercise_name}'), {weight}, {reps}, CURRENT_TIMESTAMP)"
            reply_message = f"Got it, a set of *{exercise_name}* at *{weight}* kg, for *{reps}* reps"
        case _:
            reply_message = f"Unknown category {category}"

    execute_query( query)

    reply_keyboard = ReplyKeyboardMarkup(
        [[log_text], ["Done"]], one_time_keyboard=True
    )

    exercise_name = context.user_data.get("exercise")    

    await update.message.reply_text(
        reply_message,
        reply_markup=reply_keyboard,
        parse_mode="MarkdownV2"
    )

    return DOING_EXERCISE

async def done_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Go back to the choose exercise menu."""
    # remove the exercise from the user data
    if "exercise" in context.user_data:
        context.user_data.pop("exercise")

    category = context.user_data.get("category")

    # ask user to choose an exercise
    exercises = get_list_exercises_in_category(category)
    reply_text = "Choose an exercise: "
    reply_markup = ReplyKeyboardMarkup(exercises, one_time_keyboard=True)
    await update.message.reply_text(reply_text, reply_markup=reply_markup)

    return CHOOSING_EXERCISE


async def show_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display the gathered info."""
    await update.message.reply_text(
        f"This is what you already told me: {facts_to_str(context.user_data)}"
    )

async def quit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ending session. Remove keyboard"""

    # remove user data
    if "category" in context.user_data:
        context.user_data.pop("category")
    if "exercise" in context.user_data:
        context.user_data.pop("exercise")

    await update.message.reply_text(
        f"Well done! See you next time!", reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


def main() -> None:
    """Run the bot."""
    # Create the Application and pass it your bot's token.
    persistence = PicklePersistence(filepath="conversationbot")
    application = Application.builder().token(token).persistence(persistence).build()

    # Add conversation handler with the states CHOOSING, TYPING_CHOICE and TYPING_REPLY
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
        ],
        states={
            CHOOSING_CATEGORY: [
                MessageHandler(filters.Text(["/collective", "/muscleupper", "/musclelower", "/cardio"]), choosing_category),
            ],
            CHOOSING_EXERCISE: [
                MessageHandler(filters.Regex("^New$"), pressed_new),
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND | filters.Regex("^Done$")) ,
                    choosing_exercise
                ),
                MessageHandler(filters.Text(["/collective", "/muscleupper", "/musclelower", "/cardio"]), choosing_category),
            ],
            ADDING_EXERCISE: [ 
                MessageHandler(filters.Text(["/collective", "/muscleupper", "/musclelower", "/cardio"]), choosing_category),
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND | filters.Regex("^Done$")),
                    adding_exercise,
                ),
            ],
            DOING_EXERCISE: [
                MessageHandler(
                    # filters.Regex(r"^(\d+([.,]?\d*)?)\s*x\s*(\d+)$"), # weight x reps
                    filters.TEXT & ~(filters.COMMAND | filters.Regex("^Done$")), 
                    logging_exercise,
                ),
                MessageHandler(filters.Text(["/collective", "/muscleupper", "/musclelower", "/cardio"]), choosing_category),
                MessageHandler(filters.Regex("^Done$"), done_exercise),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex("^/quit$"), quit)],
        name="gym-tracker-conversation",
        persistent=True,
    )

    application.add_handler(conv_handler)

    show_data_handler = CommandHandler("show_data", show_data)
    application.add_handler(show_data_handler)

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    path_keys = "C:/Users/Tai/Desktop/gym-tracker-bot/gym-tracker-telegram/python-telegram-bot/keys.json"
    with open(path_keys, "r") as f:
        keys = json.load(f)
    
    token = keys["gym-tracker-bot"]["token"]
    db_info = keys["database"]

    main()
