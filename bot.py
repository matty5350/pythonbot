import asyncio
import discord
import json
import os
import a2s
from LifxChatBot import LifxChatBot  # Import the LifxChatBot

class MessageManager:
    def __init__(self):
        self.message_cache = {}

    async def delete_old_messages(self, channel, ignore_ids=[]):
        """Delete old messages sent by the bot in the channel."""
        async for message in channel.history(limit=100):
            if message.author == channel.guild.me:
                if message.id not in ignore_ids:
                    try:
                        await message.delete()
                        print(f"Deleted old message: {message.id}")
                    except discord.NotFound:
                        print(f"Message {message.id} not found for deletion.")
                    except Exception as e:
                        print(f"Failed to delete message {message.id}: {e}")

    async def send_embedded_message(self, channel, embed):
        """Send an embedded message to the specified channel."""
        message = await channel.send(embed=embed)
        print(f"Sent message: {message.id}")
        return message

async def get_server_info(address):
    """Fetch real server information using a2s."""
    try:
        ip = address.get('server_ip')
        port = int(address.get('query_port')) if address.get('query_port') else None
        
        info = a2s.info((ip, port), timeout=5)
        players = int(info.player_count) if info.player_count is not None else 0
        max_players = int(info.max_players) if info.max_players is not None else 0
        
        return players, max_players, True  # Server is online
    except Exception as e:
        print(f"Error fetching server info: {e}")
        return 0, 0, False  # Server is offline

async def setup_discord_bot(message_manager, bot_config, bot_name, stagger_delay):
    # Set up intents
    intents = discord.Intents.default()
    intents.messages = True  # Enable message intent
    intents.guilds = True    # Include guilds intent

    client = discord.Client(intents=intents)

    # Initialize LifxChatBot with responses file
    lifx_chat_bot = LifxChatBot(bot_config.get('responses_file_path', 'responses.json'))  # Path to the JSON responses

    @client.event
    async def on_ready():
        print(f"{bot_name} | Bot logged in as {client.user}")

        # Fetch channels from config
        try:
            server_status_channel_id = bot_config['webhooks']['server_status']['channel_id']
            server_info_channel_id = bot_config['webhooks']['server_information']['channel_id']
            server_rules_channel_id = bot_config['webhooks']['server_rules']['channel_id']

            server_status_channel = client.get_channel(int(server_status_channel_id))
            server_info_channel = client.get_channel(int(server_info_channel_id))
            server_rules_channel = client.get_channel(int(server_rules_channel_id))

            if not all([server_status_channel, server_info_channel, server_rules_channel]):
                raise ValueError(f"One or more channels for {bot_name} could not be found.")

            # Start periodic updates if enabled
            if bot_config['webhooks']['server_status']['enabled']:
                client.loop.create_task(periodic_server_status_update(client, server_status_channel, bot_config, bot_name))
            else:
                print(f"{bot_name} | Server status updates are disabled.")

            if bot_config['webhooks']['server_information']['enabled']:
                client.loop.create_task(periodic_server_info_update(server_info_channel, bot_config, bot_name))
            else:
                print(f"{bot_name} | Server information updates are disabled.")

            if bot_config['webhooks']['server_rules']['enabled']:
                client.loop.create_task(periodic_server_rules_update(server_rules_channel, bot_config, bot_name))
            else:
                print(f"{bot_name} | Server rules updates are disabled.")

            client.loop.create_task(periodic_presence_update(client, bot_config, stagger_delay, bot_name))

        except KeyError as e:
            print(f"Missing required configuration for {bot_name}: {e}")
        except Exception as e:
            print(f"An error occurred while setting up {bot_name}: {e}")

    async def handle_message(message):
        """Handle incoming Discord messages."""
        if message.author.bot:
            return  # Ignore messages from bots

        # Get a response from LifxChatBot
        response = await lifx_chat_bot.handle_message(message)
        if response:
            await message.channel.send(response)  # Send the response back to the channel

    @client.event
    async def on_message(message):
        """Handle incoming messages from users."""
        await handle_message(message)

    async def update_bot_presence(client, players_online, max_players):
        """Update the bot's presence to show current player count."""
        await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f"{players_online}/{max_players} players"))
        print(f"Updated bot presence: {players_online}/{max_players} players online for {client.user}")

    async def periodic_presence_update(client, bot_config, stagger_delay, bot_name):
        """Periodically update bot's presence."""
        await client.wait_until_ready()
        
        while not client.is_closed():
            players_online, max_players, _ = await get_server_info({
                'server_ip': bot_config['server_ip'],
                'query_port': bot_config['query_port']
            })

            await update_bot_presence(client, players_online, max_players)
            await asyncio.sleep(60 + stagger_delay)

    async def periodic_server_status_update(client, channel, bot_config, bot_name):
        """Periodically check and update server status."""
        await client.wait_until_ready()

        previous_status = None  # Keep track of the previous status

        while not client.is_closed():
            try:
                players_online, max_players, server_online = await get_server_info({
                    'server_ip': bot_config['server_ip'],
                    'query_port': bot_config['query_port']
                })

                # Only update if server status has changed
                if server_online != previous_status:
                    embed = discord.Embed(
                        title="Server Status", 
                        color=0x00FF00 if server_online else 0xFF0000
                    )
                    embed.description = "@everyone " + ("Server is Online." if server_online else "Server is down.")

                    await message_manager.delete_old_messages(channel)
                    await message_manager.send_embedded_message(channel, embed)

                    previous_status = server_online  # Update previous status
                else:
                    print(f"{bot_name} | Skipped server status update: No changes in status.")
            except Exception as e:
                print(f"Error during status update: {e}")

            await asyncio.sleep(720)

    async def periodic_server_info_update(channel, bot_config, bot_name):
        """Periodically update server information."""
        await client.wait_until_ready()

        previous_info = None  # Keep track of the previous server info

        while not client.is_closed():
            try:
                players_online, max_players, server_online = await get_server_info({
                    'server_ip': bot_config['server_ip'],
                    'query_port': bot_config['query_port']
                })

                current_info = {
                    "players_online": players_online,
                    "max_players": max_players,
                    "server_online": server_online
                }

                # Only update if server info has changed
                if current_info != previous_info:
                    embed_server_info = discord.Embed(title="Server Information", color=0x00FF00)
                    embed_server_info.add_field(name="Server Name", value=bot_config['server_name'], inline=False)
                    embed_server_info.add_field(name="Players Online", value=f"{players_online}/{max_players}", inline=False)
                    embed_server_info.add_field(name="Server IP", value=bot_config['server_ip'])
                    embed_server_info.add_field(name="Connect Port", value=bot_config['server_port'])
                    embed_server_info.add_field(name="Query Port", value=bot_config['query_port'])
                    embed_server_info.add_field(name="Last Wipe Date", value=bot_config.get('last_wipe', 'N/A'))
                    embed_server_info.add_field(name="Next Planned Wipe Date", value=bot_config.get('next_wipe', 'N/A'))
                    embed_server_info.add_field(name="Live Map", value=bot_config.get('livemap', 'N/A'), inline=False)

                    map_image_url = bot_config.get('map_image', None)
                    if map_image_url:
                        embed_server_info.set_image(url=map_image_url)  # Set the image if the URL exists

                    await message_manager.delete_old_messages(channel)
                    await message_manager.send_embedded_message(channel, embed_server_info)

                    previous_info = current_info  # Update previous info
                else:
                    print(f"{bot_name} | Skipped server info update: No changes in server info.")
            except Exception as e:
                print(f"Error during server information update: {e}")

            await asyncio.sleep(3600)

    async def periodic_server_rules_update(channel, bot_config, bot_name):
        """Periodically update server rules."""
        await client.wait_until_ready()

        previous_rules = None  # Initialize a variable to store the previous rules

        while not client.is_closed():
            try:
                # Get current rules from the config
                current_rules = bot_config.get('rules', ["No rules specified."])

                # Compare current rules with previous rules
                if current_rules != previous_rules:
                    # If rules have changed, update the embed and send a new message
                    embed_rules = discord.Embed(title="Server Rules", color=0x00FF00)
                    embed_rules.description = "\n".join([f"{index + 1}. {rule}" for index, rule in enumerate(current_rules)])

                    await message_manager.delete_old_messages(channel)
                    await message_manager.send_embedded_message(channel, embed_rules)

                    # Update previous_rules to the current state
                    previous_rules = current_rules
                else:
                    print(f"{bot_name} | Skipped rules update: No changes in server rules.")
            except Exception as e:
                print(f"Error during server rules update: {e}")

            await asyncio.sleep(9320)

    await client.start(bot_config['bot_token'])

async def load_bot_configs():
    """Load bot configurations from JSON files in the 'Bots' folder."""
    config_dir = "Bots"
    bot_configs = []

    if not os.path.exists(config_dir):
        raise FileNotFoundError(f"Configuration directory '{config_dir}' does not exist.")

    for filename in os.listdir(config_dir):
        if filename.endswith('.json'):
            with open(os.path.join(config_dir, filename), 'r') as f:
                bot_config = json.load(f)
                bot_name = os.path.splitext(filename)[0]
                bot_configs.append((bot_config, bot_name))

    return bot_configs

async def main():
    message_manager = MessageManager()
    bot_configs = await load_bot_configs()
    
    stagger_delay = 0

    tasks = [setup_discord_bot(message_manager, bot_config, bot_name, stagger_delay) for bot_config, bot_name in bot_configs]
    
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
