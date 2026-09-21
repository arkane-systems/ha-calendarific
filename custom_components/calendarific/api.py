"""Calendarific API client and holiday cache."""
from datetime import date
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

    def __init__(self, api_key, country, state, today=None):
        self._country = country
        self._state = state
        self._api_key = api_key
        self._lastupdated = None
        _LOGGER.debug("apiReader loaded")
        self._holidays = []
        self._next_holidays = []
        self._error_logged = False
        self.update(today)

    def get_state(self):
        return "new"

    def get_date(self, holiday_name, today=None):
        # today is caller-supplied so HA-aware callers can pass a timezone-correct
        # "today" (see sensor.py) instead of the system clock's local date, which
        # is often UTC and would roll the day over at the wrong wall-clock time.
        today = today or date.today()
        try:
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

    def get_next_holiday(self, holiday_names, today=None):
        """Return (name, date) of the soonest occurrence among holiday_names, or (None, None).

        Ties (same date) break on name, for a deterministic result. today
        follows the same caller-supplied convention as get_date() - see the
        comment there.
        """
        today = today or date.today()
        candidates = []
        for name in holiday_names:
            holiday_date = self.get_date(name, today)
            if holiday_date != "-":
                candidates.append((holiday_date, name))
        if not candidates:
            return (None, None)
        holiday_date, name = min(candidates)
        return (name, holiday_date)

    def get_holidays(self):
        return [item['name'] for item in self._holidays]

    def update(self, today=None):
        today = today or date.today()
        if self._lastupdated == today:
            return
        self._lastupdated = today
        year = today.year
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
