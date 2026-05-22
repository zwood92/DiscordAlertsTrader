
import discord
from DiscordAlertsTrader.configurator import cfg
import sys

# Set default encoding to utf-8 for stdout
sys.stdout.reconfigure(encoding='utf-8')

class CheckClient(discord.Client):
    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print(f'Type: {"Bot" if self.user.bot else "User"}')
        print('\nGuilds accessible:')
        for guild in self.guilds:
            print(f' - {guild.name} (ID: {guild.id})')
            
        print('\nChannels in config.ini:')
        channel_ids = {
            "demon": 904396043498709072,
            "TradeProElite": 1126325195301462117,
            "TPE_team": 1136674041122529403,
            "TPE_challenge": 1161371386191822870,
            "JPA": 1214652173171040256,
            "all-alerts-mashup": 1194499208682684546,
        }
        for name, ch_id in channel_ids.items():
            channel = self.get_channel(ch_id)
            if channel:
                print(f' [OK] {name}: {channel.name} (ID: {ch_id})')
            else:
                print(f' [FAIL] {name}: (ID: {ch_id}) - NO ACCESS')
        await self.close()

token = cfg['discord']['discord_token']
client = CheckClient()
try:
    client.run(token)
except Exception as e:
    print(f"Error: {e}")
