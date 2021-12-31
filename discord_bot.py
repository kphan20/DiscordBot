import os
from discord.ext import commands
from discord.ext.commands.errors import MissingRequiredArgument, UserInputError, BadArgument
from dotenv import load_dotenv
import requests
import os
import random
from bs4 import BeautifulSoup
# from selenium import webdriver
# from webdriver_manager.chrome import ChromeDriverManager
# from selenium.webdriver import Chrome
# from selenium.webdriver.chrome.options import Options

# load_dotenv()
#Unique bot token
TOKEN = os.environ.get('TOKEN')

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
    
@client.command(name='c')
async def list_of_commands(ctx):
    response = 'List of commands:\n'
    for BotCommand, desc in BotCommands.items():
        response += BotCommand + ': ' + desc + '\n'
    await ctx.send(response)


client.run(TOKEN)
