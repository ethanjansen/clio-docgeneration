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
    _oauthBaseUrl = "https://app.clio.com/oauth"
    _redirectBaseUlr = "http://127.0.0.1"
    _authorizationBlankHeader = "Authorization: Bearer"

    # Constructor
    def __init__(self, clientId: str, clientSecret: str):
        self._token = None
        self._refreshToken = None
        self.whenTokenExpires = None

        self._state = None

        self.isAuthorized = False
        if self._refreshToken is not None:
            self.isAuthorized = True

        self._clientId = clientId
        self._clientSecret = clientSecret
        
    # Methods
    def getAuthorizationRequestLink(self) -> str:
        """
        Generate an application state and return the redirect link to authorize the application.

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
            "client_id": self._clientId,
            "redirect_uri": f"{self._redirectBaseUlr}/authorized",
            "redirect_on_decline": True,
            "state": self._state,
        }
        return f"{self._oauthBaseUrl}/authorize?{urlencode(params)}"
    

    def handleAuthorizationResponse(self, state: str, code: str = None, error: str = None) -> bool:
        """
        Handle the authorization response and get the access tokens.

        ### Args:
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
            "client_id": self._clientId,
            "client_secret": self._clientSecret,
            "redirect_uri": f"{self._redirectBaseUlr}/authorized", # should be the same as the one in the authorization request
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        response = requests.post(f"{self._oauthBaseUrl}/token", data=params, headers=headers)
        if response.status_code != 200:
            return False

        # Set the tokens
        data = response.json()
        self._token = data["access_token"]
        self._refreshToken = data["refresh_token"]
        self.whenTokenExpires = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])
        return True
    
    def checkAccessToken(self) -> bool:
        """
        Check if the access token is still valid.

        ### Returns:
        - True if the access token is still valid, False otherwise
        """
        if self._token is None or self.whenTokenExpires is None:
            return False
        return datetime.now(timezone.utc) < self.whenTokenExpires
    
    def refreshToken(self) -> bool:
        """
        Refresh the access token.
        This should be called after _whenTokenExpires is passed and/or client receives an 401 Unauthorized response.

        ### Args:
        - clientId: the client id of the application
        - clientSecret: the client secret of the application

        ### Returns:
        - True if the refresh was successful, False otherwise
        """
        if self._refreshToken is None:
            return False
        
        # Make the request
        params = {
            "grant_type": "refresh_token",
            "refresh_token": self._refreshToken,
            "client_id": self._clientId,
            "client_secret": self._clientSecret,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        response = requests.post(f"{self._oauthBaseUrl}/token", data=params, headers=headers)

        if response.status_code != 200:
            return False
        
        # Set the tokens
        data = response.json()
        self._token = data["access_token"]
        self.whenTokenExpires = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])

        return True