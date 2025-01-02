import discord
from discord.ext import commands
import asyncio
from discord.utils import get
import yt_dlp
import random
import math

ffmpeg_options = {
    'options': '-vn',
    "before_options": "-loglevel debug -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
}

ydl_opts = {
    'format': 'bestaudio/best',
    'restrictfilenames': True,
    'audioformat': 'mp3',
    'extract_flat': 'in_playlist',
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' 
}

# controls volume of AudioSource
VOLUME_CONTROL = 0.1

# determines size of each page for queue command
QUEUE_PAGE_SIZE = 10

# causes queue message to timeout at this time
Q_TIMEOUT = 30

# causes bot to disconnect after queue empties after some time
EMPTY_TIMEOUT = 5

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
    
    HELPER METHODS-
    get_server_info(ctx)
        Retrieves server async components or creates new ones
    connect_to_user(ctx)
        Handles connecting bot to the user's voice channel
    add_to_queue(ctx, *params)
        Adds songs to queue
    disconnect(guild)
        Handles disconnecting bot AFTER confirming voice protocol
        and server cleanup
    
    LISTENER-
    on_voice_state_update(member, before, after)
        Listener that detects when there are no human users left in voice chat
        and disconnects the bot
    
    COMMANDS-
    add(ctx, *params)
        Queues song query without automatically playing
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
        self.ydl = yt_dlp.YoutubeDL(ydl_opts)
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
                'loop': False,
                'timeout': False
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
        elif ctx.voice_client != ctx.author.voice.channel:
            await ctx.voice_client.move_to(ctx.author.voice.channel)
        return True
    
    
    async def add_to_queue(self, ctx, *params):
        """
        Adds songs to queue

        Args:
            ctx (discord.ext.commands.Context): context related to command call
        """
        # exits if the user is not connected to a voice channel
        connected = await self.connect_to_user(ctx)
        if not connected:
            return
        
        # gets server's async components
        server_info = self.get_server_info(ctx)
        q, lock = server_info['q'], server_info['lock']
        
        # retrieves youtube links if params are given
        if params:
            try:
                query = ' '.join(params)
                # assumes only soundcloud and youtube are available
                # TODO link verification? handle variety of links
                is_link = 'list=' in query or 'soundcloud.com' in query or 'youtube.com' in query
                info = self.ydl.extract_info(f"{'' if is_link else 'ytsearch:'}{query}", download=False)
                await ctx.send(f"Added song to queue!")
            except:
                ctx.send('Error in finding song')
                return
            # lock ensures that only one person is affecting the queue at a time
            async with lock:
                server_info["timeout"] = False
                if is_link:
                    await q.put(info)
                else:
                    for entry in info['entries']:
                        await q.put(entry)
    
    async def disconnect(self, guild):
        """
        Handles disconnecting bot AFTER confirming voice protocol
        and server cleanup

        Args:
            guild (discord.Guild): guild related to function call
        """
        await guild.voice_client.disconnect()
        if guild.id in self.servers:
            del self.servers[guild.id]
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before: discord.VoiceChannel, after):
        """
        Listener that detects when there are no human users left in voice chat
        and disconnects the bot

        This event triggers for a variety of voice state changes, the only 
        important one of which is when a user leaves the channel that the 
        bot is currently in.
        
        Args:
            member (discord.Member): the user
            before (discord.VoiceState): the previous voice state of the user
            after (discord.VoiceState): the resulting voice state of the user
        """
        
        # ignores bots
        if member.bot:
            return
        
        # if the user just joined a chat, nothing happens
        if before.channel is None:
            return
        
        # if the bot is not connected to before's guild, exit
        bot_vc = get(self.bot.voice_clients, guild=before.channel.guild)
        if bot_vc is None:
            return
        
        # if the user was not in the same channel as bot, exit
        if before.channel.id != bot_vc.channel.id:
            return
        
        # handles cases such as muting, unmuting, etc.
        if after.channel and before.channel.id == after.channel.id:
            return
        
        # counts the number of real users in the voice chat
        user_found = False
        for channel_member in before.channel.voice_states.keys():
            user = await self.bot.fetch_user(channel_member)
            if not user.bot:
                user_found = True
                break
        
        # is there is only one or no real users, disconnect
        if not user_found:
            await self.disconnect(before.channel.guild)    
    
    @commands.command(name="add", aliases=['a'])
    async def add(self, ctx, *params):
        """
        Queues song query without automatically playing
        
        Args:
            ctx (discord.ext.commands.Context): context related to command call
            params: command parameters that stores the query information
        """
        await self.add_to_queue(ctx, *params)
        
    @commands.command(name='play', aliases=['p'])
    async def play(self, ctx, *params):
        """
        Queues song query and plays from queue if not currently playing
        
        Args:
            ctx (discord.ext.commands.Context): context related to command call
            params: command parameters that stores the query information
        """
        await self.add_to_queue(ctx, *params)

        # if bot is paused, continue playing
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            
        # gets server's async components
        server_info = self.get_server_info(ctx)
        q, event, lock = server_info['q'], server_info['event'], server_info['lock']
        
        # exits early if client is already playing
        if ctx.voice_client.is_playing(): # TODO does resume make it play right away? What about small gaps between songs?
            return

        # continues until the song queue is empty
        while not q.empty():
            # uses event to communicate when current song is done playing
            event.clear()
            
            # if the bot is currently connected, play a song
            # otherwise, clear the queue
            if ctx.voice_client:
                # handles loop command logic
                async with lock:
                    song = server_info['current_song'] if server_info['loop'] else await q.get()
                    server_info['current_song'] = song
                
                # extracts audio stream and creates AudioSource object with adjustable volume
                if song.get('ie_key') == 'Soundcloud':
                    source = self.ydl.extract_info(song['url'], download=False)
                else:
                    source = self.ydl.extract_info(f"https://www.youtube.com/watch?v={song['id']}", download=False)

                updated_options = dict(ffmpeg_options)
                audio_source = discord.FFmpegPCMAudio(source['url'], **updated_options)
                audio_source = discord.PCMVolumeTransformer(audio_source)
                audio_source.volume = VOLUME_CONTROL
                
                # handles errors where two songs are played simultaneously
                try:
                    ctx.guild.voice_client.play(audio_source, after = lambda _: event.set())
                    await ctx.send(f"Now playing: {source['title']}")
                except:
                    async with lock:
                        await q.put((song))
                        
                await event.wait()
                audio_source.cleanup()
            else:
                q._init(0)
        else:
            async def timeout():
                await asyncio.sleep(EMPTY_TIMEOUT)
                async with lock:
                    if server_info["timeout"]:
                        await ctx.send("Queue is empty, so I'm leaving. See you next time!")
                        if ctx.voice_client is not None:
                            await self.disconnect(ctx.guild)

            async with lock:
                if server_info["timeout"]:
                    return
                server_info["timeout"] = True
            
            await timeout()

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
        if ctx.voice_client is None:
            await ctx.send("Bot is not connected.")
        elif ctx.voice_client.is_playing():
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
        if ctx.voice_client is None:
            await ctx.send("Bot is not connected.")
        elif ctx.voice_client.is_playing():
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
            async with info['lock']:
                loop_setting = not info['loop']
                info['loop'] = loop_setting
                title = info['current_song']['title']
            await ctx.send(f"Loop {'en' if loop_setting else 'dis'}abled for song {title}")
            # adds current song back to queue to start loop
            async with info['lock']:
                if loop_setting and info['q'].empty():
                    await info['q'].put(info['current_song'])
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
        page_size = QUEUE_PAGE_SIZE
        async with info['lock']:
            num_pages = math.ceil(info['q'].qsize() / page_size)
        if num_pages < 1:
            await ctx.send("Queue is empty! Add some songs first.")
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
                source_type = song.get('ie_key')
                # assumes only soundcloud and youtube available
                if source_type == 'Soundcloud':
                    time_str = 'Soundcloud song'
                    title = song['url']
                    title = title.split('/')[-1].replace('-', ' ')
                else:
                    duration = int(math.floor(song['duration']))
                    hours = '' if duration < 3600 else f'{duration // 3600}:'
                    minutes = duration % 3600 // 60
                    minutes = minutes if duration < 3600 else f'{minutes:02}'
                    time_str = f"{hours}{minutes}:{duration % 60:02}"
                    title = song['title']
                embed_settings.add_field(name=f"{index}. {title}", 
                                        value=time_str, inline=False)
        update_embed_settings(current_page)
        
        # sends initial message with left and right emotes to change pages
        message = await ctx.send(embed=embed_settings)
        await message.add_reaction("\u25c0")
        await message.add_reaction("\u25b6")
        
        def check(reaction, user):
            """
            Detects whether one of the valid reactions was used by a non-bot user

            Args:
                reaction (discord.Reaction): reaction added to the message
                user (discord.User): user that added the reaction
                
            Returns:
                bool: returns whether reaction was added one of the page flip emotes
            """
            return str(reaction.emoji) in ["\u25c0", "\u25b6"] and not user.bot

        # scans for reactions until timeout
        while True:
            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=Q_TIMEOUT, check=check)
                if str(reaction.emoji) == "\u25c0" and current_page > 1:
                    current_page -= 1
                    update_embed_settings(current_page)
                    await message.edit(embed=embed_settings)
                elif str(reaction.emoji) == "\u25b6" and current_page < num_pages:
                    current_page += 1
                    update_embed_settings(current_page)
                    await message.edit(embed=embed_settings)
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
            await self.disconnect(ctx.guild)
