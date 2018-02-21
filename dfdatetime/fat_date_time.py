# -*- coding: utf-8 -*-
"""FAT date time implementation."""

from __future__ import unicode_literals

from dfdatetime import definitions
from dfdatetime import interface


class FATDateTimeEpoch(interface.DateTimeEpoch):
  """FAT date time time epoch."""

  def __init__(self):
    """Initializes a FAT date time epoch."""
    super(FATDateTimeEpoch, self).__init__(1980, 1, 1)


class FATDateTime(interface.DateTimeValues):
  """FAT date time.

  The FAT date time is mainly used in DOS/Windows file formats and FAT.

  The FAT date and time is a 32-bit value containing two 16-bit values:
    * The date (lower 16-bit).
      * bits 0 - 4: day of month, where 1 represents the first day
      * bits 5 - 8: month of year, where 1 represent January
      * bits 9 - 15: year since 1980
    * The time of day (upper 16-bit).
      * bits 0 - 4: seconds (in 2 second intervals)
      * bits 5 - 10: minutes
      * bits 11 - 15: hours

  The FAT date time has no time zone information and is typically stored
  in the local time of the computer.

  Attributes:
    is_local_time (bool): True if the date and time value is in local time.
    precision (str): precision of the date and time value, which should
        be one of the PRECISION_VALUES in definitions.
  """

  _EPOCH = FATDateTimeEpoch()

  # The difference between Jan 1, 1980 and Jan 1, 1970 in seconds.
  _FAT_DATE_TO_POSIX_BASE = 315532800

  def __init__(self, fat_date_time=None):
    """Initializes a FAT date time.

    Args:
      fat_date_time (Optional[int]): FAT date time.
    """
    number_of_seconds = None
    if fat_date_time is not None:
      number_of_seconds = self._GetNumberOfSeconds(fat_date_time)

    super(FATDateTime, self).__init__()
    self._number_of_seconds = number_of_seconds
    self.precision = definitions.PRECISION_2_SECONDS

  def _GetNumberOfSeconds(self, fat_date_time):
    """Retrieves the number of seconds from a FAT date time.

    Args:
      fat_date_time (int): FAT date time.

    Returns:
      int: number of seconds since January 1, 1980 00:00:00.

    Raises:
      ValueError: if the month, day of month, hours, minutes or seconds
          value is out of bounds.
    """
    day_of_month = (fat_date_time & 0x1f)
    month = ((fat_date_time >> 5) & 0x0f)
    year = (fat_date_time >> 9) & 0x7f

    days_per_month = self._GetDaysPerMonth(year, month)
    if day_of_month < 1 or day_of_month > days_per_month:
      raise ValueError('Day of month value out of bounds.')

    number_of_days = self._GetDayOfYear(1980 + year, month, day_of_month)
    number_of_days -= 1
    for past_year in range(0, year):
      number_of_days += self._GetNumberOfDaysInYear(past_year)

    fat_date_time >>= 16

    seconds = (fat_date_time & 0x1f) * 2
    minutes = (fat_date_time >> 5) & 0x3f
    hours = (fat_date_time >> 11) & 0x1f

    if hours not in range(0, 24):
      raise ValueError('Hours value out of bounds.')

    if minutes not in range(0, 60):
      raise ValueError('Minutes value out of bounds.')

    if seconds not in range(0, 60):
      raise ValueError('Seconds value out of bounds.')

    number_of_seconds = (((hours * 60) + minutes) * 60) + seconds
    number_of_seconds += number_of_days * definitions.SECONDS_PER_DAY
    return number_of_seconds

  def CopyFromDateTimeString(self, time_string):
    """Copies a FAT date time from a date and time string.

    Args:
      time_string (str): date and time value formatted as:
          YYYY-MM-DD hh:mm:ss.######[+-]##:##

          Where # are numeric digits ranging from 0 to 9 and the seconds
          fraction can be either 3 or 6 digits. The time of day, seconds
          fraction and time zone offset are optional. The default time zone
          is UTC.

    Raises:
      ValueError: if the time string is invalid or not supported.
    """
    date_time_values = self._CopyDateTimeFromString(time_string)

    year = date_time_values.get('year', 0)
    month = date_time_values.get('month', 0)
    day_of_month = date_time_values.get('day_of_month', 0)
    hours = date_time_values.get('hours', 0)
    minutes = date_time_values.get('minutes', 0)
    seconds = date_time_values.get('seconds', 0)

    if year < 1980 or year > (1980 + 0x7f):
      raise ValueError('Year value not supported: {0!s}.'.format(year))

    self._number_of_seconds = self._GetNumberOfSecondsFromElements(
        year, month, day_of_month, hours, minutes, seconds)
    self._number_of_seconds -= self._FAT_DATE_TO_POSIX_BASE

    self.is_local_time = False

  def CopyToStatTimeTuple(self):
    """Copies the FAT date time to a stat timestamp tuple.

    Returns:
      tuple[int, int]: a POSIX timestamp in seconds and the remainder in
          100 nano seconds or (None, None) on error.
    """
    if self._number_of_seconds is None or self._number_of_seconds < 0:
      return None, None

    timestamp = self._number_of_seconds + self._FAT_DATE_TO_POSIX_BASE
    return timestamp, None

  def CopyToDateTimeString(self):
    """Copies the FAT date time to a date and time string.

    Returns:
      str: date and time value formatted as:
          YYYY-MM-DD hh:mm:ss
    """
    if self._number_of_seconds is None:
      return

    number_of_days, hours, minutes, seconds = self._GetTimeValues(
        self._number_of_seconds)

    year, month, day_of_month = self._GetDateValuesWithEpoch(
        number_of_days, self._EPOCH)

    return '{0:04d}-{1:02d}-{2:02d} {3:02d}:{4:02d}:{5:02d}'.format(
        year, month, day_of_month, hours, minutes, seconds)

  def GetDate(self):
    """Retrieves the date represented by the date and time values.

    Returns:
       tuple[int, int, int]: year, month, day of month or (None, None, None)
           if the date and time values do not represent a date.
    """
    if self._number_of_seconds is None:
      return None, None, None

    try:
      number_of_days, _, _, _ = self._GetTimeValues(self._number_of_seconds)
      return self._GetDateValuesWithEpoch(number_of_days, self._EPOCH)

    except ValueError:
      return None, None, None

  def GetPlasoTimestamp(self):
    """Retrieves a timestamp that is compatible with plaso.

    Returns:
      int: a POSIX timestamp in microseconds or None on error.
    """
    if self._number_of_seconds is None or self._number_of_seconds < 0:
      return

    return definitions.MICROSECONDS_PER_SECOND * (
        self._number_of_seconds + self._FAT_DATE_TO_POSIX_BASE)
