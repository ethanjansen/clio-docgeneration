from enum import Enum
import requests
from urllib import urlencode
import json
import random
import string
from datetime import datetime, timedelta, timezone


# Clio Client
class Clio:
    # Enums/Constants/Types
    class CustomAction(Enum):
        GENERATE_DOCUMENT = 1
        # IMPORT_MATTER_FROM_GOOGLE_FORMS = 2 #NYI

    # Class Variables
    _baseUrl = "https://app.clio.com/api/v4"
    _oauthBaseUrl = "https://app.clio.com/oauth"
    _redirectBaseUrl = "http://127.0.0.1"
    _authorizationBlankHeader = "Authorization: Bearer"

    # Constructor
    def __init__(self, clientId: str, clientSecret: str, refreshToken: str = None, userInstalledCustomActions: dict[int, CustomAction] = None):
        self._clientId = clientId
        self._clientSecret = clientSecret

        self._token = None
        self._refreshToken = refreshToken
        self.whenTokenExpires = None
        self.isAuthorized = self._refreshToken is not None

        self._state = None

        self.userInstalledCustomActions = userInstalledCustomActions  # dict[id, CustomAction]

        self._rateLimitRemaining = 100

    # Authorization Methods
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
            "redirect_uri": f"{self._redirectBaseUrl}/authorized",
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
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self._clientId,
            "client_secret": self._clientSecret,
            "redirect_uri": f"{self._redirectBaseUrl}/authorized",  # should be the same as the one in the authorization request
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        response = requests.post(f"{self._oauthBaseUrl}/token", data=data, headers=headers)
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
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self._refreshToken,
            "client_id": self._clientId,
            "client_secret": self._clientSecret,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        response = requests.post(f"{self._oauthBaseUrl}/token", data=data, headers=headers)

        if response.status_code != 200:
            return False

        # Set the tokens
        data = response.json()
        self._token = data["access_token"]
        self.whenTokenExpires = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])

        return True

    # Custom Action Methods
    def installCustomActions(self, customActions: set[CustomAction]) -> dict[str, list[tuple[CustomAction, str]]]:
        """
        Install custom actions into Clio Manage.

        ### Args:
        - customActions: the set of custom actions to install

        ### Returns:
        - a dictionary including "success" and "failed" custom actions (with optional reasons for failure)
        """
        returnDict = {
            "success": list(),
            "failed": list(),
        }

        for installedAction in self.userInstalledCustomActions.values():
            if installedAction in customActions:
                customActions.remove(installedAction)
                returnDict["failed"].add((installedAction, "Already installed"))

        for customAction in customActions:
            if customAction == Clio.CustomAction.GENERATE_DOCUMENT:
                installation = self._installActionGenerateDocument()
                if installation[0]:
                    returnDict["success"].add((customAction, "Installed"))
                else:
                    returnDict["failed"].add((customAction, installation[1]))
            else:  # how did we get here? Likely not fully implemented
                returnDict["failed"].add((customAction, "Not implemented"))

        return returnDict

    def removeCustomActions(self, customActions: set[CustomAction]) -> dict[str, list[tuple[CustomAction, str]]]:
        """
        Remove custom actions from Clio Manage.

        ### Args:
        - customActions: the set of custom actions to remove

        ### Returns:
        - a dictionary including "success" and "failed" custom actions (with optional reasons for failure)
        """
        returnDict = {
            "success": list(),
            "failed": list(),
        }

        for installedAction in self.userInstalledCustomActions.values():
            if installedAction not in customActions:
                continue

            if installedAction == Clio.CustomAction.GENERATE_DOCUMENT:
                removal = self._removeActionGenerateDocument()
                if removal[0]:
                    returnDict["success"].add((installedAction, "Removed"))
                else:
                    returnDict["failed"].add((installedAction, removal[1]))
            else:  # how did we get here? Likely not fully implemented
                returnDict["failed"].add((installedAction, "Not implemented"))

            customActions.remove(installedAction)

        for customAction in customActions:
            returnDict["failed"].add((customAction, "Not installed"))

        return returnDict

    def getCustomAction(self, id: int) -> str:
        """
        Get label for custom action installed in Clio.

        ### Args:
        - id: id for custom action

        ### Returns: label of custom action associated with id. Returns empty string if id does not exist.
        """
        label = ""
        headers = {
            "Authorization": f"{self._authorizationBlankHeader} {self._token}",
        }
        params = {
            "fields": "label",
        }
        response = requests.get(f"{self.baseUrl}/custom_actions/{id}.json", params=params, headers=headers)
        handledResponse = self._handleRequest(response)  # expect "200 Ok" -- 404 is also likely acceptable if id does not exist
        if handledResponse[0]:
            label = response.json()["label"]

        return label

    def _installActionGenerateDocument(self) -> tuple[bool, str]:
        """
        Install the Generate Document custom action into Clio Manage.
        It is assumed that the user has not already installed the custom action.

        ### Returns:
        - tuple of (True, "Installed") if the installation was successful, (False, reason) otherwise
        """
        headers = {
            "Authorization": f"{self._authorizationBlankHeader} {self._token}",
        }
        data = {
            "data": {
                "label": "Generate Document",
                "target_url": f"{self._redirectBaseUrl}/custom_actions/generate_document",  # TODO: proper URL
                "ui_reference": "matters/show",
            }
        }
        response = requests.post(f"{self._baseUrl}/custom_actions.json", data=data, headers=headers)
        handledReponse = self._handleRequest(response)  # expect "201 Created" response

        if handledReponse[0]:
            # There should not be any repeated id's. If there is we have old data
            self.userInstalledCustomActions[response.json()["id"]] = Clio.CustomAction.GENERATE_DOCUMENT

        return handledReponse

    def _removeActionGenerateDocument(self) -> tuple[bool, str]:
        """
        Remove the Generate Document custom action from Clio Manage.
        It is assumed that the custom action is installed.

        ### Returns:
        - tuple of (True, "Removed") if the removal was successful, (False, reason) otherwise
        """
        headers = {
            "Authorization": f"{self._authorizationBlankHeader} {self._token}",
        }

        id = None
        for action in self.userInstalledCustomActions.items():
            if action[1] == Clio.CustomAction.GENERATE_DOCUMENT:
                id = action[0]
                break

        if self.getCustomAction(id) != "Generate Document":
            self.userInstalledCustomActions.pop(id)  # remove bad record
            return (False, "We have invalid ID for \"Generate Document\" custom action!")

        response = requests.delete(f"{self._baseUrl}/custom_actions/{id}.json", headers=headers)
        handledResponse = self._handleRequest(response)  # expect "204 No Content"

        if handledResponse[0]:
            self.userInstalledCustomActions.pop(id)

        return handledResponse

    def handleCustomActions(self, params: dict) -> dict:
        """
        Handles the reception of a custom action request.

        ### Args:
        - params: the parameters of the custom action
            - custom_action_id: the id of the custom action
            - user_id: the id of the user
            - subject_url: the record from which the custom action was triggered
            - custom_action_nonce: single-use nonce to verify the authenticity of the request

        ### Returns:
        - the response of the custom action
        """
        # verify the nonce
        # parse the subject_url based on the custom_action_id
        pass

    # Hidden API Wrapper Methods
    # TODO: Consider adding rate limiting (monitoring the headers of the response)
    def _makeCall(self, method: str, path: str, data: dict = None) -> dict:
        """
        Make a Clio API call.

        ### Args:
        - method: the HTTP method
        - ...
        """
        pass

    def _handleRequest(self, response: requests.Response) -> tuple[bool, str]:
        """
        Handle the response from the Clio API.

        ### Args:
        - response: the response from the Clio API

        ### Returns:
        - tuple of (True, "Success") if the response was successful, (False, reason) otherwise
        """
        pass

    # API GET Methods

