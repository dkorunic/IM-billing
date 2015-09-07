#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

"""InfoMAR Google calendar billing/time tracking software
"""

__copyright__ = """Copyright (C) 2014  Dinko Korunic, InfoMAR

This program is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation; either version 2 of the License, or (at your
option) any later version.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License along
with this program; if not, write to the Free Software Foundation, Inc.,
59 Temple Place, Suite 330, Boston, MA  02111-1307 USA
"""

__program__ = 'IM-billing'
__version__ = '1.3'
__author__ = 'Dinko Korunic'

__readme__ = """
Installation:
    pip install --upgrade python-dateutil oauth2client \
            google-api-python-client python-gflags
"""

import os
import getopt
import sys
import math
import datetime
import dateutil
import dateutil.parser
import dateutil.tz
import dateutil.relativedelta

import httplib2
import oauth2client.file
import oauth2client.client
import oauth2client.tools

import apiclient.discovery


__API_CLIENT_ID__ = '719895376614-sgqd9vhln9837rj7p8o347cl18ducrhn.apps.googleusercontent.com'
__API_CLIENT_SECRET__ = 'SgMphHLlmUb8HkvM6sowTW8Q'
__API_CLIENT_SCOPE__ = 'https://www.googleapis.com/auth/calendar'
sort_order = {'owner': 1, 'writer': 2,
              'reader': 3, 'freeBusyReader': 4}


class IMBilling(object):
    """
    IM Billing class.

    :param client_id: Google API Client ID (application specific)
    :param client_secret: Google API Client Secret (application specific)
    :param client_scope: Google API Client Scope
    """

    def __init__(self, client_id=__API_CLIENT_ID__, client_secret=__API_CLIENT_SECRET__,
                 client_scope=__API_CLIENT_SCOPE__):
        self.client_id = client_id
        self.client_secret = client_secret
        self.client_scope = client_scope
        self.auth = None
        self.calendar_service = None
        self.calendars = self._get_calendars()

    def _get_calendars(self):
        """
        Gets a list of all available Google calendars, sorted by sort_order (owner, writer, reader, freeBusyReader).

        :return: a list of calendars
        """
        calendar_list = self._calendar_service().calendarList().list().execute()
        all_calendars = []

        while True:
            for cal in calendar_list['items']:
                all_calendars.append(cal)
            page_token = calendar_list.get('nextPageToken')

            if page_token:
                calendar_list = self._calendar_service().calendarList().list().execute()
            else:
                break

        all_calendars.sort(lambda x, y: cmp(sort_order[x['accessRole']], sort_order[y['accessRole']]))

        return all_calendars

    def _get_cal_id(self, calendar):
        """
        Gets a specific Google calendar ID for a first found string match.

        :param calendar: string containing calendar name
        :return: Google calendar ID
        """
        for cal in self.calendars:
            if cal['summary'].lower() == calendar.lower():
                return cal['id']

        return None

    def _google_auth(self):
        """
        Performs a OAuth authentication and reuses existing credentials if possible

        :return: OAuth authentication token
        """
        if self.auth:
            return self.auth

        storage = oauth2client.file.Storage(os.path.expanduser('~/.IM-billing.oauth'))
        credentials = storage.get()

        if credentials is None or True == credentials.invalid:
            user_agent = ''.join([__program__, '/', __version__])
            flow = oauth2client.client.OAuth2WebServerFlow(client_id=self.client_id, client_secret=self.client_secret,
                                                           scope=[self.client_scope], user_agent=user_agent)
            credentials = oauth2client.tools.run(flow, storage)
        self.auth = credentials.authorize(httplib2.Http())

        return self.auth

    def _calendar_service(self):
        """
        Initializes Calendar Service

        :return: fully initialized Calendar Service for v3 API
        """
        if not self.calendar_service:
            self.calendar_service = apiclient.discovery.build(serviceName='calendar',
                                                              version='v3', http=self._google_auth())

        return self.calendar_service

    @staticmethod
    def _parse_events(events_list):
        """
        Gets all Google Calendar events as individual items, gets and parses timestamps. Produces sums for each day with
        concatenated summaries.

        :param events_list: array of events by pages
        :return: dictionary contaning per-day work summaries
        """
        daily_work_summary = dict()

        for event_group in events_list:
            if 'items' not in event_group:
                break

            for event in event_group['items']:
                if 'status' in event and event['status'] == 'cancelled':
                    continue

                if 'dateTime' in event['start']:
                    start = event['start']['dateTime']
                else:
                    start = event['start']['date']
                if 'dateTime' in event['end']:
                    end = event['end']['dateTime']
                else:
                    end = event['end']['date']

                if 'description' in event:
                    desc = event['description'].strip()
                elif 'summary' in event:
                    desc = event['summary'].strip()
                else:
                    desc = 'unknown'

                # ISO8601 parsing might not work with Python3
                start_date = dateutil.parser.parse(start)
                end_date = dateutil.parser.parse(end)

                # time calculations
                current_date = start_date.date().isoformat()

                time_delta = end_date - start_date
                minute_sum = time_delta.days * 1440 + time_delta.seconds / 60 + time_delta.microseconds / 60000000

                # build dictionary of day work with descriptions and hour
                # sum
                if current_date not in daily_work_summary:
                    daily_work_summary[current_date] = (minute_sum, desc)
                else:
                    old_sum, old_desc = daily_work_summary[current_date]
                    desc = ', '.join([old_desc, desc])
                    minute_sum += old_sum
                    daily_work_summary[current_date] = (minute_sum, desc)

        return daily_work_summary

    def _get_events(self, calendar_id, start, end):
        """
        Gets all possible events within a timeframe defined by (start, end) for a given calendar, page by page.

        :param calendar_id: calendar ID for a specific calendar
        :param start: start timestamp in RFC3339 format
        :param end: end timestamp in RFC3339 format
        :return:
        """
        events_list = []
        event_result = None

        while True:
            if event_result is None:
                event_result = self._calendar_service().events().list(calendarId=calendar_id, timeMin=start,
                                                                      timeMax=end,
                                                                      singleEvents=True).execute()
                events_list.append(event_result)
            else:
                page_token = event_result.get('nextPageToken')
                if page_token:
                    event_result = self._calendar_service().events().list(calendarId=calendar_id,
                                                                          pageToken=page_token).execute()
                    events_list.append(event_result)
                else:
                    break

        return events_list

    @staticmethod
    def _get_start_end(start_min, end_max):
        """
        Returns start and end timestamps in RFC3339 format. If start is empty, then use -1 month ago. If end is empty,
        use current timestamp.

        :param start_min: start of search query criteria in any format
        :param end_max: end of search query criteria in any format
        :return: returns array with start and end timestamps in RFC3339 format
        """
        if start_min is None:
            # last month
            start_tmp = datetime.datetime.now() - dateutil.relativedelta.relativedelta(months=1)
        else:
            start_tmp = dateutil.parser.parse(start_min)

        if end_max is None:
            # today!
            end_tmp = datetime.datetime.now()
        else:
            end_tmp = dateutil.parser.parse(end_max)

        # conform to RFC3339 and add local timezones if needed
        a = [x.replace(tzinfo=dateutil.tz.gettz()) if x.tzinfo is None else x for x in start_tmp, end_tmp]
        a = [x.isoformat() for x in a]

        return a

    @staticmethod
    def _print_sums(daily_work_summary, hourly_rate):
        # print individual daily results
        """
        Agregates hourly wages and prints daily work summaries

        :param daily_work_summary: already parsed daily aggregated events
        :param hourly_rate: hourly rate in any unit
        """
        total_sum = 0
        workdays = 0

        print '%s\t\t%s\t%s' % ('Date', 'Hours', 'Description')

        for i in sorted(daily_work_summary.iterkeys()):
            minute_sum, description = daily_work_summary[i]
            daily_sum = math.ceil(float(minute_sum) / 60.)
            if daily_sum > 24:
                daily_sum = 24
            total_sum += daily_sum
            workdays += 1
            print '%s\t%d\t%s' % (i, daily_sum, description.encode('UTF-8', errors='ignore'))

        # print final sums
        print '\nTotal workhour sum for given period:\t\t%d hours\n' \
              'Total active days for given period:\t\t%d days' % (total_sum, workdays)

        if hourly_rate is not None:
            print 'Cumulative price for given period:\t\t%.2f units' % \
                  (total_sum * float(hourly_rate))


    def run(self, calendar, start_min, end_max, hourly_rate):
        # get Google Calendar ID
        """
        Main class entry point.

        :param calendar: calendar name/description as a string
        :param start_min: start query/search criteria as a string in any format
        :param end_max: end query/search criteria as a string in any format
        :param hourly_rate: hourly wage/rate in any unit
        """
        calendar_id = self._get_cal_id(calendar)

        # localize and calculate start and end timestamps
        start_iso, end_iso = self._get_start_end(start_min, end_max)

        print 'Listing work done on %s project from %s to %s' % (calendar, start_min, end_max)

        events_list = self._get_events(calendar_id, start_iso, end_iso)
        daily_work_summary = self._parse_events(events_list)
        self._print_sums(daily_work_summary, hourly_rate)


def usage():
    """
    Print usage.
    """
    print 'python IM-billing.py --calendar calendar_name [ --start YYYY-MM-DD ] ' \
          '[ --end YYYY-MM-DD ] [ --rate rate_per_hour ]'
    print 'Please note that --end is exclusive, while --start is inclusive.'
    sys.exit(2)


def main():
    """
    Default code entrypoint.
    """
    opts = None
    # noinspection PyUnusedLocal
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', ['calendar=', 'start=', 'end=', 'rate='])
    except getopt.error, msg:
        usage()

    calendar = None
    start = None
    end = None
    rate = None

    # Process options
    for o, a in opts:
        if o == '--calendar':
            calendar = a
        elif o == '--start':
            start = a
        elif o == '--end':
            end = a
        elif o == '--rate':
            rate = a

    if calendar is None:
        usage()

    billing = IMBilling()
    billing.run(calendar, start, end, rate)


if __name__ == '__main__':
    main()
