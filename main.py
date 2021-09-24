"""
# Notes
## Links
 - https://www.daysoftheyear.com/days/2021/08/02/
 - https://nationaldaycalendar.com/what-day-is-it/
 - https://whatnationaldayisit.com/today/
  - Seems non-functional
- https://en.wikipedia.org/wiki/August_2
- https://www.onthisday.com/today/events.php
- http://news.bbc.co.uk/onthisday/hi/dates/stories/august/2/default.stm
- https://learning.blogs.nytimes.com/on-this-day/august-2
## Types and priority
- Types:
  - National/international days and celebrations
  - Events on this day
  - Births/deaths
- Priority
  - Try and select national/international days first, then events on this day
  - I'm not good at parsing the births/deaths
  - Try and select positive things
## For automation
- Uri has some code to rank people by a wikipedia fame metric
  - Here's Uri's wiki code: https://github.com/Udzu/pudzu/blob/master/wikipage.md
  - And his fame metric: https://github.com/Udzu/pudzu/blob/master/dataviz/wikiscrape.py#L43
  - An example in use: https://www.flickr.com/photos/zarfo/24073155478/in/album-72157688351121374/
- Might be good to do it on Telegram actually, so I can give it in standups where I run into the office
"""
import datetime
from functools import total_ordering
from ABC import ABC, abstractmethod

import requests
import dateutil
from bs4 import BeautifulSoup


class Source(ABC):
    @property
    def weight(self) -> int:
        """
        How to weight the source in the results. Smaller weights come first
        """
        return 10

    @abstractmethod
    def fetch_events(self, day: int, month: int, year: Optional[int] = None) -> List[Event]:
        raise NotImplementedError


class DaysOfTheYearSource(Source):
    url_format = "https://www.daysoftheyear.com/days/{year:04}/{month:02}/{day:02}/"

    def fetch_events(self, day: int, month: int, year: Optional[int] = None) -> List[Event]:
        date = datetime.date(year or datetime.date.today().year, month, day)
        if year is None and date < today:
            date += datetime.timedelta(years=1)
        url = self.url_format.format(year=date.year, month=date.month, day=date.day)
        resp = requests.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        day_cards = soup.find_all("div", attrs={"class": "card--day"})
        events = []
        for day_card in day_cards:
            card_date = day_card.find("div", attrs={"class": "card__date"}).find("div", attrs={"class": "date_day"})
            end_date = None
            if "-" in card_date.content:
                # <div class="date_day">Thu Sep 15th, 2022 - Sat Oct 15th, 2022</div>
                start, end = card_date.content.split("-")
                event_date = dateutil.parser.parse(start.strip()).date
                end_date = dateutil.parser.parse(end.strip()).date
            elif card_date.content.split() == 2:
                # <div class="date_day date_day_month">September, 2022</div>
                month, year = card_date.content.split(", ")
                month = datetime.datetime.strptime(month, "%b")
                event_date = datetime.datetime(year, month.month, 1)
                end_date = datetime.datetime(year, (month.month % 12) + 1, 1) - datetime.timedelta(days=1)
            else:
                # <div class="date_day">Tue Sep 20th, 2022</div>
                event_date = dateutil.parser.parse(card_date.content)
            card_title_tag = day_card.find("div", attrs={"class": "card__title"}).find("a")
            event_title = card_title_tag.content
            event_link = card_title_tag['href']
            event = Event(self, event_date, event_title, event_link, EventType.NATIONAL_DAY_OF_X, end_date)
            events.append(event)
        return events


class WikipediaSource(Source):
    api_format = "https://en.wikipedia.org/api/rest_v1/feed/onthisday/all/{month:02}/{day:02}"

    def fetch_events(self, day: int, month: int, year: Optional[int] = None) -> List[Event]:
        date = datetime.date(year or datetime.date.today().year, month, day)
        if year is None and date < today:
            date += datetime.timedelta(years=1)
        api_url = self.api_format.format(month=month, day=day)
        resp = requests.get(api_url)
        api_data = resp.json()
        all_events = []
        for birth_data in api_data['births']:
            all_events.append(Event(
                self,
                datetime.date(birth_data['year'], month, day),
                birth_data['text'],
                birth_data['pages'][0]['content_urls']['desktop']['page'],
                EventType.BIRTH
            ))
        for death_data in api_data['deaths']:
            all_events.append(Event(
                self,
                datetime.date(death_data['year'], month, day),
                death_data['text'],
                birth_data['pages'][0]['content_urls']['desktop']['page'],
                EventType.DEATH
            ))
        for event_data in api_data['events']:
            all_events.append(Event(
                self,
                datetime.date(event_data['year'], month, day),
                event_data['text'],
                event_data['pages'][0]['content_urls']['desktop']['page'],
                EventType.ON_THIS_DAY
            ))
        for holiday_data in api_data['holidays']:
            all_events.append(Event(
                self,
                datetime.date(date.year, month, day),
                holiday_data['text'],
                holiday_data['pages'][0]['content_urls']['desktop']['page'],
                EventType.HOLIDAY
            ))
        return all_events

class OnThisDayComSource(Source):
    # Highlights: https://www.onthisday.com/day/march/10
    # Events: https://www.onthisday.com/events/march/10
    # Births: https://www.onthisday.com/birthdays/march/10
    # Deaths: https://www.onthisday.com/deaths/march/10
    

@total_ordering
class Event:
    def __init__(
        self,
        source: 'Source',
        date: datetime.date,
        title: str,
        link: str,
        type: EventType,
        end_date: Optional[datetime.date] = None
    ) -> None:
        self.source = source
        self.date = date
        self.end_date = end_date or date
        self.title = title
        self.link = link
        self.type = type

    @property
    def is_single_day(self) -> bool:
        return self.end_date is None or self.date == self.end_date

    def __eq__(self, other) -> bool:
        if not isinstance(other, Event):
            return False
        return self.title == other.title and self.link == other.link

    def __str__(self) -> str:
        date_str = self.date.strftime("%Y-%m-%d")
        if not self.is_single_day:
            date_str += " - " + self.end_date.strftime("%Y-%m-%d")
        return f"{date_str}: {self.type.name}: {self.title} ({self.link})

    def __lt__(self, other) -> bool:
        if not isinstance(other, Event):
            return NotImplemented
        return self.order_index < other.order_index

    @property
    def order_index(self) -> List:
        """
        Returns a list to use when ordering events
        """
        # TODO: Maybe order births and deaths by notoriety
        # TODO: Maybe mix source and event rating
        # TODO: Rate events by sentiment analysis
        return [
            self.source.weight,  # Source weight first
            0 if self.is_single_day else 1,  # Single days should come before multi-day events
            self.date,  # Order by event date
            self.type.value,  # Order by event type
            self.title,  # Order by title
        ]


class EventType(Enum):
    NATIONAL_DAY = 10 # National day of whatever
    HOLIDAY = 20 # "holiday"
    ON_THIS_DAY = 30 # "on_this_day"
    BIRTH = 40 # "birth"
    DEATH = 41 # "death"


class EventCollector:
    def __init__(self) -> None:
        self.sources = [DaysOfTheYearSource()]

    def events_today(self) -> List[Event]:
        t_day = datetime.date.today()
        all_events = []
        for source in self.sources:
            all_events += source.fetch_events(t_day.day, t_day.month)
        sorted_events = sorted(all_events)
        return sorted_events


if __name__ == "__main__":
    collector = EventCollector()
    events_today = collector.events_today()
    print(f"Found {len(events_today)} events for today:")
    for e in collector.events_today():
        print(e)
