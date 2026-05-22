
import discord
import asyncio
import pandas as pd
from datetime import datetime, timedelta, timezone
from DiscordAlertsTrader.configurator import cfg, channel_ids
from DiscordAlertsTrader.server_alert_formatting import server_formatting
import os
import sys

# Set default encoding to utf-8
sys.stdout.reconfigure(encoding='utf-8')

class HistoryPuller(discord.Client):
    def __init__(self, days=7, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.days = days
        self.data_dir = cfg['general']['data_dir']
        os.makedirs(self.data_dir, exist_ok=True)

    async def on_ready(self):
        print(f'Logged in as {self.user}')
        print(f'Pulling last {self.days} days of history...')
        
        after_date = datetime.now(timezone.utc) - timedelta(days=self.days)
        
        for ch_name, ch_id in channel_ids.items():
            channel = self.get_channel(ch_id)
            if channel is None:
                print(f"Skipping {ch_name} ({ch_id}): No access.")
                continue
            
            print(f"Fetching {ch_name}...")
            msgs = []
            try:
                async for message in channel.history(after=after_date, oldest_first=True):
                    # Basic parsing to save to CSV format expected by the app
                    # AuthorID,Author,Date,Content,Parsed
                    msg_date = message.created_at.replace(tzinfo=timezone.utc).astimezone(tz=None)
                    msg_date_f = msg_date.strftime("%Y-%m-%d %H:%M:%S.%f")
                    
                    # Reformat if needed
                    formatted = server_formatting(message)
                    
                    msgs.append({
                        'AuthorID': message.author.id,
                        'Author': f"{message.author.name}#{message.author.discriminator}".replace("#0", ""),
                        'Date': msg_date_f,
                        'Content': message.content,
                        'Parsed': formatted.content if formatted.content != message.content else ""
                    })
                
                if msgs:
                    df = pd.DataFrame(msgs)
                    fname = os.path.join(self.data_dir, f"{ch_name}_message_history.csv")
                    # Append or overwrite? User asked to "pull", so I'll merge with existing if possible
                    if os.path.exists(fname):
                        existing_df = pd.read_csv(fname)
                        df = pd.concat([existing_df, df]).drop_duplicates(subset=['Date', 'Author', 'Content'])
                    
                    df.to_csv(fname, index=False)
                    print(f" Saved {len(msgs)} messages to {fname}")
                else:
                    print(f" No new messages found for {ch_name} in the last {self.days} days.")
            except discord.errors.Forbidden:
                print(f" Error: No permission to read history for {ch_name}")
            except Exception as e:
                print(f" Error pulling {ch_name}: {e}")
                
        print("Done pulling history.")
        await self.close()

token = cfg['discord']['discord_token']
client = HistoryPuller(days=7)
try:
    client.run(token)
except Exception as e:
    print(f"Error: {e}")
