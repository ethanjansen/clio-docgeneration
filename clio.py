import requests
from urllib import urlencode
import json
import random
import string
from datetime import datetime, timedelta, timezone


# Clio Client
class Clio:
    # Class Variables
    _baseUrl = "https://app.clio.com/api/v4"
    _redirectBaseUlr = "http://127.0.0.1"

    # Constructor
    def __init__(self):
        self._token = None
        self._refreshToken = None
        self._whenTokenExpires = None

        self._state = None

        self.isAuthorized = False
        if self._refreshToken is not None:
            self.isAuthorized = True
        
    # Methods
    def getAuthorizationRequestLink(self, clientId: str) -> str:
        """
        Generate an application state and return the redirect link to authorize the application.

        ### Args:
        - clientId: the client id of the application

        ### Returns:
        - When not authorized: the redirect link to authorize the application
        - When authorized: None
        """
        if self.isAuthorized:
            return None
        
        # Set the state
        self._state = ''.join(random.choices(string.ascii_letters + string.digits, k=random.randint(15, 30)))

        # Make the request
        params = {
            "response_type": "code",
            "client_id": clientId,
            "redirect_uri": f"{self._redirectBaseUlr}/authorized",
            "redirect_on_decline": True,
            "state": self._state,
        }
        return f"https://app.clio.com/oauth/authorize?{urlencode(params)}"
    

    def handleAuthorizationResponse(self, clientId: str, clientSecret: str, state: str, code: str = None, error: str = None) -> bool:
        """
        Handle the authorization response and get the access tokens.

        ### Args:
        - clientId: the client id of the application
        - clientSecret: the client secret of the application
        - state: the returned state from the authorization request
        - code (optional): the authorization code
        - error (optional): the error code - None if no error, 'access_denied' if the user declined the authorization 

        ### Returns:
        - True if the authorization was successful (or already authorized), False otherwise
        """
        if self.isAuthorized:
            return True
        if error is not None and state != self._state:
            return False
        
        self._state = None

        # Make the request
        params = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": clientId,
            "client_secret": clientSecret,
            "redirect_uri": f"{self._redirectBaseUlr}/authorized", # should be the same as the one in the authorization request
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        response = requests.post(f"https://app.clio.com/oauth/token", data=params, headers=headers)
        if response.status_code != 200:
            return False

        # Set the tokens
        data = response.json()
        self._token = data["access_token"]
        self._refreshToken = data["refresh_token"]
        self._whenTokenExpires = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])
        return True
    
    def checkAccessToken(self) -> bool:
        """
        Check if the access token is still valid.

        ### Returns:
        - True if the access token is still valid, False otherwise
        """
        if self._token is None or self._whenTokenExpires is None:
            return False
        return datetime.now(timezone.utc) < self._whenTokenExpires
    
    def refreshToken(self, clientId: str, clientSecret: str) -> bool:
        """
        Refresh the access token.

        ### Args:
        - clientId: the client id of the application
        - clientSecret: the client secret of the application

        ### Returns:
        - True if the refresh was successful, False otherwise
        """
        pass