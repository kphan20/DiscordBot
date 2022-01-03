# DiscordBot

## Description

With the outage of a certain large music bot and the paywalls of other music bots, I decided to implement one for many reasons:

- Scale up an old project I used to learn the ropes of Python development
- Gain familiarity with the discord.py API for future reference
- Get introduced to async programming with the asyncio project
- Have an opportunity to examine open-source projects in depth
- Learn how to host applications on Heroku
- Practice Git/Github workflows more
- Develop something my friends and I can use regularly

I used youtube_dl to retrieve the audio streams, ffmpeg to play the audio streams, and the discord.py bot methods to handle command recognition and interacting with the Discord client. As mentioned before, Heroku was used for hosting the bot. There were many hangups as I tackled with asynchronous programming more deeply than I have before and figuring out the Heroku deployment process, but the current rendition of the bot successfully:

- Searches for songs
- Adds them to a queue
- Play songs continuously
- Shuffle the queue
- Skip songs
- Loop the current song
- Can handle multiple servers and support different music queues for each
- Various unrelated commands for fun

As for further improvements, these come to mind:

- Implement more established testing modules
- Allow for more advanced querying (eg from Spotify, Soundcloud, etc.)
- Implementing interactive games (more cogs)

## Running the project

The project was developed on a Windows device, so commands may vary depending on the OS.

Clone the repository:

```
git clone https://github.com/kphan20/DiscordBot.git
```

After navigating to the project, initialize a virtual environment:

```
python -m venv [venv_name]
venv_name/scripts/activate
```

Install all of the packages listed in the requirements.txt file:

```
pip install -r requirements.txt
```

You will need to create a bot and get its token. Instructions can be found [here.](https://discordpy.readthedocs.io/en/stable/discord.html)

Store the token as an environment variable. To run the bot locally, you will need to download ffmpeg and you may need to link its filepath whenever an FFmpegPCMAudio instance is created:

```
source = discord.FFmpegPCMAudio(audio_source, executable='FILEPATH_HERE')
```

To start the bot, use this:

```
python discord_bot.py
```

To host on Heroku, make sure the Procfile and runtime.txt are set up correctly. Add the bot token as a config variable through either the dashboard or the command line. I also used these buildpacks:

- [heroku-opus](https://elements.heroku.com/buildpacks/xrisk/heroku-opus)
- [heroku-buildpack-ffmpeg-latest](https://elements.heroku.com/buildpacks/jonathanong/heroku-buildpack-ffmpeg-latest)
- [heroku-buildpack-python](https://elements.heroku.com/buildpacks/heroku/heroku-buildpack-python)
