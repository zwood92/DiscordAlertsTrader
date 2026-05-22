
import discord
from DiscordAlertsTrader.configurator import cfg

class SearchClient(discord.Client):
    async def on_ready(self):
        print(f'Logged in as {self.user}')
        print('Searching for "Trade Alerts Pro" server...')
        found = False
        for guild in self.guilds:
            if 'trade alerts pro' in guild.name.lower():
                print(f'Found Guild: {guild.name} (ID: {guild.id})')
                found = True
                print('Channels:')
                for channel in guild.text_channels:
                    print(f'  - {channel.name} (ID: {channel.id})')
        if not found:
            print('Server "Trade Alerts Pro" not found in your guilds.')
            print('Listing all guilds:')
            for guild in self.guilds:
                print(f' - {guild.name} (ID: {guild.id})')
        await self.close()

token = cfg['discord']['discord_token']
if len(token) < 20:
    print("Invalid token in config.ini")
else:
    client = SearchClient()
    try:
        client.run(token)
    except Exception as e:
        print(f"Error connecting to Discord: {e}")
