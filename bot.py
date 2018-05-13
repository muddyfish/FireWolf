from discord.ext.commands import Bot
from discord.activity import Game
from discord import Embed
import discord
from db.models import GuildData
import asyncio

bot = Bot(command_prefix="!",
          description="A bot to let you block out trolls with ease",
          activity=Game("meeping"))


async def initialise(config, db):
    await bot.login(token=config["token"], bot=True)
    asyncio.ensure_future(bot.connect(reconnect=True))
    await bot.wait_until_ready()
    bot.db = db
    return bot


async def create_channels(guild, url):
    category = await guild.create_category("FireWolf", reason="FireWolf category creation")
    gateway = await guild.create_text_channel("Gateway", category=category)
    logs = await guild.create_text_channel("FireWolf-Logs", category=category)
    embed = Embed(title="FireWolf Gateway",
                  colour=0xf04747,
                  description="To enter this server, you'll need to first share your integrations.\n"
                              "To get in, you'll need to have at least one verified integration that hasn't been used by anyone else in the server.\n"
                              "\n"
                             f"[Verify here]({url}/verify?guild_id={guild.id})")
    await gateway.send(content=None, embed=embed)
    guild_info = GuildData(guild_id=guild.id,
                           log_id=logs.id)
    await bot.db.insert(guild_info)


async def verify_member(member, role_id, add_on_authenticate, connections):
    guild = member.guild
    role = discord.utils.get(guild.roles, id=role_id)
    log_channel_id = await bot.db.get_log_channel(guild.id)
    log_channel = bot.get_channel(log_channel_id)
    try:
        if add_on_authenticate:
            await member.add_roles(role, reason="Verified")
        else:
            await member.remove_roles(role, reason="Verified")
    except discord.errors.Forbidden:
        await log_channel.send(f"Bot doesn't have permission to {'give' if add_on_authenticate else 'take'} {role.name} {'to' if add_on_authenticate else 'from'} {member}")
        return
    embed = Embed(title=str(member),
                  description="Has been verified",
                  colour=0xf04747)
    for connection in connections:
        embed.add_field(name=connection['type'].title(), value=f"{connection['name']} ({connection['id']})", inline=False)
    await log_channel.send(embed=embed)


@bot.listen()
async def on_member_join(member):
    role_id, add_on_authenticate = await bot.db.get_guild_settings(member.guild.id)
    if None in (role_id, add_on_authenticate):
        log_channel_id = await bot.db.get_log_channel(member.guild.id)
        log_channel = bot.get_channel(log_channel_id)
        await log_channel.send(f"Bot isn't set up yet. Cannot do anything to {member}")
        return
    if not add_on_authenticate:
        role = discord.utils.get(member.guild.roles, id=role_id)
        await member.add_roles(role, reason="FireWolf auto role")

@bot.command()
async def create(ctx):
    await create_channels(ctx.guild, "http://127.0.0.1:7788")
