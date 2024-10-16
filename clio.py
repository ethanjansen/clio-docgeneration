from enum import Enum
import requests
from urllib import urlencode
import json
import random
import string
from datetime import datetime, timedelta, timezone
import re


# Clio Client
class Clio:
    # Enums/Constants/Types
    class CustomAction(Enum):
        GENERATE_DOCUMENT = 1
        # IMPORT_MATTER_FROM_GOOGLE_FORMS = 2 #NYI

    class Address:
        def __init__(self, street: str, city: str, state: str, zipcode: str, country: str, name: str = "Other"):
            self.street = street
            self.city = city
            self.state = state
            self.zipcode = zipcode
            self.country = country
            self.name = name.capitalize()

            if self.name not in {"Work", "Home", "Billing"}:
                self.name = "Other"

        def _propercase(self, string: str) -> str:  # this will work for most things in an address
            return ' '.join(word[0].upper() + word[1:] for word in string.split())

        def fixCase(self) -> None:
            """
            Iterates over self fixing the case of street, city, state, and country.
            Does not remove existing capitalization, but capitalizes the first letter of each word.
            Also removes repeated spaces.
            """
            self.street = self._propercase(self.street)
            self.city = self._propercase(self.city)
            self.state = self._propercase(self.state)
            self.country = self._propercase(self.country)

    class Email:
        def __init__(self, email: str, isDefault: bool = True, name: str = "Other"):
            self.email = email  # could check if valid email?
            self.name = name.capitalize()
            self.default = isDefault

            if self.name not in {"Work", "Home"}:
                self.name = "Other"

    class phoneNumber:
        # accept both integer and string numbers
        def __init__(self, number, isDefault: bool = True, name: str = "Other"):
            self.default = isDefault
            self.name = name.capitalize()

            # assume US numbers
            if type(number) is str:
                self.number = int(re.sub("[^0-9]", "", number))
            if self.number < 9999999999:
                self.number += 10000000000

            if self.name not in {"Work", "Home", "Mobile", "Fax", "Pager", "Skype"}:
                self.name = "Other"

    class Contact:
        # requires at least first and last name
        def __init__(self, firstName: str, lastName: str, contactType: str = "Person",
                     middleName: str = None, title: str = None, addresses: list["Clio.Address"] = None,
                     company: int = None, customFields: dict[int, str] = None, dob: str = None,
                     emails: list["Clio.Email"] = None, phoneNumbers: list["Clio.phoneNumber"] = None,
                     id: int = None, etag: str = None):
            self.firstName = firstName
            self.lastName = lastName
            self.middleName = middleName
            self.title = title
            self.addresses = addresses
            self.company = company
            self.customFields = customFields
            self.dob = dob  # could make this date type?
            self.emails = emails
            self.phoneNumbers = phoneNumbers
            self.id = id
            self.etag = etag

            self.contactType = contactType.capitalize()
            if self.contactType != "Person":
                self.contactType = "Company"

        def toDict(self) -> dict:
            """
            Create a dictionary of Contact compatible with Clio API.
            Does not include members that are None.

            ### Returns:
            - dictionary of contact
            """
            addressDicts = []
            emailDicts = []
            phoneDicts = []
            customFieldDicts = []

            for address in self.addresses:
                addressDict = address.toDict()
                if addressDict is not None:
                    addressDicts.append(addressDict)
            for email in self.emails:
                emailDict = email.toDict()
                if emailDict is not None:
                    emailDicts.append(emailDict)
            for phone in self.phoneNumbers:
                phoneDict = phone.toDict()
                if phoneDict is not None:
                    phoneDicts.append(phoneDict)

            for customField in self.customFields.items():
                customFieldDicts.append(
                    {
                        "value": customField[1],
                        "custom_field": {
                            "id": customField[0],
                        },
                    }
                )

            dictionary = {
                    "id": self.id,
                    "etag": self.etag,
                    "firt_name": self.firstName,
                    "last_name": self.lastName,
                    "type": self.contactType,
                    "middle_name": self.middleName,
                    "title": self.title,
                    "company": self.company,
                    "date_of_birth": self.dob,
                    "addresses": addressDicts,
                    "email_addresses": emailDicts,
                    "phone_numbers": phoneDicts,
                    "custom_field_values": customFieldDicts,
            }

            for key, value in dictionary.items():
                if value is None or value.len() == 0:
                    dictionary.pop(key)

            return dictionary

    # Class Variables
    _baseUrl = "https://app.clio.com/api/v4"
    _oauthBaseUrl = "https://app.clio.com/oauth"
    _redirectBaseUrl = "http://127.0.0.1"
    _authorizationBlankHeader = "Authorization: Bearer"

    # Constructor
    def __init__(self, clientId: str, clientSecret: str, refreshToken: str = None, userInstalledCustomActions: dict[int, "Clio.CustomAction"] = None):
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
    def installCustomActions(self, customActions: set["Clio.CustomAction"]) -> dict[str, list[tuple["Clio.CustomAction", str]]]:
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

    def removeCustomActions(self, customActions: set["Clio.CustomAction"]) -> dict[str, list[tuple["Clio.CustomAction", str]]]:
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
            label = response.json()["data"]["label"]

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
            self.userInstalledCustomActions[response.json()["data"]["id"]] = Clio.CustomAction.GENERATE_DOCUMENT

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

    def getAllContacts(self) -> dict:
        """
        Get all contacts in Clio. Will likely be used for updating internal database.
        Required for getting specific contact, as id is needed.
        Does not yet include any filtering support (TODO).

        ### Returns:
        - contact list dictionary
        """
        headers = {
            "Authorization": f"{self._authorizationBlankHeader} {self._token}",
        }
        params = {
            # "fields": "",  # include only certain fields - keep this short for ALL: name, email, address, DOB, type, client?, phone, folder, etag
            # "order": "",  # likely order by id for ALL which is default
            # "query": "",  # some future query parameter support
            # "type": "person",  # only include people, not companies
            # "updated_since": "ISO-8601 timestamp",  # for updating records efficiently
            # "client_only": true,  # only include clients
            # "email_only": true,  # only include contacts with an email on file
        }
        response = requests.get(f"{self._baseUrl}/contacts.json", headers=headers, params=params)  # expect "200 Ok"
        self._handleRequest(response)
        # do something useful here...
        return response.json()

    def getContact(self, id: int) -> dict:
        """
        Get detailed information about Clio contact related to id.
        Does not yet include querying specific parameters (TODO).
        Includes these parameters by default: (TODO)

        ### Args:
        - id of contact

        ### Returns:
        - contact dictionary
        """
        headers = {
            "Authorization": f"{self._authorizationBlankHeader} {self._token}",
            # "IF-MODIFIED-SINCE": "RFC 2822 timestamp",  # return 304 if not modified since last query (store locally)
            # "IF-NONE-MATCH": "ETag",  # return 304 if Etag does not different from local store
        }
        params = {
            # "fields": "",  # include relevant fields for document generation
            # "custom_field_ids": [],  # get specific custom fields (this requires querying custom fields separately - Not Implemented)
        }
        response = requests.get(f"{self._baseUrl}/contacts/{id}.json", headers=headers, params=params)  # expect "200 Ok"
        self._handleRequest(response)
        # do something useful...
        return response.json()

    def createContact(self, contactData: "Clio.Contact") -> int:
        """
        Create a new contact based on contactData.
        Use updateContact() instead if contact already exists.

        ### Args:
        - contactData: contact instance to add to Clio

        ### Returns:
        - id on success, negative on failure
        """
        if contactData.id is not None or contactData.etag is not None:
            # contact already exists
            return -1

        headers = {
            "Authorization": f"{self._authorizationBlankHeader} {self._token}",
        }
        response = requests.post(f"{self._baseUrl}/contacts.json", headers=headers, data=contactData.toDict())
        self._handleRequest(response)

        if response.status_code != 201:
            return -2
        responseData = response.json()["data"]
        newId = responseData["id"]
        newEtag = responseData["etag"]
        contactData.id = newId
        contactData.etag = newEtag
        return newId  # not returning etag

    def upateContact(self, contactData: "Clio.Contact", overwrite: bool = False) -> int:
        """
        Update a contact based on contactData.
        Use createContact() if contact does not already exist.

        ### Args:
        - contactData: contact instance to update in Clio.
        - overwrite: if True update contact without checking etag, on false check etag -- if no match contact was updated elsewhere, do nothing.

        ### Returns:
        - id on success, negative on failure
        """
        if contactData.id is None:
            # contact does not exist, or we do not know what to update
            return -1
        if contactData.etag is None and (not overwrite):
            # we do not have a current etag, so cannot perform check
            return -3

        headers = {
            "Authorization": f"{self._authorizationBlankHeader} {self._token}",
        }
        if not overwrite:
            headers["IF-MATCH"]: contactData.etag
        response = requests.post(f"{self._baseUrl}/contacts/{contactData.id}.json", headers=headers, data=contactData.toDict())
        self._handleRequest(response)

        if response.status_code != 200:
            return -2
        responseData = response.json()["data"]
        contactData.etag = responseData["etag"]
        return responseData["id"]

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

