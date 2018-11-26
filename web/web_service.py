import aiohttp_jinja2
from jinja2 import FileSystemLoader
import aiohttp
from aiohttp import web
import asyncio
from discord.http import Route
import discord
import bs4

from bot import create_channels, verify_member


class NotLoggedIn(Exception):
    pass


class WebService:
    def __init__(self, bot, oauth, web_config):
        self.bot = bot
        self.oauth = oauth
        self.url = web_config["url"]
        self.bot.url = self.url
        self.loop = asyncio.get_event_loop()

        self.app = web.Application()

        aiohttp_jinja2.setup(self.app, loader=FileSystemLoader("./template/"))
        self.app.router.add_get('/static/css/generic.css', self.render_generic_css, name="css_no_login")
        self.app.router.add_static("/static/", "./static", name="static_no_login")
        self.app.router.add_get('/setup', self.handle_setup_server, name="setup_no_login")
        self.app.router.add_get('/edit_server', self.handle_edit)
        self.app.router.add_post('/edit_server', self.handle_edit_post)
        self.app.router.add_get('/verify', self.handle_verify)
        self.app.router.add_get('/verify_success', self.handle_verify_success)

        self.handler = self.app.make_handler()
        self.web_server = self.loop.create_server(self.handler, web_config["host"], web_config["port"])

        asyncio.ensure_future(self.web_server)
        asyncio.ensure_future(self.app.startup())

    async def exchange_code(self, code, uri):
        token = await self.oauth.exchange_token(code, uri=uri)
        print(token)
        if "error" in token:
            raise web.HTTPBadRequest(text=token["error"])
        if token["scope"] != "identify connections":
            raise web.HTTPBadRequest(text="Invalid scope")
        return token

    async def handle_setup_server(self, request):
        args = request.query
        code = args.get("code", None)
        if code is None:
            return web.Response(status=400, text="No code")
        token = await self.exchange_code(code, "setup")
        guild_id = token["guild"]["id"]
        assert guild_id == args["guild_id"]
        response = web.HTTPFound(f"edit_server?guild_id={guild_id}&setup=1")
        response.cookies["access_token"] = token["access_token"]
        response.cookies["refresh_token"] = token["refresh_token"]
        return response

    async def handle_verify(self, request):
        args = request.query
        code = args.get("code", None)
        if code is None:
            if "guild_id" not in args:
                return web.Response(status=400, text="No code or guild_id")
            client_id = self.bot.user.id
            uri = self.url + "/verify"
            response = web.HTTPFound(f"https://discordapp.com/oauth2/authorize?client_id={client_id}&redirect_uri={uri}&response_type=code&scope=identify%20connections")
            response.cookies["guild_id"] = args["guild_id"]
            return response
        token = await self.exchange_code(code, "verify")
        response = web.HTTPFound("verify_success")
        response.cookies["access_token"] = token["access_token"]
        response.cookies["refresh_token"] = token["refresh_token"]
        return response

    async def handle_verify_success(self, request):
        access = request.cookies["access_token"]
        refresh = request.cookies["refresh_token"]
        guild_id = int(request.cookies["guild_id"])
        member = await self.get_member(request, guild_id)
        connections = await self.get_connections(access, refresh)
        if not connections:
            return aiohttp_jinja2.render_template("verify_success.jinja2",
                                                  request,
                                                  {"text": "Failure - You have no verified connections. "
                                                           "Add one and try again"})
        if await self.is_allowed_in(guild_id, connections):
            role_id, add_on_authenticate, require_steam = await self.bot.db.get_guild_settings(guild_id)
            if None in (role_id, add_on_authenticate):
                return aiohttp_jinja2.render_template("verify_success.jinja2",
                                                      request,
                                                      {"text": "Failure - This server hasn't been set up yet",
                                                       "base_url": self.url})
            if require_steam:
                if not await self.verify_steam(connections):
                    return aiohttp_jinja2.render_template("verify_success.jinja2",
                                                          request,
                                                          {"text": "Failure - Your Steam account either isn't connected to Discord "
                                                                   ' <a href="https://support.steampowered.com/kb_article.php?ref=3330-IAGK-7663">or is limited</a>',
                                                           "base_url": self.url})
            try:
                verified = await verify_member(member, role_id, add_on_authenticate, connections)
            except discord.errors.Forbidden:
                return aiohttp_jinja2.render_template("verify_success.jinja2",
                                                      request,
                                                      {"text": "Failure - The bot isn't set up properly on the server.<br/>"
                                                               "DM an admin and ask them to fix it (cannot message logging channel)",
                                                       "base_url": self.url})
            if not verified:
                return aiohttp_jinja2.render_template("verify_success.jinja2",
                                                      request,
                                                      {"text": "Failure - The bot isn't set up properly on the server.<br/>"
                                                               "DM an admin and ask them to fix it (no permission to give role)",
                                                       "base_url": self.url})
            await self.bot.db.add_connections(member, connections)
            return aiohttp_jinja2.render_template("verify_success.jinja2",
                                                  request,
                                                  {"text": "Success - You may now close the tab",
                                                   "base_url": self.url})
        else:
            log_channel_id = await self.bot.db.get_log_channel(member.guild.id)
            log_channel = self.bot.get_channel(log_channel_id)
            await log_channel.send(f"{member} already has one of their integrations used")
            return aiohttp_jinja2.render_template("verify_success.jinja2",
                                                  request,
                                                  {"text": "Failure - One of your connections has already been used",
                                                   "base_url": self.url})

    async def handle_edit(self, request):
        code = request.query.get("code", None)
        if code is not None:
            token = await self.exchange_code(code, "edit_server")
            response = web.HTTPFound(f"edit_server?guild_id={int(request.cookies['guild_id'])}")
            response.cookies["access_token"] = token["access_token"]
            response.cookies["refresh_token"] = token["refresh_token"]
            return response
        try:
            member = await self.get_member(request)
        except NotLoggedIn:
            client_id = self.bot.user.id
            uri = self.url + "/edit_server"
            response = web.HTTPFound(f"https://discordapp.com/oauth2/authorize?client_id={client_id}&redirect_uri={uri}&response_type=code&scope=identify%20connections")
            response.cookies["guild_id"] = int(request.query["guild_id"])
            return response
        perms = member.guild_permissions
        if not perms.manage_guild:
            return aiohttp_jinja2.render_template("verify_success.jinja2",
                                                  request,
                                                  {"text": "Failure - You cannot manage this guild",
                                                   "base_url": self.url})

        member = member.guild.get_member(self.bot.user.id)
        perms = member.guild_permissions
        if not (perms.administrator or (perms.manage_roles and perms.manage_channels and
                                        perms.read_messages and perms.send_messages and
                                        perms.embed_links)):
            return aiohttp_jinja2.render_template("verify_success.jinja2",
                                                  request,
                                                  {"text": "Failure - Bot doesn't have required permissions",
                                                   "base_url": self.url})
        context = {"guild": member.guild,
                   "base_url": self.url}
        rtn = aiohttp_jinja2.render_template("setup.jinja2", request, context)
        return rtn

    async def handle_edit_post(self, request):
        member = await self.get_member(request)
        perms = member.guild_permissions
        if not perms.manage_guild:
            return web.Response(text="Cannot manage this guild")
        args = request.query
        if "setup" in args:
            await create_channels(member.guild)
        post = await request.post()
        role_id = int(post["role_id"])
        add_on_authenticate = post["add_on_authenticate"] == "true"
        require_steam = post["require_steam"] == "true"
        await self.bot.db.set_guild_settings(member.guild.id, role_id, add_on_authenticate, require_steam)
        log_channel_id = await self.bot.db.get_log_channel(member.guild.id)
        log_channel = self.bot.get_channel(log_channel_id)
        role = discord.utils.get(member.guild.roles, id=role_id)
        if add_on_authenticate:
            await log_channel.send(f"Adding {role} when user authenticates")
        else:
            await log_channel.send(f"Adding {role} when user joins, removing when authenticates")
        return web.Response(text="Success.<br>You may now close this tab")

    async def get_member(self, request, guild_id=None):
        try:
            access = request.cookies["access_token"]
            refresh = request.cookies["refresh_token"]
        except KeyError:
            raise NotLoggedIn()
        async with self.oauth.get_oauth2_http(access, refresh) as http:
            user_info = await http.get_user_info("@me")
            user_id = int(user_info["id"])
        if guild_id is None:
            guild_id = int(request.query["guild_id"])
        guild = self.bot.get_guild(guild_id)
        member = guild.get_member(user_id)
        return member

    async def render_generic_css(self, request):
        response = web.Response(status=200)
        response.content_type = 'text/css'
        response.charset = "utf-8"
        response.text = aiohttp_jinja2.render_string("generic.css", request, {"base_url": self.url})
        return response

    async def get_connections(self, access, refresh):
        async with self.oauth.get_oauth2_http(access, refresh) as http:
            all_connections = await http.request(Route('GET', '/users/@me/connections'))
        verified = []
        for connection in all_connections:
            if connection["verified"]:
                verified.append(connection)
        return verified

    async def is_allowed_in(self, guild_id, connections):
        used_connections = await self.bot.db.get_connections(guild_id)
        for connection in connections:
            if self.bot.db.calculate_hash(connection) in used_connections:
                return False
        return True

    async def verify_steam(self, connections):
        steam_connection = next((conn for conn in connections if conn["type"] == "steam"), None)
        if steam_connection is None:
            return False
        if not steam_connection["verified"]:
            return False
        steam_id = steam_connection["id"]
        profile_url = f"https://steamcommunity.com/profiles/{steam_id}/?xml=1"
        async with aiohttp.ClientSession() as session:
            profile_data_text = await (await session.get(profile_url)).text()
        profile_data = bs4.BeautifulSoup(profile_data_text, features="html.parser")
        is_limited = int(profile_data.profile.islimitedaccount.text)
        return not is_limited
