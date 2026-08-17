"""Calendarific API client and holiday cache."""
from datetime import datetime, date
import json
import logging

import requests

_LOGGER = logging.getLogger(__name__)


class calendarificAPI:
    api_key = None

    def __init__(self, api_key):
        self.api_key = api_key

    def holidays(self, parameters):
        url = 'https://calendarific.com/api/v2/holidays?'

        if 'api_key' not in parameters:
            parameters['api_key'] = self.api_key

        response = requests.get(url, params=parameters);
        data     = json.loads(response.text)

        if response.status_code != 200:
            if 'error' not in data:
                data['error'] = 'Unknown error.'

        return data


def fetch_holiday_names(api_key, country, state):
    """Fetch the list of holiday names available for a country/state, or [] on error."""
    params = {'country': country, 'year': date.today().year, 'location': state}
    response = calendarificAPI(api_key).holidays(params)
    if 'error' in response:
        return []
    return [item['name'] for item in response['response']['holidays']]


class CalendarificApiReader:

    def __init__(self, api_key, country, state):
        self._country = country
        self._state = state
        self._api_key = api_key
        self._lastupdated = None
        _LOGGER.debug("apiReader loaded")
        self._holidays = []
        self._next_holidays = []
        self._error_logged = False
        self.update()

    def get_state(self):
        return "new"

    def get_date(self,holiday_name):
        try:
            today = date.today()
            holiday_datetime = next(i for i in self._holidays if i['name'] == holiday_name)['date']['datetime']
            testdate = date(holiday_datetime['year'],holiday_datetime['month'],holiday_datetime['day'])
            if testdate < today:
                holiday_datetime = next(i for i in self._next_holidays if i['name'] == holiday_name)['date']['datetime']
                testdate = date(holiday_datetime['year'],holiday_datetime['month'],holiday_datetime['day'])
            return testdate
        except:
            return "-"

    def get_description(self,holiday_name):
        try:
            return next(i for i in self._holidays if i['name'] == holiday_name)['description']
        except:
            return "NOT FOUND"

    def get_holidays(self):
        return [item['name'] for item in self._holidays]

    def update(self):
        if self._lastupdated == datetime.now().date():
            return
        self._lastupdated = datetime.now().date()
        year = date.today().year
        params = {'country': self._country,'year': year,'location': self._state}
        calapi = calendarificAPI(self._api_key)
        response = calapi.holidays(params)
        _LOGGER.debug("Updating from Calendarific api")
        if 'error' in response:
            if not self._error_logged:
                _LOGGER.error(response['meta']['error_detail'])
                self._error_logged = True
            return
        self._holidays = response['response']['holidays']
        params['year'] = year + 1
        response = calapi.holidays(params)
        if 'error' in response:
            if not self._error_logged:
                _LOGGER.error(response['meta']['error_detail'])
                self._error_logged = True
            return
        self._error_logged = False
        self._next_holidays = response['response']['holidays']

        return True
