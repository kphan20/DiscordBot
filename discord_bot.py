import discord
from discord.ext import commands
from dotenv import load_dotenv
import requests
import os
import random
from bs4 import BeautifulSoup
import youtube_dl
import queue
import asyncio
# from selenium import webdriver
# from webdriver_manager.chrome import ChromeDriverManager
# from selenium.webdriver import Chrome
# from selenium.webdriver.chrome.options import Options

load_dotenv()
#Unique bot token
TOKEN = os.environ.get('TOKEN') or os.getenv('TOKEN')

#Instantiating the bot
client = commands.Bot(command_prefix='.')

#Setting up the headless browser and html waiting
# chrome_options = Options()
# chrome_options.add_argument("-headless")
# chrome_options.page_load_strategy = 'eager'

#Dictionary of all available commands
BotCommands = {
    '.day': 'Prints the word of the day, its part of speech, and its definition(s)',
    '.flip': 'Flips a coin and returns the result',
    '.randword': 'Prints a random word and its definition',
    '.randnum [int1] [int2]': 'Returns a random number between [int1] and [int2]',
    }

#Variables required for different commands
head_tail = ['Heads', 'Tails']
day_url = 'https://www.merriam-webster.com/word-of-the-day'
randword_url = 'https://randomword.com/'

@client.event
async def on_ready():
    print(f'{client.user} had connected to Discord!')
    print(client.guilds)

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if 'bruh' in message.content.lower():
        await message.channel.send("bruh")
    await client.process_commands(message)

@client.command(name='day')
async def day(ctx):
    # driver = webdriver.Chrome(ChromeDriverManager().install(), options = chrome_options)
    # driver.get(day_url)
    response = requests.get(day_url)
    soup = BeautifulSoup(response.text, "html.parser")
    # driver.quit()

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
    await ctx.send('Result: ' + head_tail[random.randint(0,1)] + '!')

@client.command(name='randword')
async def rand(ctx):
    page_source = requests.get(randword_url).text
    soup = BeautifulSoup(page_source, 'html.parser')
        # driver.quit()

    word = soup.find(id="random_word").string
    definition = soup.find(id="random_word_definition").string
    response = word + ': ' + definition
    await ctx.send(response)

@client.command(name='randnum')
async def randnum(ctx, arg1 = None, arg2 = None):
    min = int(arg1)
    max = int(arg2)
    if max < min:
        response = 'Invalid range of numbers'
    else:
        response = 'Number between ' + arg1 + '-' + arg2 + ': ' + str(random.randint(min, max))
    await ctx.send(response)
    
@randnum.error
async def randnum_error(ctx, error):
    await ctx.send('Requires two valid number arguments!')

async def connect_to_user(ctx):
    if ctx.author.voice is None:
        await ctx.send("User must join a voice channel first!")
        return
    elif ctx.voice_client is None:
        await ctx.author.voice.channel.connect()
    else:
        await ctx.voice_client.move_to(ctx.author.voice.channel)

q = asyncio.Queue()
ydl_opts = {
    'format': 'bestaudio/best',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
    }

@client.command(name='play')
async def play(ctx, param):
    await connect_to_user(ctx)
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(param, download=False)
        URL = info['formats'][0]['url']
    ctx.voice_client.play(discord.FFmpegPCMAudio(URL, executable=os.path.abspath(os.getcwd()) + '\\ffmpeg\\ffmpeg\\bin\\ffmpeg.exe'))
    
@client.command()
async def test(ctx):
    
    print(ctx.voice_client.is_playing())
        
@play.error
async def play_error(ctx, error):
    print(error)
    await ctx.send('Something went wrong lmao')
    
@client.command(name='pause')
async def pause(ctx):
    pass

@client.command(name='skip')
async def skip(ctx):
    pass

@client.command()
async def connect(ctx):
    await connect_to_user(ctx)

@client.command()
async def dc(ctx):
    if ctx.voice_client is None:
        await ctx.send("Bot is not connected to a channel")
    else:
        await ctx.voice_client.disconnect()

@client.command(name='c')
async def list_of_commands(ctx):
    response = 'List of commands:\n'
    for BotCommand, desc in BotCommands.items():
        response += BotCommand + ': ' + desc + '\n'
    await ctx.send(response)


client.run(TOKEN)
