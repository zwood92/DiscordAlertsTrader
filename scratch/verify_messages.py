
import discord
import asyncio
from datetime import datetime, timedelta
from DiscordAlertsTrader.configurator import cfg
from DiscordAlertsTrader.server_alert_formatting import server_formatting

class HistoryClient(discord.Client):
    async def on_ready(self):
        print(f'Logged in as {self.user}')
        # Channel ID from user: 1001042379962322984
        # Mashup channel ID: 1194499208682684546
        target_channels = [1001042379962322984, 1194499208682684546]
        
        for ch_id in target_channels:
            channel = self.get_channel(ch_id)
            if channel is None:
                print(f"Channel {ch_id} not found.")
                continue
            
            print(f"\nFetching messages from {channel.name} ({ch_id})...")
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            count = 0
            async for message in channel.history(after=today, oldest_first=True):
                formatted_msg = server_formatting(message)
                print(f"[{message.created_at}] {message.author.name}: {message.content[:50]}...")
                if formatted_msg.content != message.content:
                    print(f"  -> Formatted: {formatted_msg.content[:50]}...")
                count += 1
            print(f"Found {count} messages from today.")
            
        await self.close()

token = cfg['discord']['discord_token']
print(f"Using token: {token[:10]}...")
client = HistoryClient()
try:
    client.run(token)
except Exception as e:
    print(f"Error: {e}")
