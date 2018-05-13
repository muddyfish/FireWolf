from discord.http import HTTPClient
from discord.errors import HTTPException
import aiohttp


class Oauth2:
    def __init__(self, bot, config):
        self.bot = bot
        self.client_id = self.bot.user.id
        self.redirect_uri = config["redirect_uri"]
        self.client_secret = config["secret"]

    async def refresh_token(self, refresh_token):
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'redirect_uri': self.redirect_uri
        }
        async with aiohttp.ClientSession() as session:
            async with session.post("https://discordapp.com/api/v6/oauth2/token",
                                                data=data,
                                                headers={"Content-Type": "application/x-www-form-urlencoded"}) as res:
                json = await res.json()
                return json["refresh_token"], json["access_token"]

    async def exchange_token(self, access_token, uri=""):
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'code': access_token,
            'redirect_uri': self.redirect_uri+uri
        }
        async with aiohttp.ClientSession() as session:
            #print(data)
            async with session.post("https://discordapp.com/api/v6/oauth2/token",
                                                data=data,
                                                headers={"Content-Type": "application/x-www-form-urlencoded"}) as res:
                json = await res.json()
                return json

    def get_oauth2_http(self, access_token, refresh_token):
        return Oauth2Http(self, access_token, refresh_token)


class Oauth2Http:
    def __init__(self, oauth2, access_token, refresh_token):
        self.oauth2 = oauth2
        self.refresh_token = refresh_token
        self.access_token = "Bearer "+access_token

    async def __aenter__(self):
        self.http = HTTPClient(None)
        self.http.token = self.access_token

        orig_request = self.http.request

        async def request(route, *, header_bypass_delay=None, **kwargs):
            try:
                return await orig_request(route, header_bypass_delay=header_bypass_delay, **kwargs)
            except HTTPException as e:
                if e.response.status == 401:
                    self.refresh_token, self.access_token = await self.oauth2.refresh_token(self.refresh_token)
                    self.http.token = "Bearer "+self.access_token
                    return await orig_request(route, header_bypass_delay=header_bypass_delay, **kwargs)
                raise

        self.http.request = request

        return self.http

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.http.close()
        return False
