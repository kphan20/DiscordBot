import discord
from discord.ext import commands
from dotenv import load_dotenv
import requests
import os
import random
from bs4 import BeautifulSoup
import youtube_dl
import asyncio

load_dotenv()
#Unique bot token
TOKEN = os.environ.get('TOKEN') or os.getenv('TOKEN')

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

@client.event
async def on_ready():
    print(f'{client.user} had connected to Discord!')
    print(client.guilds)
    #await test({})

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if 'bruh' in message.content.lower():
        await message.channel.send("bruh")
    await client.process_commands(message)

@client.command(name='day')
async def day(ctx):
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
        return False
    elif ctx.voice_client is None:
        await ctx.author.voice.channel.connect()
    else:
        await ctx.voice_client.move_to(ctx.author.voice.channel)
    return True

ydl_opts = {
    'format': 'bestaudio/best',
    'restrictfilenames': True,
    #'noplaylist': True,
    'extract_flat': 'in_playlist',
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
    }
lock = asyncio.Lock()
q = asyncio.Queue()
event = asyncio.Event()
ydl = youtube_dl.YoutubeDL(ydl_opts)
song_index = 0
servers = {}
@client.command(name='play')
async def play(ctx, param=None):
    connected = await connect_to_user(ctx)
    if not connected:
        return
    if param:
        info = ydl.extract_info(param, download=False)
        async with lock:
            if info.get('_type'):
                for entry in info['entries']:
                    await q.put(entry['id'])
            else:
                await q.put(info['id'])
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
    if not ctx.voice_client.is_playing():
        while not q.empty():
            event.clear()
            if ctx.voice_client:
                print("playing next song")
                source = ydl.extract_info(f"https://www.youtube.com/watch?v={q.get_nowait()}", download=False)
                await ctx.send(f"Now playing: {source['title']}")
                source = discord.FFmpegPCMAudio(source['formats'][0]['url'])
                source = discord.PCMVolumeTransformer(source)
                source.volume = 0.5
                ctx.voice_client.play(source, after = lambda _: ctx.bot.loop.call_soon_threadsafe(event.set))
                await event.wait()
                source.cleanup()
            else:
                q._init(0)

@client.command()
async def test(ctx, param='https://www.youtube.com/watch?v=aRsWk4JZa5k&list=PLYPQMTVEJGdRc8VEUp85DrWEpoTVzSHME'):
    urls = []
    with youtube_dl.YoutubeDL({'format':'bestaudio', 'extract_flat': 'in_playlist'}) as ydl:
        info = ydl.extract_info(param, download=False)
        print(info.keys())
        print(info.get('formats'))
        print(info.get('id'))
    #print(ctx.voice_client.is_playing())
    print(ctx.cog)

@client.command()
async def shuffle(ctx):
    async with lock:
        random.shuffle(q._queue)
    await ctx.send("Shuffled queue!")

@play.error
async def play_error(ctx, error):
    print(error)
    await ctx.send('Something went wrong lmao')
    
@client.command(name='pause')
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Music is paused!")
    else:
        await ctx.send("No music is playing right now!")

@client.command(name='skip')
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Song skipped!")
    else:
        await ctx.send("Invalid command!")

@client.command()
async def connect(ctx):
    await connect_to_user(ctx)

@client.command()
async def dc(ctx):
    if ctx.voice_client is None:
        await ctx.send("Bot is not connected to a channel")
    else:
        await ctx.voice_client.disconnect()

@client.command(name='help')
async def list_of_commands(ctx):
    response = 'List of commands:\n'
    for bot_command in bot_commands:
        response += f"{bot_command}\n"
    await ctx.send(response)


client.run(TOKEN)
