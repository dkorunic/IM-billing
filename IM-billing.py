#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-

"""InfoMAR Google calendar billing/time tracking software
"""

__copyright__ = """Copyright (C) 2011  Dinko Korunic, InfoMAR

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

__version__ = '$Id: IM-billing.py,v ae84f692f79e 2012/02/07 11:02:40 dinko $'

import getopt
import sys
import string
import time
import math
import dateutil
import dateutil.parser
import dateutil.tz
try:
    from xml.etree import ElementTree
except ImportError:
    from elementtree import ElementTree
import gdata.calendar.data
import gdata.calendar.client
import gdata.calendar.service
import gdata.acl.data
import atom


class IMBilling:
    def __init__(self, email, password):
        # usual Google API init
        self.calendar_service = gdata.calendar.service.CalendarService()
        self.calendar_service.email = email
        self.calendar_service.password = password
        self.calendar_service.source = __version__
        self.calendar_service.ProgrammaticLogin()

    def _GetCalID(self, calendar):
        # extract Google Calendar ID: seems like a total hack, but there
        # is no other way using Google API itself
        if calendar == 'default' or calendar == 'primary':
            return 'default'
        feed = self.calendar_service.GetAllCalendarsFeed()
        calID = 'default'

        # parse all calendars and get the one we need
        for i, a_calendar in zip(xrange(len(feed.entry)), feed.entry):
            if (a_calendar.title.text == calendar):
                calID = '%s' % a_calendar.GetEditLink().href.split('/')[8]
                # recode back HTML special characters
                calID = calID.replace('%40','@').replace('%23','#')
                break
        return calID

    def _ParseAndSummarize(self, calendar, start_min, start_max,
            hourly_rate):
        # empty daily work dict
        work_period = dict()

        # Google Calendar init
        self._GetCalID(calendar)
        query = gdata.calendar.service.CalendarEventQuery( \
                self._GetCalID(calendar),
                'private', 'full')
        query.max_results = 10000

        # prepare start/end dates
        time_format = '%Y-%m-%d'
        if start_min is None:
            # return work in last 60 days
            query.start_min = time.strftime(time_format,
                    time.gmtime(time.time() - 86400 * 60))
        else:
            query.start_min = start_min
        if start_max is None:
            # end time is now!
            query.start_max = time.strftime(time_format,
                    time.gmtime(time.time()))
        else:
            query.start_max = start_max

        # fugly fixups
        query.start_min = '%sT00:00:00' % query.start_min
        query.start_max = '%sT23:59:59' % query.start_max

        # print headers
        print 'Listing work done on %s project from %s to %s' % \
                (calendar, query.start_min, query.start_max)

        # implement basic sanity bound checking
        real_start_max = dateutil.parser.parse(query.start_max).replace(tzinfo=dateutil.tz.tzlocal())
        real_start_min = dateutil.parser.parse(query.start_min).replace(tzinfo=dateutil.tz.tzlocal())

        # execute the query
        feed = self.calendar_service.CalendarQuery(query)

        # parse each of the responses
        workday_output_format = '%04d-%02d-%02d'
        for i, an_event in zip(xrange(len(feed.entry)), feed.entry):

            # parse individual event entries
            for a_when in an_event.when:
                # event desc
                description = an_event.title.text

                # ISO8601 parsing might not work with Python3
                start_date = dateutil.parser.parse(a_when.start_time)
                end_date = dateutil.parser.parse(a_when.end_time)

                if start_date < real_start_min or start_date > real_start_max:
                    print 'Oops, got date out of bounds! Start:', \
                        start_date, 'End:', end_date
                    continue

                # time calculations
                current_date = workday_output_format % (start_date.year,
                        start_date.month, start_date.day)
                time_delta = end_date - start_date
                minute_sum = time_delta.days * 1440 + \
                    time_delta.seconds / 60 + \
                    time_delta.microseconds / 60000000

                # build dictionary of day work with descriptions and hour
                # sum
                if not current_date in work_period:
                    work_period[current_date] = (minute_sum, description)
                else:
                    old_sum, old_description = work_period[current_date]
                    description = ', '.join([old_description, description])
                    minute_sum += old_sum
                    work_period[current_date] = (minute_sum, description)

        # print individual daily results
        total_sum = 0
        workdays = 0
        print '%s\t\t%s\t%s' % ('Date', 'Hours', 'Description')
        for i in sorted(work_period.iterkeys()):
            minute_sum, description = work_period[i]
            daily_sum = math.ceil(float(minute_sum) / 60)
            if daily_sum > 24:
                daily_sum = 24
            total_sum += daily_sum
            workdays += 1
            print '%s\t%d\t%s' % (i, daily_sum, description)

        # print final sums
        print 'Total workhour sum for given period:\t\t%d hours' % total_sum
        print 'Total active days for given period:\t\t%d days' % workdays
        if hourly_rate is not None:
            print 'Cumulative price for given period:\t\t%.2f units' % \
                    (total_sum * float(hourly_rate))

    def Run(self, calendar, start_min, start_max, hourly_rate):
        self._ParseAndSummarize(calendar, start_min, start_max,
                hourly_rate)

def usage():
    print 'python IM-billing.py --user username --pw password ' \
            '--calendar calendar_name [ --start YYYY-MM-DD ] ' \
            '[ --end YYYY-MM-DD ] [ --rate rate_per_hour ]'
    sys.exit(2)

def main():
    # parse command line options
    try:
        opts, args = getopt.getopt(sys.argv[1:], '', ['user=', 'pw=',
            'calendar=', 'start=', 'end=', 'rate='])
    except getopt.error, msg:
        usage()

    user = None
    pw = None
    calendar = None
    start = None
    end = None
    rate = None

    # Process options
    for o, a in opts:
        if o == '--user':
            user = a
        elif o == '--pw':
            pw = a
        elif o == '--calendar':
            calendar = a
        elif o == '--start':
            start = a
        elif o == '--end':
            end = a
        elif o == '--rate':
            rate = a

    if pw is None:
        import getpass
        pw = getpass.getpass()

    if user is None or pw is None or calendar is None:
        usage()

    billing = IMBilling(user, pw)
    billing.Run(calendar, start, end, rate)

if __name__ == '__main__':
    try:
        import psyco
        psyco.full()
    except ImportError:
        pass
    main()
