from discord.ext.commands import Bot
from discord.activity import Activity, ActivityType
from discord import Embed
import discord
import dbl
import aiohttp
import bs4
from db.models import GuildData
import asyncio
import urllib.parse
import datetime

bot = Bot(command_prefix="!",
          description="A bot to let you block out trolls with ease",
          request_offline_members=True)


async def initialise(config, steam_api_key, db):
    await bot.login(token=config["token"], bot=True)
    asyncio.ensure_future(bot.connect(reconnect=True))
    await bot.wait_until_ready()
    bot.db = db
    bot.steam_api_key = steam_api_key
    if config.get("dbl_token", ""):
        bot.dbl = dbl.Client(bot, config["dbl_token"])
        bot.dbl.bot_id = bot.user.id
        await bot.dbl.post_server_count()
    else:
        bot.dbl = None
    await update_status()
    return bot


async def create_channels(guild):
    category = await guild.create_category("FireWolf", reason="FireWolf category creation")
    gateway = await guild.create_text_channel("Gateway", category=category)
    logs = await guild.create_text_channel("FireWolf-Logs", category=category)
    embed = Embed(title="FireWolf Gateway",
                  colour=0xf04747,
                  description="To enter this server, you'll need to first share your integrations.\n"
                              "To get in, you'll need to have at least one verified integration that hasn't been used by anyone else in the server.\n"
                              "\n"
                             f"[Verify here]({bot.url}/verify?guild_id={guild.id})")
    await gateway.send(content=None, embed=embed)
    await bot.db.delete_guild(guild.id)
    guild_info = GuildData(guild_id=guild.id,
                           log_id=logs.id)
    await bot.db.insert(guild_info)


async def verify_member(member, role_id, add_on_authenticate, connections):
    guild = member.guild
    role = discord.utils.get(guild.roles, id=role_id)
    log_channel_id = await bot.db.get_log_channel(guild.id)
    if log_channel_id is None:
        log_channel = None
    else:
        log_channel = bot.get_channel(log_channel_id)
    try:
        if add_on_authenticate:
            await member.add_roles(role, reason="Verified")
        else:
            await member.remove_roles(role, reason="Verified")
    except discord.errors.Forbidden:
        if log_channel:
            await log_channel.send(f"Bot doesn't have permission to {'give' if add_on_authenticate else 'take'} {role.name} {'to' if add_on_authenticate else 'from'} {member}")
        return False
    if not log_channel:
        return True
    embed = Embed(title=str(member),
                  description="Has been verified",
                  colour=0xf04747)
    for connection in connections:
        embed.add_field(name=connection['type'].title(), value=f"{connection['name']} ({connection['id']})", inline=False)
    await log_channel.send(embed=embed)
    return True


@bot.listen()
async def on_member_join(member):
    role_id, add_on_authenticate, require_steam = await bot.db.get_guild_settings(member.guild.id)
    if None in (role_id, add_on_authenticate, require_steam):
        log_channel_id = await bot.db.get_log_channel(member.guild.id)
        if log_channel_id is None:
            return
        log_channel = bot.get_channel(log_channel_id)
        await log_channel.send(f"Bot isn't set up yet. Cannot do anything to {member}")
        return
    if not add_on_authenticate:
        role = discord.utils.get(member.guild.roles, id=role_id)
        await member.add_roles(role, reason="FireWolf auto role")


@bot.listen("on_guild_join")
@bot.listen("on_guild_remove")
async def update_status(*args, **kwargs):
    no_users = 0
    for guild in bot.guilds:
        if guild.id == 264445053596991498:
            continue
        no_users += len(guild.members)
    await bot.change_presence(activity=Activity(name=f"{len(bot.guilds)} servers and {no_users} users",
                                                type=ActivityType.watching))
    if bot.dbl:
        await bot.dbl.post_server_count()


@bot.command()
async def settings(ctx):
    await ctx.channel.send(f"{bot.url}/edit_server?guild_id={ctx.guild.id}")


@bot.command()
async def invite_me(ctx):
    params = urllib.parse.urlencode({"client_id": bot.user.id,
                                     "permissions": 268454928,
                                     "redirect_uri": f"{bot.url}/setup",
                                     "scope": "bot identify",
                                     "response_type": "code"})
    await ctx.channel.send(f"https://discordapp.com/api/oauth2/authorize?{params}")


@bot.command()
async def steam_profile(ctx, steam_id: int):
    steam_key = ctx.bot.steam_api_key
    xml_profile_url = f"https://steamcommunity.com/profiles/{steam_id}/?xml=1"
    json_profile_url = f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"
    async with aiohttp.ClientSession() as session:
        profile_data = bs4.BeautifulSoup(await (await session.get(xml_profile_url)).text(), features="html.parser")
        alt_profile_data = await (await session.get(json_profile_url,
                                                    params={"key": steam_key, "steamids": steam_id})).json()
    error = profile_data.find("error")
    if error:
        return await ctx.send(f"Steam error: {error.text}")
    alt_profile_data = alt_profile_data["response"]["players"][0]

    description = [profile_data.profile.onlinestate.text]
    if int(profile_data.profile.vacbanned.text): description.append("VAC Banned")
    trade_ban_state = profile_data.profile.tradebanstate.text
    if trade_ban_state != "None": description.append(f"Trade ban: {trade_ban_state}")
    embed = Embed(title=alt_profile_data["personaname"],
                  colour=0xf04747,
                  description="\n".join(description))
    embed.set_thumbnail(url=alt_profile_data["avatarfull"])
    embed.add_field(name="Steam ID", value=alt_profile_data["steamid"])
    last_logoff = datetime.datetime.fromtimestamp(alt_profile_data["lastlogoff"])
    if profile_data.profile.realname and profile_data.profile.realname.text.strip():
        embed.add_field(name="Name", value=profile_data.profile.realname.text)
    if profile_data.profile.summary and profile_data.profile.summary.text.strip():
        embed.add_field(name="Summary", value=profile_data.profile.summary.text)
    embed.add_field(name="Last seen", value=last_logoff.strftime("%d %B %Y at %I:%M %p (UTC+0)"))
    if profile_data.profile.membersince:
        embed.add_field(name="Member since", value=profile_data.profile.membersince.text)
    if profile_data.profile.location and profile_data.profile.location.text.strip():
        embed.add_field(name="Location", value=profile_data.profile.location.text)
    embed.url = f"https://steamcommunity.com/profiles/{steam_id}"
    await ctx.send(embed=embed)
