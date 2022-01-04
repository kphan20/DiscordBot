import discord
from discord.ext import commands
import asyncio
import youtube_dl
import random
import math

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
    loop(ctx)
        Loop the current song
    queue(ctx)
        Sends an embedded message that contains the songs currently loaded on the queue
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
                query = ' '.join(params)
                info = self.ydl.extract_info(f"{'' if 'list=' in query else'ytsearch:'}{query}", download=False)
                await ctx.send(f"Added song to queue!")
            except:
                ctx.send('Error in finding song')
                return
            # lock ensures that only one person is affecting the queue at a time
            async with lock:
                # adds multiple songs if a playlist was queried, adds a single song otherwise
                if info.get('_type'):
                    for entry in info['entries']:
                        await q.put(entry)
                else:
                    await q.put(info)

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
                    source = self.ydl.extract_info(f"https://www.youtube.com/watch?v={song['id']}", download=False)
                    await ctx.send(f"Now playing: {source['title']}")
                    source = discord.FFmpegPCMAudio(source['formats'][0]['url'], **ffmpeg_options)
                    source = discord.PCMVolumeTransformer(source)
                    source.volume = 0.5
                    ctx.voice_client.play(source, after = lambda _: ctx.bot.loop.call_soon_threadsafe(event.set))
                    await event.wait()
                    # if loop setting is on, then add song back to queue
                    if server_info['loop']:
                        async with lock:
                            await q.put((song))
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
            await ctx.send(f"Loop {'en' if info['loop'] else 'dis'}abled for song {info['current_song']['title']}")
            # adds current song back to queue to start loop
            if loop_setting:
                async with info['lock']:
                    await info['q'].put((info['current_song']))
        else:
            await ctx.send("Nothing is playing")
        
    @commands.command(name='queue', aliases=['q'])
    async def queue(self, ctx):
        """
        Sends an embedded message that contains the songs currently loaded on the queue

        Args:
            ctx (discord.ext.commands.Context): context related to command call
        """
        info = self.get_server_info(ctx)
        
        # used to decide which songs are displayed on the current page of the embed message
        page_size = 10
        num_pages = math.ceil(info['q'].qsize() / page_size)
        if num_pages < 1:
            return
        current_page = 1
        
        # enumerates songs in queue
        async with info['lock']:
            songs = list(enumerate(info['q']._queue, start = 1))
            
        embed_settings = discord.Embed(title='Current song queue:', color=discord.Color.blue())
        def update_embed_settings(page_num):
            """
            Changes the embed fields based on the current page
            """
            embed_settings.clear_fields()
            for x in range((page_num - 1) * page_size, min(len(songs), page_num * page_size)):
                index = songs[x][0]
                song = songs[x][1]
                duration = int(math.floor(song['duration']))
                minutes = duration % 3600 // 60
                time_str = f"{'' if duration < 3600 else f'{duration // 3600}:'}{minutes}:{duration % 60}"
                embed_settings.add_field(name=f"{index}. {song['title']}", 
                                        value=time_str, inline=False)
        update_embed_settings(current_page)
        
        # sends initial message with left and right emotes to change pages
        message = await ctx.send(embed=embed_settings)
        await message.add_reaction("\u25c0")
        await message.add_reaction("\u25b6")
        
        def check(reaction, user):
            """
            Detects whether one of the valid reactions was used

            Args:
                reaction (discord.Reaction): reaction added to the message
                user (discord.User): user that added the reaction
                
            Returns:
                bool: returns whether reaction was added one of the page flip emotes
            """
            return str(reaction.emoji) in ["\u25c0", "\u25b6"]
        
        # scans for reactions until timeout
        while True:
            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=30, check=check)
                if str(reaction.emoji) == "\u25c0" and current_page > 1:
                    current_page -= 1
                    update_embed_settings(current_page)
                    await message.edit(embed=embed_settings)
                elif str(reaction.emoji) == "\u25b6" and current_page < num_pages:
                    current_page += 1
                    update_embed_settings(current_page)
                    await message.edit(embed=embed_settings)
                else:
                    await message.remove_reaction(reaction, user)
            except asyncio.TimeoutError:
                break
                
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
