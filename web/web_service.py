import aiohttp_jinja2
from jinja2 import FileSystemLoader
from aiohttp import web
import asyncio
from discord.http import Route
import discord

from bot import create_channels, verify_member

class WebService:
    def __init__(self, bot, oauth, web_config):
        self.bot = bot
        self.oauth = oauth
        self.url = web_config["url"]
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

    async def handle_setup_server(self, request):
        args = request.query
        code = args.get("code", None)
        if code is None:
            return web.Response(status=400, text="No code")
        token = await self.oauth.exchange_token(code, uri="setup")
        if "error" in token:
            return web.Response(status=400, text=token["error"])
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
        token = await self.oauth.exchange_token(code, uri="verify")
        if "error" in token:
            return web.Response(status=400, text=token["error"])
        if token["scope"] != "identify connections":
            return web.Response(status=400, text="Invalid scope")
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
            role_id, add_on_authenticate = await self.bot.db.get_guild_settings(guild_id)
            if None in (role_id, add_on_authenticate):
                return web.Response(status=400, text="This guild hasn't been set up")
            await verify_member(member, role_id, add_on_authenticate, connections)
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
        member = await self.get_member(request)
        perms = member.guild_permissions
        if not perms.manage_guild:
            return web.Response(text="Cannot manage this guild")

        context = {"guild": member.guild,
                   "base_url": self.url}
        return aiohttp_jinja2.render_template("setup.jinja2", request, context)

    async def handle_edit_post(self, request):
        member = await self.get_member(request)
        perms = member.guild_permissions
        if not perms.manage_guild:
            return web.Response(text="Cannot manage this guild")
        args = request.query
        if "setup" in args:
            await create_channels(member.guild, self.url)
        post = await request.post()
        role_id = int(post["role_id"])
        add_on_authenticate = post["add_on_authenticate"] == "true"
        await self.bot.db.set_guild_settings(member.guild.id, role_id, add_on_authenticate)
        log_channel_id = await self.bot.db.get_log_channel(member.guild.id)
        log_channel = self.bot.get_channel(log_channel_id)
        role = discord.utils.get(member.guild.roles, id=role_id)
        if add_on_authenticate:
            await log_channel.send(f"Adding {role} when user authenticates")
        else:
            await log_channel.send(f"Adding {role} when user joins, removing when authenticates")
        return web.Response(text="Success.<br>You may now close this tab")

    async def get_member(self, request, guild_id=None):
        access = request.cookies["access_token"]
        refresh = request.cookies["refresh_token"]
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
            if (connection["type"], connection["id"]) in used_connections:
                return False
        return True
