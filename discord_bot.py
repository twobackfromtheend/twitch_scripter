import asyncio
import logging
from threading import Thread

import discord

from twitch_scripter import TwitchScripter

logger = logging.getLogger(__name__)


class TwitchScripterBot(discord.Client):
    def __init__(self, twitch_id: str, vad_aggressiveness: int = 1):
        super().__init__()
        self.twitch_id = twitch_id
        self.vad_aggressiveness = vad_aggressiveness
        self.loop.create_task(self.twitch_scripter_backend())

    async def on_ready(self):
        logger.info(f'Logged on as {self.user}.')

    async def on_message(self, message):
        logger.debug('Message from {0.author}: {0.content}'.format(message))
        if message.author == self.user:
            return

        if message.content.startswith('$hello'):
            await message.channel.send('Hello!')

    async def twitch_scripter_backend(self):
        await self.wait_until_ready()
        await self.set_and_create_channel()

        twitch_scripter = TwitchScripter(self.twitch_id)

        twitch_scripter_thread = Thread(
            target=twitch_scripter.start,
            kwargs={
                'vad_aggressiveness': self.vad_aggressiveness,
                'callback': self.send_message_to_server,
            }
        )
        twitch_scripter_thread.start()

    async def set_and_create_channel(self):
        """
        Sets self.channel to the desired channel to output text.
        Creates the channel if it does not exist.
        :return:
        """
        self.guild = self.get_guild(747102730207625237)
        self.channel = None
        for category_channel in self.guild.categories:
            if category_channel.name == 'channels':
                for channel in category_channel.channels:
                    if channel.name == self.twitch_id:
                        self.channel = channel
                        break

                if self.channel is None:
                    self.channel = await category_channel.create_text_channel(self.twitch_id)
                    logger.info(f"Created text channel: {self.twitch_id}")

    def send_message_to_server(self, message: str):
        if message:
            asyncio.run_coroutine_threadsafe(self.channel.send(message), loop=self.loop)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    token = "REDACTED"

    client = TwitchScripterBot('rocketleague')
    client.run(token)
