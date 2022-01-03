import discord
from discord.ext import commands
import asyncio
import youtube_dl
import random

ffmpeg_options = {
    'options': '-vn',
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
}

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

class SongQueue(asyncio.Queue):
    """
    Subclass of asyncio.Queue that allows for putting items in front of underlying deque

    ...

    Attributes
    ----------
    _put(item)
        Overridden from asyncio.Queue; appends left if item is a tuple and appends to back otherwise
        
    """
    def __init__(self):
        super().__init__()
        
    def _put(self, item):
        """
        Overridden from asyncio.Queue; appends left if item is a tuple and appends to back otherwise
        https://github.com/python/cpython/blob/3.10/Lib/asyncio/queues.py
        
        Args:
            item (tuple or str): item to be appended to queue
        """
        if isinstance(item, tuple):
            self._queue.appendleft(item[0])
        else:
            self._queue.append(item)
            
class Music(commands.Cog):
    """
    Represents the music command handler and allows for different music to be played between servers
    
    ...

    Attributes
    ----------
    bot : discord.ext.commands.Bot
        a representation of the bot
    ydl : youtube_dl.YoutubeDL
        used for retrieving the audio from youtube videos
    servers : dict
        stores all of the async components required to handle playing music


    Methods
    -------
    get_server_info(ctx)
        Retrieves server async components or creates new ones
    connect_to_user(ctx)
        Handles connecting bot to the user's voice channel
    play(ctx, *params)
        Queues song query and plays from queue if not currently playing
    shuffle(ctx)
        Shuffles the song queue
    play_error(ctx, error)
        Handles errors with the play command
    pause(ctx)
        Pauses the current song if one is playing
    skip(ctx)
        Skips the current song
    connect(ctx)
        Connects to user's voice channel
    dc(ctx)
        Disconnects bot from current voice channel. Also, deletes server information (clears queue, etc.)
        
    """
    def __init__(self, bot):
        """
        Args:
            bot (discord.ext.commands.Bot): a representation of the bot
        """
        self.bot = bot
        self.ydl = youtube_dl.YoutubeDL(ydl_opts)
        self.servers = {}
    
    def get_server_info(self, ctx):
        """
        Retrieves server async components or creates new ones

        Args:
            ctx (discord.ext.commands.Context): context related to command call

        Returns:
            dict: Returns the objects managing server music
        """
        # uses server id as key
        if not self.servers.get(ctx.guild.id):
            self.servers[ctx.guild.id] = {
                'q': SongQueue(),
                'event': asyncio.Event(),
                'lock': asyncio.Lock(),
                'current_song': '',
                'loop': False
            }
        info = self.servers.get(ctx.guild.id)
        return info
    
    async def connect_to_user(self, ctx):
        """
        Handles connecting bot to the user's voice channel
        
        Args:
            ctx (discord.ext.commands.Context): context related to command call

        Returns:
            bool: returns whether bot voice channel connection was successful or not
        """
        if ctx.author.voice is None:
            await ctx.send("User must join a voice channel first!")
            return False
        elif ctx.voice_client is None:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.voice_client.move_to(ctx.author.voice.channel)
        return True
    
    @commands.command(name='play', aliases=['p'])
    async def play(self, ctx, *params):
        """
        Queues song query and plays from queue if not currently playing
        
        Args:
            ctx (discord.ext.commands.Context): context related to command call
            params: command parameters that stores the query information
        """
        # exits if the user is not connected to a voice channel
        connected = await self.connect_to_user(ctx)
        if not connected:
            return
        
        # gets server's async components
        server_info = self.get_server_info(ctx)
        q, event, lock = server_info['q'], server_info['event'], server_info['lock']
        
        # retrieves youtube links if params are given
        if params:
            try:
                info = self.ydl.extract_info(f"ytsearch:{' '.join(params)}", download=False)
            except:
                ctx.send('Error in finding song')
                return
            # lock ensures that only one person is affecting the queue at a time
            async with lock:
                # adds multiple songs if a playlist was queried, adds a single song otherwise
                if info.get('_type'):
                    for entry in info['entries']:
                        await q.put(entry['id'])
                else:
                    await q.put(info['id'])

        # if bot is paused, continue playing
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
        
        # starts the song playing loop if no song is currently playing
        if not ctx.voice_client.is_playing():
            # continues until the song queue is empty
            while not q.empty():
                # uses event to communicate when current song is done playing
                event.clear()
                
                # if the bot is currently connected, play a song
                # otherwise, clear the queue
                if ctx.voice_client:
                    print("playing next song")
                    server_info = self.get_server_info(ctx)
                    song = q.get_nowait()
                    server_info['current_song'] = song
                    # if loop setting is on, then add song back to queue
                    if server_info['loop']:
                        async with lock:
                            await q.put((song))
                    source = self.ydl.extract_info(f"https://www.youtube.com/watch?v={song}", download=False)
                    await ctx.send(f"Now playing: {source['title']}")
                    source = discord.FFmpegPCMAudio(source['formats'][0]['url'], **ffmpeg_options, executable='C:\\Users\\knpmt\\IdeaProjects\\DiscordBot\\ffmpeg\\ffmpeg\\bin\\ffmpeg.exe')
                    source = discord.PCMVolumeTransformer(source)
                    source.volume = 0.5
                    ctx.voice_client.play(source, after = lambda _: ctx.bot.loop.call_soon_threadsafe(event.set))
                    await event.wait()
                    source.cleanup()
                else:
                    q._init(0)

    @commands.command()
    async def shuffle(self, ctx):
        """
        Shuffles the song queue
        
        Args:
            ctx (discord.ext.commands.Context): context related to command call
        """
        info = self.get_server_info(ctx)
        q, lock = info['q'], info['lock']
        
        # waits for other queue transaction to be done before shuffling
        async with lock:
            random.shuffle(q._queue)
        await ctx.send("Shuffled queue!")

    @play.error
    async def play_error(self, ctx, error):
        """
        Handles errors with the play command

        Args:
            ctx (discord.ext.commands.Context): context related to command call
            error : play command errors
        """
        print(error)
        await ctx.send('Something went wrong lmao')
        
    @commands.command(name='pause')
    async def pause(self, ctx):
        """
        Pauses the current song if one is playing

        Args:
            ctx (discord.ext.commands.Context): context related to command call
        """
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("Music is paused!")
        else:
            await ctx.send("No music is playing right now!")

    @commands.command(name='skip', aliases=['s'])
    async def skip(self, ctx):
        """
        Skips the current song

        Args:
            ctx (discord.ext.commands.Context): context related to command call
        """
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("Song skipped!")
        else:
            await ctx.send("Invalid command!")

    @commands.command()
    async def loop(self, ctx):
        """
        Loop the current song

        Args:
            ctx (discord.ext.commands.Context): context related to command call
        """
        if ctx.voice_client and ctx.voice_client.is_playing():
            info = self.get_server_info(ctx)
            loop_setting = not info['loop']
            info['loop'] = loop_setting
            await ctx.send(f"Loop {'en' if info['loop'] else 'dis'}abled")
            # adds current song back to queue to start loop
            if loop_setting:
                async with info['lock']:
                    await info['q'].put((info['current_song']))
        else:
            await ctx.send("Nothing is playing")
        
    @commands.command()
    async def connect(self, ctx):
        """
        Connects to user's voice channel

        Args:
            ctx (discord.ext.commands.Context): context related to command call
        """
        await self.connect_to_user(ctx)

    @commands.command()
    async def dc(self, ctx):
        """
        Disconnects bot from current voice channel. Also, deletes server information (clears queue, etc.)

        Args:
            ctx (discord.ext.commands.Context): context related to command call
        """
        if ctx.voice_client is None:
            await ctx.send("Bot is not connected to a channel")
        else:
            await ctx.voice_client.disconnect()
            try:
                del self.servers[ctx.guild.id]
            except KeyError:
                pass
            