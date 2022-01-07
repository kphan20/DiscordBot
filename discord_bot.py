import music
from discord.ext import commands
from dotenv import load_dotenv
import requests
import os
import random
from bs4 import BeautifulSoup
import youtube_dl

load_dotenv()
#Unique bot token
TOKEN = os.environ.get('TOKEN') or os.getenv('TOKEN')
SECRET_MESSAGE = os.environ.get('SECRET_MESSAGE', 'hello')

#Instantiating the bot
client = commands.Bot(command_prefix='.', help_command=None)

#Dictionary of all available commands
bot_commands = [
    '.day: Prints the word of the day, its part of speech, and its definition(s)',
    '.flip: Flips a coin and returns the result',
    '.randword: Prints a random word and its definition',
    '.randnum [int1] [int2]: Returns a random number between [int1] and [int2]',
    '.connect: Brings bot to current voice channel',
    '.play [query (optional)]: Plays searched song. Also resumes music if paused',
    '.pause: Pauses current song',
    '.shuffle: Shuffles the current song queue',
    '.skip: Skips the current song'
]

#Variables required for different commands
head_tail = ['Heads', 'Tails']
day_url = 'https://www.merriam-webster.com/word-of-the-day'
randword_url = 'https://randomword.com/'

# determines chance that secret message is sent - higher means lower chance
SECRET_MESSAGE_PROC = 99

@client.event
async def on_ready():
    print(f'{client.user} had connected to Discord!')
    print(client.guilds)
    #await test({})

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
    if 'bruh' in message.content.lower():
        await message.channel.send('bruh')
    await client.process_commands(message)

@client.command(name='day')
async def day(ctx):
    """
    Sends the word of the day, retrieved from the Merriam-Webster website

    Args:
        ctx (discord.ext.commands.Context): context related to command call
    """
    response = requests.get(day_url)
    soup = BeautifulSoup(response.text, "html.parser")

    word = soup.find('h1').string
    part_of_speech = soup.find(class_='main-attr').string

    intro = 'Word of the Day-\n'
    response = intro + word + ' (' + part_of_speech + '):'

    def_find = soup.find('div', class_='wod-definition-container')
    definition = def_find.find('p').text

    response += '\n' + definition
    await ctx.send(response)

@client.command(name='flip')
async def flip(ctx):
    """
    Flips a two sided coin and sends the result

    Args:
        ctx (discord.ext.commands.Context): context related to command call
    """
    await ctx.send('Result: ' + head_tail[random.randint(0,1)] + '!')

@client.command(name='randword')
async def rand(ctx):
    """
    Retrieves a random word from a website

    Args:
        ctx (discord.ext.commands.Context): context related to command call
    """
    page_source = requests.get(randword_url).text
    soup = BeautifulSoup(page_source, 'html.parser')

    word = soup.find(id="random_word").string
    definition = soup.find(id="random_word_definition").string
    response = word + ': ' + definition
    await ctx.send(response)

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

@client.command()
async def test(ctx, param='https://www.youtube.com/watch?v=aRsWk4JZa5k&list=PLYPQMTVEJGdRc8VEUp85DrWEpoTVzSHME'):
    """
    Testing command

    Args:
        ctx (discord.ext.commands.Context): context related to command call
        param (str, optional): A url to be downloaded. Defaults to a testing playlist on youtube.
    """
    urls = []
    with youtube_dl.YoutubeDL({'format':'bestaudio', 'extract_flat': 'in_playlist'}) as ydl:
        info = ydl.extract_info(param, download=False)
        print(info.keys())
        print(info.get('formats'))
        print(info.get('id'))
    #print(ctx.voice_client.is_playing())
    print(ctx.cog)


@client.command(name='help')
async def list_of_commands(ctx):
    """
    Custom help command

    Args:
        ctx (discord.ext.commands.Context): context related to command call
    """
    response = 'List of commands:\n'
    for bot_command in bot_commands:
        response += f"{bot_command}\n"
    await ctx.send(response)

client.add_cog(music.Music(client))
client.run(TOKEN)
