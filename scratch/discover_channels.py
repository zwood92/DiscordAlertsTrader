
import discord
from DiscordAlertsTrader.configurator import cfg
import sys

# Set default encoding to utf-8
sys.stdout.reconfigure(encoding='utf-8')

class DiscoveryClient(discord.Client):
    async def on_ready(self):
        print(f'Logged in as {self.user}')
        # Supreme Alerts Guild ID: 1001036472717152306
        guild = self.get_guild(1001036472717152306)
        if guild is None:
            print("Could not find Supreme Alerts guild. Accessible guilds:")
            for g in self.guilds:
                print(f" - {g.name} (ID: {g.id})")
            await self.close()
            return

        print(f"Channels in {guild.name}:")
        for channel in guild.text_channels:
            # Look for keywords: alert, signal, analyst names
            name = channel.name.lower()
            if any(k in name for k in ['alert', 'signal', 'bearish', 'bishop', 'awieee', 'ab', 'swing']):
                print(f" [Potential Signal] {channel.name} (ID: {channel.id})")
            else:
                # Still print all for discovery
                print(f" {channel.name} (ID: {channel.id})")
        
        await self.close()

token = cfg['discord']['discord_token']
client = DiscoveryClient()
try:
    client.run(token)
except Exception as e:
    print(f"Error: {e}")
