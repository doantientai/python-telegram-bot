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
markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)

def get_list_exercises_in_category(category: str) -> list[str]:
    """Helper function for getting the list of exercises."""
    category = category.replace("/", "")
    return [[x] for x in pseudo_database[category]] + [["New exercise"]]

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
    """Letting the user choose a category."""
    # if "category" in context.user_data:
    #     category = context.user_data.get("category")
    # else:
    # extract category from user message
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
    reply_text = "Choose an exercise below: "
    reply_markup = ReplyKeyboardMarkup(exercises, one_time_keyboard=True)
    await update.message.reply_text(reply_text, reply_markup=reply_markup)

    return CHOOSING_EXERCISE


async def choosing_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the chosen exercise."""

    # The exercise is already started
    if "exercise" in context.user_data:
        exercise_name = context.user_data.get("exercise")
    # The exercise has just been chosen
    else:
        exercise_name = update.message.text
        context.user_data.setdefault("exercise", exercise_name)

    reply_keyboard = ReplyKeyboardMarkup(
        [["Done"]], one_time_keyboard=True
    )
    await update.message.reply_text(
        f"{exercise_name}? \nLog the exercise: \n*_weight_* x *_reps_*",
        reply_markup=reply_keyboard)

    return DOING_EXERCISE


async def adding_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ask the user for a description of a custom category."""
    await update.message.reply_text("What is the name of the exercise?")

    return ADDING_EXERCISE


async def logging_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store info provided by user and ask for the next category."""
    text = update.message.text
    pattern = r'(\d+([.,]?\d*)?)\s*x\s*(\d+)'
    match = re.search(pattern, text)
    weight = match.group(1).replace(",", ".")
    reps = match.group(3)

    # TODO: Add weight and reps to the database

    reply_keyboard = ReplyKeyboardMarkup(
        [[text], ["Done"]], one_time_keyboard=True
    )

    exercise_name = context.user_data.get("exercise")    

    await update.message.reply_text(
        f"{exercise_name}: {weight}kg x {reps} times \n",
        reply_markup=reply_keyboard,
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
    reply_text = "Choose an exercise below: "
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
    application = Application.builder().token("6866660801:AAFJU5kEP7aG96m_4njx-0wjuu6N9bIyNvg").persistence(persistence).build()

    # Add conversation handler with the states CHOOSING, TYPING_CHOICE and TYPING_REPLY
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            # CommandHandler(["collective", "muscleupper", "musclelower", "cardio"], choosing_category),
        ],
        states={
            CHOOSING_CATEGORY: [
                # MessageHandler(filters.TEXT & ~(filters.COMMAND), choosing_category),
                MessageHandler(filters.Text(["/collective", "/muscleupper", "/musclelower", "/cardio"]), choosing_category),
            ],
            CHOOSING_EXERCISE: [
                MessageHandler(filters.Regex("^New exercise$"), adding_exercise),
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND | filters.Regex("^Done$")) ,
                    choosing_exercise
                ),
                MessageHandler(filters.Text(["/collective", "/muscleupper", "/musclelower", "/cardio"]), choosing_category),
            ],
            ADDING_EXERCISE: [
                MessageHandler(
                    filters.TEXT & ~(filters.COMMAND | filters.Regex("^Done$")), 
                    choosing_exercise
                )
            ],
            DOING_EXERCISE: [
                MessageHandler(
                    filters.Regex("^(\d+([.,]?\d*)?)\s*x\s*(\d+)$"), # weight x reps
                    logging_exercise,
                ),
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
    main()