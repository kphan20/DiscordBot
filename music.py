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

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ydl = youtube_dl.YoutubeDL(ydl_opts)
        self.servers = {}
    
    def get_server_info(self, ctx):
        if not self.servers.get(ctx.guild.id):
            self.servers[ctx.guild.id] = {
                'q': asyncio.Queue(),
                'event': asyncio.Event(),
                'lock': asyncio.Lock(),
                'song_index': 0
            }
        info = self.servers.get(ctx.guild.id)
        return (info['q'], info['event'], info['lock'])
    
    async def connect_to_user(self, ctx):
        if ctx.author.voice is None:
            await ctx.send("User must join a voice channel first!")
            return False
        elif ctx.voice_client is None:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.voice_client.move_to(ctx.author.voice.channel)
        return True
    
    @commands.command(name='play')
    async def play(self, ctx, *param):
        connected = await self.connect_to_user(ctx)
        if not connected:
            return
        
        q, event, lock = self.get_server_info(ctx)
        
        if param:
            try:
                info = self.ydl.extract_info(f"ytsearch:{' '.join(param)}", download=False)
            except:
                ctx.send('Error in finding song')
                return
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
                    source = self.ydl.extract_info(f"https://www.youtube.com/watch?v={q.get_nowait()}", download=False)
                    await ctx.send(f"Now playing: {source['title']}")
                    source = discord.FFmpegPCMAudio(source['formats'][0]['url'], **ffmpeg_options)
                    source = discord.PCMVolumeTransformer(source)
                    source.volume = 0.5
                    ctx.voice_client.play(source, after = lambda _: ctx.bot.loop.call_soon_threadsafe(event.set))
                    await event.wait()
                    source.cleanup()
                else:
                    q._init(0)

    @commands.command()
    async def shuffle(self, ctx):
        q, event, lock = self.get_server_info(ctx.guild.id)
        async with lock:
            random.shuffle(q._queue)
        await ctx.send("Shuffled queue!")

    @play.error
    async def play_error(self, ctx, error):
        print(error)
        await ctx.send('Something went wrong lmao')
        
    @commands.command(name='pause')
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("Music is paused!")
        else:
            await ctx.send("No music is playing right now!")

    @commands.command(name='skip')
    async def skip(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("Song skipped!")
        else:
            await ctx.send("Invalid command!")

    @commands.command()
    async def loop(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            pass
        
    @commands.command()
    async def connect(self, ctx):
        await self.connect_to_user(ctx)

    @commands.command()
    async def dc(self, ctx):
        if ctx.voice_client is None:
            await ctx.send("Bot is not connected to a channel")
        else:
            await ctx.voice_client.disconnect()
            try:
                del self.servers[ctx.guild.id]
            except KeyError:
                pass
            