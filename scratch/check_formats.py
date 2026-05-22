
import discord
import asyncio
from datetime import datetime, timedelta, timezone
from DiscordAlertsTrader.configurator import cfg
import sys

# Set default encoding to utf-8
sys.stdout.reconfigure(encoding='utf-8')

class FormatChecker(discord.Client):
    async def on_ready(self):
        print(f'Logged in as {self.user}')
        # Target Channel IDs
        channels_to_check = {
            "bearish-trades": 1238284846246133840,
            "bishop-alerts": 1222877717725450240,
            "awieee-alerts": 1272430749311565844,
            "ab-swings": 1335883303592394803
        }
        
        for name, ch_id in channels_to_check.items():
            channel = self.get_channel(ch_id)
            if channel is None:
                print(f"No access to {name} ({ch_id})")
                continue
            
            print(f"\n--- Recent messages from {name} ---")
            async for message in channel.history(limit=5):
                print(f"[{message.author.name}]: {message.content[:200]}")
                for embed in message.embeds:
                    if embed.description:
                        print(f" EMBED DESC: {embed.description[:200]}")
                    for field in embed.fields:
                        print(f" EMBED FIELD [{field.name}]: {field.value[:200]}")
        
        await self.close()

token = cfg['discord']['discord_token']
client = FormatChecker()
try:
    client.run(token)
except Exception as e:
    print(f"Error: {e}")
