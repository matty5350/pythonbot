import random
import json
import logging
import re
import os  # To handle file paths
import discord
from discord.ext import commands

class LifxChatBot:
    def __init__(self, link_channel_id):
        self.responses_file_path = 'responses.json'  # Default responses file path
        self.responses = self.load_responses(self.responses_file_path)
        self.chatbot_enabled = True  # Global chatbot status
        self.channel_status = {}  # Track channel-specific status (enabled/disabled)
        self.link_channel_id = link_channel_id  # Channel ID for sending links
        logging.info("LifxChatBot initialized with default responses.")

    def load_responses(self, file_path):
        """Load responses from a JSON file."""
        try:
            with open(file_path, 'r') as f:
                responses = json.load(f)
            logging.info(f"Loaded responses from {file_path}")
            return responses
        except FileNotFoundError as e:
            logging.error(f"Could not find responses file: {e}")
            return {}

    def change_responses_file(self, file_name):
        """Change the response file used for chatbot responses based on the selected file."""
        # Construct the file path for the selected response file
        if file_name == "lifxmodding":
            new_file_path = os.path.join("modding", "responses_lifxmodding.json")
        else:
            new_file_path = os.path.join("GameRelatedResponses", f"responses_{file_name}.json")

        logging.debug(f"Attempting to load responses from {new_file_path}")

        # Clear previous responses before loading new ones
        self.responses.clear()  # Clear any existing responses

        self.responses = self.load_responses(new_file_path)
        if self.responses:
            self.responses_file_path = new_file_path
            logging.info(f"Responses file changed to {new_file_path}")
            return True
        else:
            logging.error(f"Failed to load responses from {new_file_path}")
            return False

    def get_response(self, user_input):
        """Get a random response based on user input."""
        user_input = user_input.lower()  # Normalize user input to lowercase
        logging.debug(f"User input received: {user_input}")  # Log user input

        # Check for direct matches in responses
        if user_input in self.responses:
            responses = self.responses[user_input]
            if isinstance(responses, list) and responses:
                response = random.choice(responses)
                logging.info(f"Response found for exact match: {response}")
                return response

        # Improved keyword matching using regex
        for key in self.responses.keys():
            pattern = re.compile(r'\b' + re.escape(key.lower()) + r'\b')
            if pattern.search(user_input):
                responses = self.responses[key]
                if isinstance(responses, list) and responses:
                    response = random.choice(responses)
                    logging.info(f"Response found for keyword match '{key}': {response}")
                    return response

        logging.warning(f"No response found for user input: {user_input}")
        return None

    async def handle_message(self, message):
        """Handle incoming Discord messages."""
        if message.author.bot:
            logging.info(f"Ignored message from bot: {message.content}")
            return  # Ignore messages from bots

        if message.content.startswith('!'):
            await self.handle_command(message)
            return  # Return after processing the command

        if not self.chatbot_enabled:
            logging.info("Chatbot is globally disabled, ignoring message.")
            return

        channel_status = self.channel_status.get(message.channel.id, True)
        if not channel_status:
            logging.info(f"Chatbot is disabled in channel: {message.channel.name}, ignoring message.")
            return

        logging.info(f"Handling message from {message.author}: {message.content}")
        response = self.get_response(message.content)
        
        if response is not None:
            await message.channel.send(response)
            logging.info(f"Sent response: {response}")
        else:
            logging.info(f"Ignored unrelated message: {message.content}")

    async def handle_command(self, message):
        """Handle admin commands."""
        if not message.author.guild_permissions.administrator:
            logging.warning(f"User {message.author} does not have permissions to use commands.")
            return  # Ignore if the user is not an admin

        command = message.content.split(' ', 1)
        
        if command[0] == '!lifxclearchannel':
            await message.channel.purge()
            logging.info(f"Cleared all messages in channel: {message.channel.name}")

        elif command[0] == '!lifxcleanchannel':
            await message.channel.purge(limit=None, check=lambda m: m.author.bot)
            logging.info(f"Cleared bot messages in channel: {message.channel.name}")

        elif command[0] == '!lifxcleanbotdiscord':
            for channel in message.guild.text_channels:
                await channel.purge(limit=None, check=lambda m: m.author.bot)
            logging.info("Cleared all bot messages from the server.")

        elif command[0] == '!lifxtogglechatbot':
            self.chatbot_enabled = not self.chatbot_enabled
            response = "I have woke up" if self.chatbot_enabled else "Preparing to sleep..."
            await message.channel.send(response)
            logging.info(f"Chatbot status changed: {self.chatbot_enabled}")

        elif command[0] == '!lifxtogglechannelchatbot':
            channel_status = self.channel_status.get(message.channel.id, True)
            self.channel_status[message.channel.id] = not channel_status
            response = "I am now active in this channel" if not channel_status else "I have been asked to ignore this channel"
            await message.channel.send(response)
            logging.info(f"Channel chatbot status changed for {message.channel.name}: {self.channel_status[message.channel.id]}")

        elif command[0] == '!lifxrestartbot':
            await message.channel.send("Bot is restarting... (This is a placeholder)")
            logging.info("Bot restart command issued.")

        # Commands for changing the responses based on game
        elif command[0] == '!botchangetodayzchat':
            success = self.change_responses_file("dayz")
            if success:
                await message.channel.send("Switched to DayZ chat responses!")
            else:
                await message.channel.send("Failed to load DayZ chat responses.")

        elif command[0] == '!botchangelifeisfeudalchat':
            success = self.change_responses_file("lifeisfeudal")
            if success:
                await message.channel.send("Switched to Life is Feudal chat responses!")
            else:
                await message.channel.send("Failed to load Life is Feudal chat responses.")

        elif command[0] == '!botchangerustchat':
            success = self.change_responses_file("rust")
            if success:
                await message.channel.send("Switched to Rust chat responses!")
            else:
                await message.channel.send("Failed to load Rust chat responses.")

        elif command[0] == '!botchangeconanchat':
            success = self.change_responses_file("conan")
            if success:
                await message.channel.send("Switched to Conan chat responses!")
            else:
                await message.channel.send("Failed to load Conan chat responses.")

        elif command[0] == '!botchange7daystodiechat':
            success = self.change_responses_file("7daystodie")
            if success:
                await message.channel.send("Switched to 7 Days to Die chat responses!")
            else:
                await message.channel.send("Failed to load 7 Days to Die chat responses.")

        # New command for modding chat responses
        elif command[0] == '!botchangeLifxModdingchat':
            success = self.change_responses_file("lifxmodding")  # Use the specific file in modding folder
            if success:
                await message.channel.send("Switched to LIFX modding chat responses!")
            else:
                await message.channel.send("Failed to load LIFX modding chat responses.")

