import music
from discord import Intents
from discord.ext import commands
from dotenv import load_dotenv
import os
import random

load_dotenv()

#Unique bot token
TOKEN = os.environ.get('TOKEN') or os.getenv('TOKEN')
SECRET_MESSAGE = os.environ.get('SECRET_MESSAGE', 'hello')

intents = Intents.default()
intents.typing = False
intents.message_content = True
intents.voice_states = True
# TODO see if you need to restrict more stuff

#Instantiating the bot
client = commands.Bot(command_prefix='.', help_command=commands.MinimalHelpCommand(), intents=intents)

#Variables required for different commands
head_tail = ['Heads', 'Tails']
day_url = 'https://www.merriam-webster.com/word-of-the-day'
randword_url = 'https://randomword.com/'

# determines chance that secret message is sent - higher means lower chance
SECRET_MESSAGE_PROC = 99

@client.event
async def on_ready():
    await client.add_cog(music.Music(client))
    print(f'{client.user} had connected to Discord!')
    print(client.guilds)

@client.event
async def on_message(message):
    """
    Bot will send a message whenever a certain keyword is found

    Args:
        message (discord.message): Messages sent in discord servers with bot
    """
    if message.author == client.user:
        return
    if random.randint(0, SECRET_MESSAGE_PROC) == 0:
        emotes = message.guild.emojis
        react_emote = emotes[random.randint(0, len(emotes) - 1)]
        sent = await message.channel.send(SECRET_MESSAGE.replace('_', ' '))
        await sent.add_reaction(react_emote)
    # if 'bruh' in message.content.lower():
    #     await message.channel.send('bruh')
    await client.process_commands(message)


@client.command(name='flip')
async def flip(ctx):
    """
    Flips a two sided coin and sends the result

    Args:
        ctx (discord.ext.commands.Context): context related to command call
    """
    await ctx.send('Result: ' + head_tail[random.randint(0,1)] + '!')


@client.command(name='randnum')
async def randnum(ctx, arg1 = None, arg2 = None):
    """
    Gives a random number between the two given arguments

    Args:
        ctx (discord.ext.commands.Context): context related to command call
        arg1 (str, optional): First command parameter. Defaults to None.
        arg2 (str, optional): Second command parameter. Defaults to None.
    """
    min = int(arg1)
    max = int(arg2)
    if max < min:
        response = 'Invalid range of numbers'
    else:
        response = 'Number between ' + arg1 + '-' + arg2 + ': ' + str(random.randint(min, max))
    await ctx.send(response)
    
@randnum.error
async def randnum_error(ctx, error):
    """
    Handles errors for randnum function

    Args:
        ctx (discord.ext.commands.Context): context related to command call
        error : Error that arose
    """
    await ctx.send('Requires two valid number arguments!')

if __name__ == '__main__':
    client.run(TOKEN)